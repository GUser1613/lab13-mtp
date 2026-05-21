import asyncio

from fastapi.testclient import TestClient

import main

client = TestClient(main.app)


def test_health_shape():
    r = client.get('/health')
    assert r.status_code == 200
    assert 'status' in r.json()


def test_on_result_sets_future():
    async def _run():
        fut = asyncio.get_event_loop().create_future()
        main.pending['x1'] = fut

        class Msg:
            data = b'{"id":"x1","ok":true}'

        await main.on_result(Msg())
        assert fut.done()
        assert '"id":"x1"' in fut.result().replace(' ', '')

    asyncio.run(_run())


def test_run_pipeline_success(monkeypatch):
    async def fake_request(subject, payload, timeout=6.0):
        return {"id": payload.get("id", "t"), "subject": subject}

    monkeypatch.setattr(main, 'request', fake_request)

    async def _run():
        task = main.ProjectTask(title='t', description='d', due_days=1, estimated_hours=2, budget=10)
        out = await main.run_pipeline(task)
        assert 'winner' in out
        assert len(out['pipeline']) == 5

    asyncio.run(_run())


def test_run_pipeline_timeout(monkeypatch):
    async def fake_request(subject, payload, timeout=6.0):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(main, 'request', fake_request)

    async def _run():
        task = main.ProjectTask(title='t', description='d', due_days=1, estimated_hours=2, budget=10)
        try:
            await main.run_pipeline(task)
            raise AssertionError('Expected timeout HTTPException')
        except Exception as ex:
            assert '504' in str(ex) or 'Pipeline timeout' in str(ex)

    asyncio.run(_run())


def test_retry_run_eventual_success(monkeypatch):
    calls = {'n': 0}

    async def fake_run(task):
        calls['n'] += 1
        if calls['n'] < 3:
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail='x')
        return {'ok': True}

    monkeypatch.setattr(main, 'run_pipeline', fake_run)

    async def _run():
        task = main.ProjectTask(title='t', description='d', due_days=1, estimated_hours=2, budget=10)
        out = await main.retry_run(task)
        assert out['ok'] is True
        assert calls['n'] == 3

    asyncio.run(_run())
