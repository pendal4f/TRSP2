# TRSP2 — Контрольная работа №2 (FastAPI)

## Запуск
```
cd C:\Users\User\PycharmProjects\TRSP2
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload
```

## Проверка
База: `http://127.0.0.1:8000`

```
curl http://127.0.0.1:8000/
curl -X POST http://127.0.0.1:8000/create_user -H "Content-Type: application/json" -d "{\"name\":\"Alice\",\"email\":\"alice@example.com\",\"age\":30,\"is_subscribed\":true}"
curl http://127.0.0.1:8000/product/123
curl "http://127.0.0.1:8000/products/search?keyword=phone&category=Electronics&limit=5"
curl -i -X POST http://127.0.0.1:8000/login -H "Content-Type: application/json" -d "{\"username\":\"user123\",\"password\":\"password123\"}"
curl -i http://127.0.0.1:8000/user --cookie "session_token=ВАШ_ТОКЕН"
curl -H "User-Agent: Mozilla/5.0" -H "Accept-Language: en-US,en;q=0.9,es;q=0.8" http://127.0.0.1:8000/headers
curl -i -H "User-Agent: Mozilla/5.0" -H "Accept-Language: en-US,en;q=0.9,es;q=0.8" http://127.0.0.1:8000/info
```
