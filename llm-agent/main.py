import asyncio
import json
import os

import httpx

NATS_URL = os.getenv("NATS_URL", "nats://localhost:4222")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL = os.getenv("LLM_MODEL", "qwen2.5:3b")


def build_output(task_id: str, text: str) -> dict:
    return {"id": task_id, "llm_summary": text}


async def main():
    import nats

    nc = await nats.connect(NATS_URL)

    async def cb(msg):
        data = json.loads(msg.data.decode())
        prompt = data.get("prompt", "Отвечай только на русском. Оцени задачу")
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{OLLAMA_URL}/api/generate",
                json={"model": MODEL, "prompt": prompt, "stream": False},
            )
            text = r.json().get("response", "") if r.status_code == 200 else f"LLM error: {r.text}"
        out = build_output(data.get("id"), text)
        await nc.publish("results.llm", json.dumps(out).encode())

    await nc.subscribe("tasks.llm", cb=cb)
    while True:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
