# Day 24 - Client timeout and retry experiment.
# The 1-second timeout is intentionally shorter than the API's 3-second delay.
# Reuses the same TransactionId to demonstrate idempotent retries.
# Learning example only, not production retry logic.

import time
import requests

url = "http://localhost:8000/mes/orders/complete"

payload = {
    "order_id": "ORDER100",
    "transaction_id": "TX567",
    "status": "Completed"
}

max_attempts = 4
base_delay = 1

for attempt in range(1, max_attempts + 1):
    try:
        print(f"Attempt {attempt}: Sending TX567")

        response = requests.post(
            url,
            json=payload,
            timeout=1
        )

        response.raise_for_status()

        print(f"Success: HTTP {response.status_code}")
        print(response.json())
        break

    except requests.exceptions.RequestException as ex:
        print(f"Attempt {attempt} failed: {ex}")

        if attempt == max_attempts:
            print("Maximum attempts reached")
            break

        delay = base_delay * (2 ** (attempt - 1))

        print(f"Waiting {delay} seconds before retry...")
        time.sleep(delay)