"""
Todo CORE API
=============
Runs on Node 1.

WHAT MAKES THIS ONE DIFFERENT:
  This is the "plain" todo API — basic create/read/delete, nothing fancy.
  It's the baseline the other two APIs (priority, tags) build on top of.

WHY FastAPI?
  - Gives us a real HTTP API to call
  - Built-in /docs page (Swagger UI) so you can click-test every endpoint
  - Easy to add Prometheus metrics — one library, three lines

WHAT THIS APP DOES:
  - Stores todos in memory (resets on pod restart — fine for learning)
  - Exposes REST endpoints for create / read / delete
  - Exposes /metrics so Grafana Alloy can scrape numbers about the app
  - Writes structured logs so Loki can index and search them

ENDPOINTS:
  GET    /            → welcome message (tells you pod/node, useful in K8s)
  GET    /healthz      → health check (used by Kubernetes liveness probe)
  GET    /todos        → list all todos
  POST   /todos        → create a todo   body: {"title": "Buy milk"}
  GET    /todos/{id}   → get a single todo
  PATCH  /todos/{id}   → toggle done / update title
  DELETE /todos/{id}   → delete a todo by ID
  GET    /metrics      → Prometheus metrics (scraped by Grafana Alloy)
  GET    /docs         → Swagger UI (auto-generated, great for learning)
"""

import logging
import os
import time
import uuid

from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from pydantic import BaseModel
from starlette.requests import Request
from starlette.responses import Response

# ── Logging setup ─────────────────────────────────────────────────────────────
# We log as JSON so Loki can parse fields (pod name, level, message) separately.
# In Grafana you can then filter by level="error" or app="todo-core-api"
APP_NAME = "todo-core-api"

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","app":"' + APP_NAME +
           '","pod":"' + os.getenv("POD_NAME", "unknown") + '","node":"' +
           os.getenv("NODE_NAME", "unknown") + '","msg":"%(message)s"}',
)
logger = logging.getLogger(__name__)

# ── Prometheus metrics ────────────────────────────────────────────────────────
# These are the numbers Grafana Alloy will scrape from /metrics every 15s.
# They then appear as graphs in Grafana dashboards.
#
# Counter   = ever-increasing number (total requests, total errors)
# Histogram = tracks how long things take (request duration buckets)

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status", "app"],  # labels let you filter in Grafana
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

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Todo CORE API",
    description="Learning project: basic todo CRUD running in Kubernetes (Node 1)",
    version="1.0.0",
)

# In-memory store: { id: {id, title, done, created_at, updated_at} }
todos: dict = {}


# ── Pydantic models (request/response shapes) ─────────────────────────────────
class TodoCreate(BaseModel):
    title: str                  # required: the text of the todo
    done: bool = False          # optional: default not done


class TodoUpdate(BaseModel):
    title: str | None = None
    done: bool | None = None


class Todo(BaseModel):
    id: str
    title: str
    done: bool
    created_at: float
    updated_at: float


# ── Middleware: record metrics for every request ───────────────────────────────
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    # Record in Prometheus (skip the /metrics endpoint itself)
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
    """Welcome message — also tells you which pod/node you hit (useful in K8s)."""
    pod = os.getenv("POD_NAME", "unknown")
    node = os.getenv("NODE_NAME", "unknown")
    logger.info("root endpoint called")
    return {
        "message": "Todo CORE API is running!",
        "app": APP_NAME,
        "pod": pod,
        "node": node,
        "docs": "/docs",
    }


@app.get("/healthz")
def healthz():
    """
    Health check endpoint.
    Kubernetes calls this every 15s. If it returns non-200, K8s restarts the pod.
    Grafana Alloy also tracks this as an 'up' metric.
    """
    return {"status": "ok", "app": APP_NAME}


@app.get("/todos", response_model=list[Todo])
def list_todos(done: bool | None = None):
    """Return all todos. Optionally filter with ?done=true or ?done=false."""
    items = list(todos.values())
    if done is not None:
        items = [t for t in items if t["done"] == done]
    logger.info(f"listing todos count={len(items)} filter_done={done}")
    return items


@app.get("/todos/{todo_id}", response_model=Todo)
def get_todo(todo_id: str):
    """Get a single todo by ID."""
    if todo_id not in todos:
        raise HTTPException(status_code=404, detail="Todo not found")
    return todos[todo_id]


@app.post("/todos", response_model=Todo, status_code=201)
def create_todo(body: TodoCreate):
    """
    Create a new todo.
    Body: {"title": "Buy milk"}
    Returns the created todo with a generated ID.
    """
    now = time.time()
    todo = Todo(
        id=str(uuid.uuid4())[:8],   # short 8-char ID for readability
        title=body.title,
        done=body.done,
        created_at=now,
        updated_at=now,
    )
    todos[todo.id] = todo.dict()
    todos_total.labels(app=APP_NAME).inc()
    logger.info(f"created todo id={todo.id} title={todo.title!r}")
    return todo


@app.patch("/todos/{todo_id}", response_model=Todo)
def update_todo(todo_id: str, body: TodoUpdate):
    """Update a todo's title and/or done status."""
    if todo_id not in todos:
        raise HTTPException(status_code=404, detail="Todo not found")
    existing = todos[todo_id]
    if body.title is not None:
        existing["title"] = body.title
    if body.done is not None:
        existing["done"] = body.done
    existing["updated_at"] = time.time()
    logger.info(f"updated todo id={todo_id}")
    return existing


@app.delete("/todos/{todo_id}", status_code=204)
def delete_todo(todo_id: str):
    """Delete a todo by ID. Returns 404 if not found."""
    if todo_id not in todos:
        logger.warning(f"delete failed: todo id={todo_id} not found")
        raise HTTPException(status_code=404, detail="Todo not found")
    del todos[todo_id]
    todos_deleted_total.labels(app=APP_NAME).inc()
    logger.info(f"deleted todo id={todo_id}")
    return None


@app.get("/metrics")
def metrics():
    """
    Prometheus metrics endpoint.
    Grafana Alloy scrapes this URL every 15 seconds.
    The numbers here become the graphs in your Grafana dashboards.
    """
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)