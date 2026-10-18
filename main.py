
import base64
import math
import time
import asyncio

from collections import defaultdict, deque

from fastapi import FastAPI, Header, HTTPException, Query, Request, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


app = FastAPI(title="Orders API")

# Assignment settings
TOTAL_ORDERS = 46
RATE_LIMIT = 16
WINDOW_SECONDS = 10

# In-memory storage
idempotency_store = {}
created_orders = []
client_requests = defaultdict(deque)

# Locks prevent simultaneous requests from corrupting shared state
rate_limit_lock = asyncio.Lock()
order_lock = asyncio.Lock()


# CORS: allow browser requests and let JavaScript read Retry-After
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)


# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # Browser CORS preflight requests should not consume the limit
    if request.method == "OPTIONS":
        return await call_next(request)

    client_id = request.headers.get("X-Client-Id")

    # Use the client IP if X-Client-Id is not supplied
    if not client_id:
        client_id = (
            request.client.host
            if request.client
            else "unknown-client"
        )

    now = time.monotonic()

    async with rate_limit_lock:
        requests = client_requests[client_id]

        # Remove requests that are outside the rolling 10-second window
        while requests and now - requests[0] >= WINDOW_SECONDS:
            requests.popleft()

        # Reject the request if this client has already made 16 requests
        if len(requests) >= RATE_LIMIT:
            retry_after = max(
                1,
                math.ceil(WINDOW_SECONDS - (now - requests[0]))
            )

            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded"},
                headers={
                    "Retry-After": str(retry_after)
                },
            )

        # Record this request
        requests.append(now)

    return await call_next(request)


# Home endpoint
@app.get("/")
async def home():
    return {
        "message": "Orders API is running",
        "total_orders": TOTAL_ORDERS,
        "rate_limit": RATE_LIMIT,
        "window_seconds": WINDOW_SECONDS,
    }


# Create an order with idempotency support
@app.post("/orders", status_code=201)
async def create_order(
    payload: dict = Body(default={}),
    idempotency_key: str = Header(
        ...,
        alias="Idempotency-Key"
    ),
):
    async with order_lock:
        # If this key was already used, return the original order
        if idempotency_key in idempotency_store:
            return idempotency_store[idempotency_key]

        # Create a new order
        order_id = f"created-{len(created_orders) + 1}"

        order = {
            "id": order_id,
            "data": payload,
        }

        created_orders.append(order)
        idempotency_store[idempotency_key] = order

        return order


# Return orders with cursor-based pagination
@app.get("/orders")
async def get_orders(
    limit: int = Query(default=10, ge=1, le=46),
    cursor: str | None = Query(default=None),
):
    # The assignment's fixed list of order IDs is 1 through 46
    all_orders = [
        {"id": order_id}
        for order_id in range(1, TOTAL_ORDERS + 1)
    ]

    # Decode the cursor into the starting position
    offset = 0

    if cursor:
        try:
            decoded = base64.urlsafe_b64decode(
                cursor.encode("utf-8")
            ).decode("utf-8")

            offset = int(decoded)

            if offset < 0 or offset > TOTAL_ORDERS:
                raise ValueError("Invalid cursor")

        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Invalid cursor",
            )

    # Select at most 'limit' orders
    page = all_orders[offset:offset + limit]

    # Create the next cursor if more orders remain
    next_offset = offset + len(page)

    if next_offset < TOTAL_ORDERS:
        next_cursor = base64.urlsafe_b64encode(
            str(next_offset).encode("utf-8")
        ).decode("utf-8")
    else:
        next_cursor = None

    return {
        "orders": page,
        "next_cursor": next_cursor,
    }
