"""
Todo PRIORITY API
==================
Runs on Node 2.

WHAT MAKES THIS ONE DIFFERENT:
  Adds priority levels (low/medium/high) and due dates on top of the basic
  todo concept. Has a dedicated /todos/overdue endpoint and tracks overdue
  todos as its own Prometheus metric — something todo-core-api doesn't have.
  This is the "unique feature" angle for this pod.

WHY FastAPI?
  - Gives us a real HTTP API to call
  - Built-in /docs page (Swagger UI) so you can click-test every endpoint
  - Easy to add Prometheus metrics — one library, three lines

ENDPOINTS:
  GET    /                  → welcome message (tells you pod/node, useful in K8s)
  GET    /healthz            → health check (used by Kubernetes liveness probe)
  GET    /todos              → list all todos (filter by ?priority= or ?done=)
  POST   /todos              → create a todo {"title","priority","due_date"}
  GET    /todos/{id}         → get a single todo
  PATCH  /todos/{id}         → update a todo
  DELETE /todos/{id}         → delete a todo by ID
  GET    /todos/overdue      → list todos whose due_date has passed and aren't done
  GET    /metrics            → Prometheus metrics (scraped by Grafana Alloy)
  GET    /docs                → Swagger UI (auto-generated, great for learning)
"""

import logging
import os
import time
import uuid
from datetime import datetime, timezone
from enum import Enum

from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Gauge, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import Response

# ── Logging setup ─────────────────────────────────────────────────────────────
APP_NAME = "todo-priority-api"

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","app":"' + APP_NAME +
           '","pod":"' + os.getenv("POD_NAME", "unknown") + '","node":"' +
           os.getenv("NODE_NAME", "unknown") + '","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

# ── Prometheus metrics ────────────────────────────────────────────────────────
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status", "app"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint", "app"],
)

todos_total = Counter(
    "todos_total",
    "Total todos created since app started",
    ["app"],
)

todos_deleted_total = Counter(
    "todos_deleted_total",
    "Total todos deleted since app started",
    ["app"],
)

# Gauge = a number that can go up AND down (unlike Counter, which only goes up).
# Perfect for "how many overdue todos right now" since that count changes
# both ways as todos get completed or new ones become overdue.
todos_overdue_gauge = Gauge(
    "todos_overdue",
    "Current number of overdue, not-done todos",
    ["app"],
)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Todo PRIORITY API",
    description="Learning project: todos with priority + due dates running in Kubernetes (Node 2)",
    version="1.0.0",
)

todos: dict = {}


class Priority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


# ── Pydantic models ────────────────────────────────────────────────────────────
class TodoCreate(BaseModel):
    title: str
    priority: Priority = Priority.medium
    due_date: float | None = None   # unix timestamp; optional
    done: bool = False


class TodoUpdate(BaseModel):
    title: str | None = None
    priority: Priority | None = None
    due_date: float | None = None
    done: bool | None = None


class Todo(BaseModel):
    id: str
    title: str
    priority: Priority
    due_date: float | None
    done: bool
    created_at: float
    updated_at: float


def _recompute_overdue_gauge():
    """Recalculate how many todos are overdue and not done; update the Gauge."""
    now = time.time()
    overdue_count = sum(
        1 for t in todos.values()
        if t["due_date"] is not None and t["due_date"] < now and not t["done"]
    )
    todos_overdue_gauge.labels(app=APP_NAME).set(overdue_count)


# ── Middleware: record metrics for every request ───────────────────────────────
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    if request.url.path != "/metrics":
        http_requests_total.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code,
            app=APP_NAME,
        ).inc()
        http_request_duration_seconds.labels(
            method=request.method,
            endpoint=request.url.path,
            app=APP_NAME,
        ).observe(duration)

    return response


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    pod = os.getenv("POD_NAME", "unknown")
    node = os.getenv("NODE_NAME", "unknown")
    logger.info("root endpoint called")
    return {
        "message": "Todo PRIORITY API is running!",
        "app": APP_NAME,
        "pod": pod,
        "node": node,
        "docs": "/docs",
    }


@app.get("/healthz")
def healthz():
    return {"status": "ok", "app": APP_NAME}


@app.get("/todos", response_model=list[Todo])
def list_todos(priority: Priority | None = None, done: bool | None = None):
    """List todos, optionally filtered by ?priority=high and/or ?done=false."""
    items = list(todos.values())
    if priority is not None:
        items = [t for t in items if t["priority"] == priority]
    if done is not None:
        items = [t for t in items if t["done"] == done]
    logger.info(f"listing todos count={len(items)} priority={priority} done={done}")
    return items


@app.get("/todos/overdue", response_model=list[Todo])
def list_overdue():
    """List todos that are past their due_date and not done yet."""
    now = time.time()
    items = [
        t for t in todos.values()
        if t["due_date"] is not None and t["due_date"] < now and not t["done"]
    ]
    logger.info(f"listing overdue todos count={len(items)}")
    return items


@app.get("/todos/{todo_id}", response_model=Todo)
def get_todo(todo_id: str):
    if todo_id not in todos:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todos[todo_id]


@app.post("/todos", response_model=Todo, status_code=201)
def create_todo(body: TodoCreate):
    """
    Create a new todo with a priority and optional due date.
    Body: {"title": "Ship report", "priority": "high", "due_date": 1750000000}
    """
    now = time.time()
    todo = Todo(
        id=str(uuid.uuid4())[:8],
        title=body.title,
        priority=body.priority,
        due_date=body.due_date,
        done=body.done,
        created_at=now,
        updated_at=now,
    )
    todos[todo.id] = todo.dict()
    todos_total.labels(app=APP_NAME).inc()
    _recompute_overdue_gauge()
    logger.info(f"created todo id={todo.id} title={todo.title!r} priority={todo.priority}")
    return todo


@app.patch("/todos/{todo_id}", response_model=Todo)
def update_todo(todo_id: str, body: TodoUpdate):
    if todo_id not in todos:
        raise HTTPException(status_code=404, detail="Todo not found")
    existing = todos[todo_id]
    if body.title is not None:
        existing["title"] = body.title
    if body.priority is not None:
        existing["priority"] = body.priority
    if body.due_date is not None:
        existing["due_date"] = body.due_date
    if body.done is not None:
        existing["done"] = body.done
    existing["updated_at"] = time.time()
    _recompute_overdue_gauge()
    logger.info(f"updated todo id={todo_id}")
    return existing


@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: str):
    if todo_id not in todos:
        logger.warning(f"delete failed: todo id={todo_id} not found")
        raise HTTPException(status_code=404, detail="Todo not found")
    del todos[todo_id]
    todos_deleted_total.labels(app=APP_NAME).inc()
    _recompute_overdue_gauge()
    logger.info(f"deleted todo id={todo_id}")
    return None


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)