from __future__ import annotations

import re
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import Cookie, Depends, FastAPI, Header, HTTPException, Request, Response
from itsdangerous import BadSignature, Signer
from pydantic import BaseModel, EmailStr, Field, PositiveInt

app = FastAPI(title="TRSP2 - Контрольная работа №2")

SECRET_KEY = "change-this-secret-key"
SESSION_COOKIE_NAME = "session_token"
SESSION_MAX_AGE_SECONDS = 300
SESSION_EXTEND_THRESHOLD_SECONDS = 180

signer = Signer(SECRET_KEY)

users_db = {
    "user123": {"password": "password123", "full_name": "User 123", "email": "user123@example.com"},
    "alice": {"password": "alicepass", "full_name": "Alice Example", "email": "alice@example.com"},
}
sessions: dict[str, str] = {}

sample_products = [
    {"product_id": 123, "name": "Smartphone", "category": "Electronics", "price": 599.99},
    {"product_id": 456, "name": "Phone Case", "category": "Accessories", "price": 19.99},
    {"product_id": 789, "name": "Iphone", "category": "Electronics", "price": 1299.99},
    {"product_id": 101, "name": "Headphones", "category": "Accessories", "price": 99.99},
    {"product_id": 202, "name": "Smartwatch", "category": "Electronics", "price": 299.99},
]


@app.get("/")
def root() -> dict:
    return {
        "message": "API is running",
        "docs": "/docs",
        "tasks": ["3.1-3.2", "5.1-5.5"],
    }


@app.get("/favicon.ico")
def favicon() -> Response:
    return Response(status_code=204)


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1)
    email: EmailStr
    age: Optional[PositiveInt] = None
    is_subscribed: Optional[bool] = None


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class CommonHeaders(BaseModel):
    user_agent: str
    accept_language: str

    @staticmethod
    def _validate_accept_language(value: str) -> str:
        pattern = re.compile(
            r"^[A-Za-z]{1,8}(-[A-Za-z0-9]{1,8})?"
            r"(\s*;q=0\.\d+|\s*;q=1\.0)?"
            r"(\s*,\s*[A-Za-z]{1,8}(-[A-Za-z0-9]{1,8})?"
            r"(\s*;q=0\.\d+|\s*;q=1\.0)?)*$"
        )
        if not pattern.match(value):
            raise HTTPException(status_code=400, detail="Invalid Accept-Language format")
        return value

    @classmethod
    def from_headers(
        cls,
        user_agent: Optional[str] = Header(default=None, alias="User-Agent"),
        accept_language: Optional[str] = Header(default=None, alias="Accept-Language"),
    ) -> "CommonHeaders":
        if not user_agent or not accept_language:
            raise HTTPException(status_code=400, detail="Missing required headers")
        return cls(
            user_agent=user_agent,
            accept_language=cls._validate_accept_language(accept_language),
        )


def _create_session_token(user_id: str, last_active_ts: int) -> str:
    payload = f"{user_id}.{last_active_ts}"
    return signer.sign(payload).decode("utf-8")


def _verify_session_token(token: str) -> tuple[str, int]:
    try:
        payload = signer.unsign(token).decode("utf-8")
    except BadSignature as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc

    parts = payload.split(".")
    if len(parts) < 2:
        raise HTTPException(status_code=401, detail="Invalid session")

    user_id = parts[0]
    try:
        last_active_ts = int(parts[1])
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc

    return user_id, last_active_ts


def _authorize_session(token: str, response: Response) -> dict:
    user_id, last_active_ts = _verify_session_token(token)
    username = sessions.get(user_id)
    if not username or username not in users_db:
        raise HTTPException(status_code=401, detail="Unauthorized")

    now = int(time.time())
    if last_active_ts > now + 5:
        raise HTTPException(status_code=401, detail="Invalid session")

    elapsed = now - last_active_ts
    if elapsed >= SESSION_MAX_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="Session expired")

    if SESSION_EXTEND_THRESHOLD_SECONDS <= elapsed < SESSION_MAX_AGE_SECONDS:
        new_token = _create_session_token(user_id, now)
        response.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=new_token,
            httponly=True,
            secure=False,
            max_age=SESSION_MAX_AGE_SECONDS,
        )

    profile = users_db[username]
    return {"username": username, "full_name": profile["full_name"], "email": profile["email"]}


@app.post("/create_user")
def create_user(user: UserCreate) -> dict:
    return user.model_dump()


@app.get("/products/search")
def search_products(keyword: str, category: Optional[str] = None, limit: int = 10) -> list[dict]:
    if limit <= 0:
        raise HTTPException(status_code=400, detail="Limit must be positive")

    keyword_lower = keyword.lower()
    results = [
        product
        for product in sample_products
        if keyword_lower in product["name"].lower()
    ]

    if category:
        category_lower = category.lower()
        results = [product for product in results if product["category"].lower() == category_lower]

    return results[:limit]


@app.get("/product/{product_id}")
def get_product(product_id: int) -> dict:
    for product in sample_products:
        if product["product_id"] == product_id:
            return product
    raise HTTPException(status_code=404, detail="Product not found")


@app.post("/login")
async def login(request: Request, response: Response) -> dict:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        data = await request.json()
    else:
        form = await request.form()
        data = dict(form)

    payload = LoginRequest(**data)
    user = users_db.get(payload.username)
    if not user or user["password"] != payload.password:
        raise HTTPException(status_code=401, detail="Unauthorized")

    user_id = str(uuid.uuid4())
    now = int(time.time())
    token = _create_session_token(user_id, now)
    sessions[user_id] = payload.username

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,
        max_age=SESSION_MAX_AGE_SECONDS,
    )
    return {"message": "Login successful", "session_token": token}


@app.get("/user")
def get_user(
    response: Response,
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> dict:
    if not session_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    return _authorize_session(session_token, response)


@app.get("/profile")
def get_profile(
    response: Response,
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> dict:
    if not session_token:
        raise HTTPException(status_code=401, detail="Unauthorized")

    profile = _authorize_session(session_token, response)
    return {"message": "Profile data", "profile": profile}


@app.get("/headers")
def headers(common: CommonHeaders = Depends(CommonHeaders.from_headers)) -> dict:
    return {
        "User-Agent": common.user_agent,
        "Accept-Language": common.accept_language,
    }


@app.get("/info")
def info(response: Response, common: CommonHeaders = Depends(CommonHeaders.from_headers)) -> dict:
    response.headers["X-Server-Time"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return {
        "message": "Добро пожаловать! Ваши заголовки успешно обработаны.",
        "headers": {
            "User-Agent": common.user_agent,
            "Accept-Language": common.accept_language,
        },
    }
