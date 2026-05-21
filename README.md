# Project Management MAS (LR13, variant 14, advanced)

## Данные студента
- ФИО (полностью): Новохатский Иван Эдуардович
- Группа: 220032-11
- Вариант: 14
- Номер лабораторной: 13
- Сложность: повышенная

## Что реализовано
Проект выполнен по повышенной сложности для варианта 14 (управление проектами).

1. Полная мультиагентная система:
- 4 Go-агента: `task-agent`, `deadline-agent`, `resource-agent`, `budget-agent`
- Python-оркестратор (FastAPI)
- Python LLM-агент (Ollama)

2. Pipeline-обработка задач:
- endpoint `POST /run`
- последовательность этапов: task -> deadline -> resource -> budget -> llm

3. Распределенная трассировка:
- OpenTelemetry в оркестраторе
- Jaeger: trace `orchestrator: run_pipeline`

4. Агент с состоянием:
- `resource-agent` хранит счетчик в Redis (`resource_agent_count`)

5. Динамическое масштабирование (реализовано через Docker API):
- при `len(pending) > SCALE_THRESHOLD` оркестратор вызывает Docker SDK
- автоматически запускается дополнительный контейнер `agent-task-auto-*`
- добавлены метрики `scale_signals` и `scale_actions`

6. Аукционное распределение:
- выбор победителя `winner` по минимальной стоимости (`cost`)

7. Интеграция LLM:
- Ollama (`qwen2.5:3b`)
- LLM-результат в поле `llm_summary`

8. Веб-интерфейс мониторинга:
- Streamlit dashboard на `http://localhost:8501`

## Запуск
1. Проверить Ollama:
- `ollama list`
- при необходимости: `ollama pull qwen2.5:3b`

2. Поднять систему:
- `docker compose up -d --build`

3. Проверить контейнеры:
- `docker compose ps`

## Проверка
1. `curl http://localhost:8000/health`
2. `curl -X POST "http://localhost:8000/run" -H "Content-Type: application/json" -d "{\"title\":\"Final check\",\"description\":\"Run pipeline\",\"due_days\":5,\"estimated_hours\":16,\"budget\":2500}"`
3. Jaeger: `http://localhost:16686` -> service `orchestrator` -> operation `run_pipeline`
4. Dashboard: `http://localhost:8501`
5. Автоскейл:
- дать параллельную нагрузку на `/run`
- проверить `scale_actions > 0` в `/health`
- проверить контейнер `agent-task-auto-*` в `docker ps`

## Тесты
1. `cd orchestrator && .venv\Scripts\python.exe -m pytest -q`
2. `python -m pytest -q tests\test_llm_agent.py`
3. `cd agents\task-agent && go test ./...`
4. `cd agents\deadline-agent && go test ./...`
5. `cd agents\resource-agent && go test ./...`
6. `cd agents\budget-agent && go test ./...`

## Скриншоты
Папка в репозитории: `./scrins`
1. `01_dashboard.png`
2. `02_health.png`
3. `03_run.png`
4. `04_jaeger_trace.png`
5. `05_docker_ps.png`
6. `06_go_tests.png`
7. `07_autoscaling_action.png`
