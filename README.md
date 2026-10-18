# FastAPI Orders API

A beginner-friendly assignment project demonstrating:

- Idempotent `POST /orders` using the `Idempotency-Key` header
- Cursor-based pagination over fixed order IDs `1` through `46`
- Per-client rolling-window rate limiting: 16 requests per 10 seconds
- CORS support for browser-based grading

## Run locally

Requires Python 3.10 or newer.

```bash
python -m venv venv
```

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Windows Command Prompt:

```bat
venv\Scripts\activate
```

macOS/Linux:

```bash
source venv/bin/activate
```

Install and start:

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open the interactive API docs at <http://127.0.0.1:8000/docs>.

## Test pagination

Start with:

```text
GET /orders?limit=10
```

Copy the returned `next_cursor` exactly into the next request's `cursor` query parameter. Continue until `next_cursor` is `null`. The pages should cover IDs 1–46 exactly once.

## Test idempotency

Send `POST /orders` with this header:

```text
Idempotency-Key: assignment-key-123
```

Repeat the request with the exact same key. Both responses should contain the same order ID.

## Test rate limiting

Send requests with:

```text
X-Client-Id: student-1
```

The first 16 requests within a rolling 10-second window are accepted; the next request is rejected with HTTP 429 and a `Retry-After` header. A different client ID has a separate bucket.

## Deploy on Render

1. Push this folder to a GitHub repository.
2. Create a new Web Service on <https://render.com/>.
3. Select the repository and set:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Deploy and test the public `/docs` URL.

## Important limitations

This assignment example uses in-memory storage. Idempotency records, order creation counters, and rate-limit counters reset on restart and are not shared between multiple service instances. A production service should use a database and a shared rate-limit store such as Redis. For production CORS, replace `allow_origins=["*"]` with the required page origin if known.
