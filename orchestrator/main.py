import asyncio
import json
import os
import uuid
from collections import defaultdict

import httpx
import nats
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

app = FastAPI(title="Project Management MAS")

nc = None
pending = {}
metrics = defaultdict(int)
agent_health = defaultdict(lambda: {"processed": 0})
tracer = trace.get_tracer("orchestrator")

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
    global nc
    resource = Resource.create({"service.name": "orchestrator"})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    nc = await nats.connect(NATS_URL)
    await nc.subscribe("results.*", cb=on_result)


@app.on_event("shutdown")
async def shutdown():
    if nc:
        await nc.close()


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
            if len(pending) > 10:
                metrics["scale_signals"] += 1

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
