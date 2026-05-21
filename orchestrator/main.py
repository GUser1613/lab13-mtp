import asyncio
import json
import os
import uuid
from collections import defaultdict

import httpx
import nats
import docker
from fastapi import FastAPI, HTTPException
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from pydantic import BaseModel

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:3b")
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://jaeger:4317")
SCALE_THRESHOLD = int(os.getenv("SCALE_THRESHOLD", "10"))
SCALE_MAX_REPLICAS = int(os.getenv("SCALE_MAX_REPLICAS", "3"))
SCALE_COOLDOWN_SEC = int(os.getenv("SCALE_COOLDOWN_SEC", "30"))
SCALE_TARGET_SERVICE = os.getenv("SCALE_TARGET_SERVICE", "agent-task")
COMPOSE_PROJECT = os.getenv("COMPOSE_PROJECT_NAME", "project-management-mas")

app = FastAPI(title="Project Management MAS")

nc = None
pending = {}
metrics = defaultdict(int)
agent_health = defaultdict(lambda: {"processed": 0})
tracer = trace.get_tracer("orchestrator")
docker_client = None
last_scale_ts = 0.0

class ProjectTask(BaseModel):
    title: str
    description: str
    due_days: int
    estimated_hours: int
    budget: float


async def request(subject: str, payload: dict, timeout: float = 6.0):
    task_id = str(uuid.uuid4())
    payload["id"] = task_id
    fut = asyncio.get_event_loop().create_future()
    pending[task_id] = fut
    await nc.publish(subject, json.dumps(payload).encode())
    try:
        raw = await asyncio.wait_for(fut, timeout=timeout)
        return json.loads(raw)
    finally:
        pending.pop(task_id, None)


async def on_result(msg):
    data = json.loads(msg.data.decode())
    task_id = data.get("id")
    if task_id in pending and not pending[task_id].done():
        pending[task_id].set_result(msg.data.decode())


@app.on_event("startup")
async def startup():
    global nc, docker_client
    resource = Resource.create({"service.name": "orchestrator"})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    nc = await nats.connect(NATS_URL)
    await nc.subscribe("results.*", cb=on_result)
    try:
        docker_client = docker.from_env()
    except Exception:
        docker_client = None


@app.on_event("shutdown")
async def shutdown():
    if nc:
        await nc.close()
    if docker_client:
        docker_client.close()


def _scale_if_needed() -> bool:
    """Auto-scale one extra agent container when queue pressure is high."""
    global last_scale_ts
    if docker_client is None:
        return False
    if len(pending) <= SCALE_THRESHOLD:
        return False

    now = asyncio.get_event_loop().time()
    if now - last_scale_ts < SCALE_COOLDOWN_SEC:
        return False

    filters = {
        "label": [
            f"com.docker.compose.project={COMPOSE_PROJECT}",
            f"com.docker.compose.service={SCALE_TARGET_SERVICE}",
        ]
    }
    running = docker_client.containers.list(filters=filters)
    if len(running) >= SCALE_MAX_REPLICAS:
        return False

    image = f"{COMPOSE_PROJECT}-{SCALE_TARGET_SERVICE}"
    network = f"{COMPOSE_PROJECT}_default"
    container_name = f"{COMPOSE_PROJECT}-{SCALE_TARGET_SERVICE}-auto-{int(now)}"
    docker_client.containers.run(
        image=image,
        name=container_name,
        detach=True,
        network=network,
        environment={"NATS_URL": NATS_URL, "AGENT_ID": f"{SCALE_TARGET_SERVICE}-auto"},
        labels={
            "com.docker.compose.project": COMPOSE_PROJECT,
            "com.docker.compose.service": SCALE_TARGET_SERVICE,
            "mas.autoscaled": "true",
        },
        restart_policy={"Name": "unless-stopped"},
    )
    last_scale_ts = now
    metrics["scale_actions"] += 1
    return True


@app.get("/health")
async def health():
    return {"status": "ok", "metrics": dict(metrics), "agents": dict(agent_health)}


@app.post("/run")
async def run_pipeline(task: ProjectTask):
    with tracer.start_as_current_span("run_pipeline") as span:
        span.set_attribute("task.title", task.title)
        span.set_attribute("task.estimated_hours", task.estimated_hours)
        span.set_attribute("task.budget", task.budget)
        bids = [
            {"agent": "task-agent", "cost": task.estimated_hours * 1.1},
            {"agent": "task-agent-2", "cost": task.estimated_hours * 1.0},
        ]
        winner = min(bids, key=lambda x: x["cost"])
        span.set_attribute("auction.winner", winner["agent"])
        span.set_attribute("auction.cost", winner["cost"])

        try:
            step1 = await request("tasks.task", {"task": task.model_dump(), "winner": winner}, timeout=6)
            step2 = await request("tasks.deadline", {"task": task.model_dump(), "prev": step1}, timeout=6)
            step3 = await request("tasks.resource", {"task": task.model_dump(), "prev": step2}, timeout=6)
            step4 = await request("tasks.budget", {"task": task.model_dump(), "prev": step3}, timeout=6)
            llm_payload = {
                "prompt": f"Отвечай только на русском. Оцени риск проекта: {task.model_dump_json()}"
            }
            step5 = await request("tasks.llm", llm_payload, timeout=20)

            metrics["processed"] += 1
            if len(pending) > SCALE_THRESHOLD:
                metrics["scale_signals"] += 1
                _scale_if_needed()

            return {
                "winner": winner,
                "pipeline": [step1, step2, step3, step4, step5],
                "jaeger": "http://localhost:16686",
            }
        except asyncio.TimeoutError:
            metrics["timeouts"] += 1
            span.set_attribute("error.timeout", True)
            raise HTTPException(status_code=504, detail="Pipeline timeout")


@app.post("/retry-run")
async def retry_run(task: ProjectTask):
    for _ in range(3):
        try:
            return await run_pipeline(task)
        except HTTPException:
            await asyncio.sleep(0.3)
    raise HTTPException(status_code=500, detail="Retries exhausted")
