"""Manual rate-limit smoke test. Run the API first in another terminal."""
import urllib.error
import urllib.request

URL = "http://127.0.0.1:8000/orders?limit=1"

for number in range(1, 19):
    request = urllib.request.Request(
        URL,
        headers={"X-Client-Id": "student-1"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            print(number, response.status)
    except urllib.error.HTTPError as error:
        print(
            number,
            error.code,
            "Retry-After:",
            error.headers.get("Retry-After"),
        )

request = urllib.request.Request(
    URL,
    headers={"X-Client-Id": "student-2"},
)
try:
    with urllib.request.urlopen(request) as response:
        print("Different client:", response.status)
except urllib.error.HTTPError as error:
    print("Different client:", error.code)
