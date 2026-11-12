import json
import logging
import re
import time
import uuid
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeout
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from app import repositories, security
from app.config import settings
from app.db import get_db
from app.errors import APIError, api_error, envelope
from app.inbox_api import router as inbox_router
from app.models import Transfer, User
from app.schedule_api import router as schedule_router
from app.schemas import (
    MAX_AMOUNT,
    AccountOutput,
    LoginInput,
    TokenOutput,
    TransferInput,
    TransferOutput,
    UserOutput,
)
from app.transfers import execute_transfer
from app.v2 import router as v2_router

app = FastAPI(
    title="Moneta · Simulated Banking API",
    version="2.0.0",
    docs_url="/docs" if settings().docs_enabled else None,
    redoc_url=None,
    openapi_url="/openapi.json" if settings().docs_enabled else None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings().origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
    expose_headers=["X-Request-ID", "X-Idempotency-Replayed"],
)
app.add_exception_handler(APIError, api_error)
logger = logging.getLogger("banking")
logging.basicConfig(level=logging.INFO, format="%(message)s")
DB = Annotated[Session, Depends(get_db)]
Actor = Annotated[User, Depends(security.current_user)]
Customer = Annotated[User, Depends(security.require_roles("CUSTOMER"))]
PREFIX = "/api/v1"
app.include_router(v2_router)
app.include_router(schedule_router)
app.include_router(inbox_router)


@app.exception_handler(OperationalError)
@app.exception_handler(PoolTimeout)
async def database_unavailable(request: Request, exc: Exception):
    return JSONResponse(
        envelope(
            "SERVICE_UNAVAILABLE",
            "Database temporarily unavailable. Retry the original request safely.",
            request.state.request_id,
        ),
        status_code=503,
    )


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    start = time.monotonic()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error(
            json.dumps({"request_id": request.state.request_id, "error_type": type(exc).__name__})
        )
        response = JSONResponse(
            envelope(
                "INTERNAL_ERROR",
                "Something went wrong. Try again with the same request key.",
                request.state.request_id,
            ),
            status_code=500,
        )
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    logger.info(
        json.dumps(
            {
                "request_id": request.state.request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.monotonic() - start) * 1000),
            }
        )
    )
    return response


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    fields = [
        {"field": ".".join(str(x) for x in error["loc"]), "message": error["msg"]}
        for error in exc.errors()
    ]
    return JSONResponse(
        envelope(
            "VALIDATION_ERROR",
            "Check the highlighted fields.",
            request.state.request_id,
            {"fields": fields},
        ),
        status_code=422,
    )


@app.exception_handler(HTTPException)
async def http_error(request: Request, exc: HTTPException):
    return JSONResponse(
        envelope(
            "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR",
            str(exc.detail),
            request.state.request_id,
        ),
        status_code=exc.status_code,
    )


@app.get("/health/live")
def live():
    return {"status": "ok"}


@app.get("/health/ready")
def ready(db: DB):
    try:
        revision = db.scalar(text("SELECT version_num FROM alembic_version"))
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        if revision != ScriptDirectory.from_config(Config("alembic.ini")).get_current_head():
            raise ValueError("Migration not ready")
    except Exception as exc:
        raise APIError(503, "NOT_READY", "Database is not ready.") from exc
    return {"status": "ready", "migration": revision}


def set_cookie(response: Response, raw: str):
    response.set_cookie(
        security.COOKIE,
        raw,
        httponly=True,
        secure=settings().cookie_secure,
        samesite="strict",
        path=security.COOKIE_PATH,
        max_age=settings().refresh_days * 86400,
    )


@app.post(
    PREFIX + "/auth/login",
    response_model=TokenOutput,
    dependencies=[Depends(security.origin_guard), Depends(security.limit_login)],
)
def login(payload: LoginInput, response: Response, db: DB):
    body, raw = security.login(db, str(payload.email), payload.password)
    set_cookie(response, raw)
    return body


@app.post(
    PREFIX + "/auth/refresh",
    response_model=TokenOutput,
    dependencies=[Depends(security.origin_guard)],
)
def refresh(request: Request, response: Response, db: DB):
    body, raw = security.refresh(db, request.cookies.get(security.COOKIE))
    set_cookie(response, raw)
    return body


@app.post(PREFIX + "/auth/logout", status_code=204, dependencies=[Depends(security.origin_guard)])
def logout(request: Request, db: DB):
    security.logout(db, request.cookies.get(security.COOKIE))
    response = Response(status_code=204)
    response.delete_cookie(
        security.COOKIE,
        path=security.COOKIE_PATH,
        secure=settings().cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return response


@app.get(PREFIX + "/auth/me", response_model=UserOutput)
def me(user: Actor):
    return user


@app.get(PREFIX + "/accounts", response_model=list[AccountOutput])
def accounts(user: Actor, db: DB):
    return repositories.owned_accounts(db, user.id)


@app.get(PREFIX + "/accounts/{account_id}", response_model=AccountOutput)
def account(account_id: uuid.UUID, user: Actor, db: DB):
    return repositories.owned_account(db, user.id, account_id)


@app.post(PREFIX + "/transfers", response_model=TransferOutput, status_code=201)
def transfer(
    payload: TransferInput,
    request: Request,
    user: Customer,
    db: DB,
    idempotency_key: Annotated[str, Header(min_length=8, max_length=100)],
):
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,100}", idempotency_key):
        raise APIError(
            422, "INVALID_IDEMPOTENCY_KEY", "Use 8–100 letters, numbers, underscores or hyphens."
        )
    status, body, replayed = execute_transfer(
        db, user.id, payload, idempotency_key, request.state.request_id
    )
    return JSONResponse(
        body, status_code=status, headers={"X-Idempotency-Replayed": str(replayed).lower()}
    )


@app.get(PREFIX + "/transfers")
def history(
    user: Actor,
    db: DB,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=50),
    account_id: uuid.UUID | None = None,
    direction: Literal["INCOMING", "OUTGOING"] | None = None,
    reference: str | None = Query(None, max_length=50),
):
    items, total = repositories.history(
        db, user.id, page, page_size, account_id, direction, reference
    )
    return {
        "items": [TransferOutput.model_validate(row).model_dump(mode="json") for row in items],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": (total + page_size - 1) // page_size,
    }


@app.get(PREFIX + "/transfers/{transfer_id}", response_model=TransferOutput)
def detail(transfer_id: uuid.UUID, user: Actor, db: DB):
    row = db.scalar(repositories.visible_query(user.id).where(Transfer.id == transfer_id))
    if row is None:
        raise APIError(404, "TRANSFER_NOT_FOUND", "Transfer not found.")
    return row


@app.get(PREFIX + "/dashboard/summary")
def summary(user: Actor, db: DB):
    rows = repositories.owned_accounts(db, user.id)
    recent, total = repositories.history(db, user.id, page_size=5)
    total_balance = sum(row.balance_vnd for row in rows)
    if total_balance > MAX_AMOUNT:
        raise APIError(
            422,
            "AGGREGATE_LIMIT_EXCEEDED",
            "This V1 summary exceeds the safe integer transport limit.",
        )
    return {
        "total_balance_vnd": total_balance,
        "account_count": len(rows),
        "transfer_count": total,
        "recent_transfers": [
            TransferOutput.model_validate(row).model_dump(mode="json") for row in recent
        ],
    }
