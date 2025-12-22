# JuCity AI Manager 2

## Запуск Qdrant

```bash
docker compose up -d
```

## Запуск без Docker (Chroma)

```bash
export VECTOR_BACKEND=chroma
export OPENAI_API_KEY=...
python scripts/reindex_nn.py
uvicorn app.main:app --reload
```

## Запуск API

```bash
uvicorn app.main:app --reload --port 8000
```

## Запуск Telegram-бота

Важно: API должен быть запущен перед ботом.

```bash
python3 -m bot.main
```

## Тесты (curl)

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Можно принести свой торт на день рождения?"}'
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Вы работаете 1 января?"}'
curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Какая скидка для ОВЗ?"}'
```


## Запуск в 2 терминалах

Терминал 1:
```bash
uvicorn app.main:app --reload --port 8000
```

Терминал 2:
```bash
python3 -m bot.main
```

Тест:
- открыть бота в Telegram
- /start
- нажать "VR"
- написать "Можно торт на день рождения?"

