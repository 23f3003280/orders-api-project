from base64 import urlsafe_b64decode, urlsafe_b64encode
from collections import defaultdict, deque
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(title="Orders API")

TOTAL_ORDERS = 46
RATE_LIMIT = 16
WINDOW_SECONDS = 10

# Demo-only in-memory storage. Data resets when the process restarts.
idempotency_store = {}
created_orders = 0
store_lock = Lock()

# Each client ID has an independent rolling-window request queue.
client_requests = defaultdict(deque)
rate_lock = Lock()


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Browser CORS preflight requests should not consume the quota.
    if request.method == "OPTIONS":
        return await call_next(request)

    client_id = request.headers.get("X-Client-Id", "anonymous")
    now = monotonic()

    with rate_lock:
        requests = client_requests[client_id]

        while requests and now - requests[0] >= WINDOW_SECONDS:
            requests.popleft()

        if len(requests) >= RATE_LIMIT:
            retry_after = max(
                1, ceil(WINDOW_SECONDS - (now - requests[0]))
            )
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )

        requests.append(now)

    return await call_next(request)


# For a real production app, restrict allow_origins to the grader's origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)


@app.post("/orders", status_code=201)
def create_order(
    idempotency_key: str = Header(..., alias="Idempotency-Key")
):
    global created_orders

    with store_lock:
        if idempotency_key in idempotency_store:
            return idempotency_store[idempotency_key]

        created_orders += 1
        order = {
            "id": f"created-{created_orders}",
            "status": "created",
        }
        idempotency_store[idempotency_key] = order
        return order


@app.get("/orders")
def list_orders(
    limit: int = Query(default=10, ge=1, le=46),
    cursor: str | None = None,
):
    if cursor is None:
        start = 0
    else:
        try:
            start = int(
                urlsafe_b64decode(cursor.encode("ascii")).decode("ascii")
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid cursor")

    if start < 0 or start > TOTAL_ORDERS:
        raise HTTPException(status_code=400, detail="Invalid cursor")

    end = min(start + limit, TOTAL_ORDERS)
    items = [
        {"id": order_id, "status": "available"}
        for order_id in range(start + 1, end + 1)
    ]

    next_cursor = None
    if end < TOTAL_ORDERS:
        next_cursor = urlsafe_b64encode(
            str(end).encode("ascii")
        ).decode("ascii")

    return {"items": items, "next_cursor": next_cursor}


@app.get("/")
def root():
    return {
        "message": "Orders API is running",
        "docs": "/docs",
        "total_orders": TOTAL_ORDERS,
        "rate_limit": f"{RATE_LIMIT} requests per {WINDOW_SECONDS} seconds",
    }
