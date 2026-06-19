"""
Todo TAGS API
=============
Runs on Node 2.

WHAT MAKES THIS ONE DIFFERENT:
  Adds tags/categories (e.g. "work", "home", "urgent") to todos, plus a
  /todos/search endpoint for free-text search across titles, and a
  /tags endpoint that lists every tag in use with counts. This is the
  "unique feature" angle for this pod — neither todo-core-api nor
  todo-priority-api has tagging or search.

WHY FastAPI?
  - Gives us a real HTTP API to call
  - Built-in /docs page (Swagger UI) so you can click-test every endpoint
  - Easy to add Prometheus metrics — one library, three lines

ENDPOINTS:
  GET    /                  → welcome message (tells you pod/node, useful in K8s)
  GET    /healthz            → health check (used by Kubernetes liveness probe)
  GET    /todos              → list all todos (filter by ?tag=)
  POST   /todos              → create a todo {"title","tags": ["work","urgent"]}
  GET    /todos/{id}         → get a single todo
  PATCH  /todos/{id}         → update a todo
  DELETE /todos/{id}         → delete a todo by ID
  GET    /todos/search?q=    → free-text search across todo titles
  GET    /tags                → list all tags currently in use, with counts
  GET    /metrics            → Prometheus metrics (scraped by Grafana Alloy)
  GET    /docs                → Swagger UI (auto-generated, great for learning)
"""

import logging
import os
import time
import uuid
from collections import Counter as CollCounter

from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import Response

# ── Logging setup ─────────────────────────────────────────────────────────────
APP_NAME = "todo-tags-api"

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

# This app's unique metric: how many times has /todos/search been hit?
# Lets you see in Grafana whether the search feature is actually being used.
search_requests_total = Counter(
    "search_requests_total",
    "Total number of /todos/search calls",
    ["app"],
)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Todo TAGS API",
    description="Learning project: todos with tags + search running in Kubernetes (Node 2)",
    version="1.0.0",
)

todos: dict = {}


# ── Pydantic models ────────────────────────────────────────────────────────────
class TodoCreate(BaseModel):
    title: str
    tags: list[str] = []
    done: bool = False


class TodoUpdate(BaseModel):
    title: str | None = None
    tags: list[str] | None = None
    done: bool | None = None


class Todo(BaseModel):
    id: str
    title: str
    tags: list[str]
    done: bool
    created_at: float
    updated_at: float


class TagCount(BaseModel):
    tag: str
    count: int


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
        "message": "Todo TAGS API is running!",
        "app": APP_NAME,
        "pod": pod,
        "node": node,
        "docs": "/docs",
    }


@app.get("/healthz")
def healthz():
    return {"status": "ok", "app": APP_NAME}


@app.get("/todos", response_model=list[Todo])
def list_todos(tag: str | None = None, done: bool | None = None):
    """List todos, optionally filtered by ?tag=work and/or ?done=false."""
    items = list(todos.values())
    if tag is not None:
        items = [t for t in items if tag in t["tags"]]
    if done is not None:
        items = [t for t in items if t["done"] == done]
    logger.info(f"listing todos count={len(items)} tag={tag} done={done}")
    return items


@app.get("/todos/search", response_model=list[Todo])
def search_todos(q: str):
    """Free-text, case-insensitive search across todo titles. ?q=milk"""
    search_requests_total.labels(app=APP_NAME).inc()
    needle = q.lower()
    items = [t for t in todos.values() if needle in t["title"].lower()]
    logger.info(f"search query={q!r} results={len(items)}")
    return items


@app.get("/tags", response_model=list[TagCount])
def list_tags():
    """List every tag currently in use, with how many todos use it."""
    counts = CollCounter()
    for t in todos.values():
        counts.update(t["tags"])
    result = [TagCount(tag=tag, count=count) for tag, count in counts.most_common()]
    logger.info(f"listing tags count={len(result)}")
    return result


@app.get("/todos/{todo_id}", response_model=Todo)
def get_todo(todo_id: str):
    if todo_id not in todos:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todos[todo_id]


@app.post("/todos", response_model=Todo, status_code=201)
def create_todo(body: TodoCreate):
    """
    Create a new todo with tags.
    Body: {"title": "Buy milk", "tags": ["home", "urgent"]}
    """
    now = time.time()
    todo = Todo(
        id=str(uuid.uuid4())[:8],
        title=body.title,
        tags=body.tags,
        done=body.done,
        created_at=now,
        updated_at=now,
    )
    todos[todo.id] = todo.dict()
    todos_total.labels(app=APP_NAME).inc()
    logger.info(f"created todo id={todo.id} title={todo.title!r} tags={todo.tags}")
    return todo


@app.patch("/todos/{todo_id}", response_model=Todo)
def update_todo(todo_id: str, body: TodoUpdate):
    if todo_id not in todos:
        raise HTTPException(status_code=404, detail="Todo not found")
    existing = todos[todo_id]
    if body.title is not None:
        existing["title"] = body.title
    if body.tags is not None:
        existing["tags"] = body.tags
    if body.done is not None:
        existing["done"] = body.done
    existing["updated_at"] = time.time()
    logger.info(f"updated todo id={todo_id}")
    return existing


@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: str):
    if todo_id not in todos:
        logger.warning(f"delete failed: todo id={todo_id} not found")
        raise HTTPException(status_code=404, detail="Todo not found")
    del todos[todo_id]
    todos_deleted_total.labels(app=APP_NAME).inc()
    logger.info(f"deleted todo id={todo_id}")
    return None


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)