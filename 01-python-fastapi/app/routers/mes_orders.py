# Day 24 - Idempotency and concurrency learning example.
# Uses in-memory transaction storage and per-transaction asyncio locks.
# The 3-second delay simulates slow database processing.
# This is only for local learning, not production use.
# Multiple Cloud Run instances cannot share these locks or transaction data.

from fastapi import APIRouter
from pydantic import BaseModel
from fastapi import HTTPException
import logging
import asyncio

router = APIRouter(
    prefix="/mes/orders",
    tags=["MES Orders"]
)

# Day 24 - One lock for each TransactionId.
# Different transactions can process in parallel.
# Learning-only: locks are shared only within this Python process.
transaction_locks: dict[str, asyncio.Lock] = {}

# Day 24 - Temporary in-memory store to understand idempotency.
# Each transaction ID represents one logical business operation.
# This is local to one Python process, not shared across containers.
processed_transactions = {}

# Request received from MES Station Service
class OrderCompletionRequest(BaseModel):
    order_id: str
    transaction_id: str
    status: str


@router.post("/complete")
async def complete_order(request: OrderCompletionRequest):

    transaction_id = request.transaction_id
     # Requests with the same TransactionId share one lock.
    lock = transaction_locks.setdefault(
        transaction_id,
        asyncio.Lock()
    )

    logging.info(
        f"TX={transaction_id}, LockId={id(lock)}, "
        f"StoreId={id(processed_transactions)}")

    async with lock:

        # Only one request can enter this section at a time.
        if transaction_id in processed_transactions:

            previous = processed_transactions[transaction_id]

            if previous["order_id"] != request.order_id or \
               previous["status"] != request.status:
                raise HTTPException(
                    status_code=409,
                    detail="Transaction ID already used for a different request"
                )

            logging.info(
                f"Duplicate transaction detected: {transaction_id}"
            )

            return previous

        # Simulate a slow MES database operation.
        await asyncio.sleep(3)

        response = {
            "order_id": request.order_id,
            "transaction_id": transaction_id,
            "status": request.status,
            "message": "Order completed successfully"
        }

        processed_transactions[transaction_id] = response

        logging.info(
            f"Processing new transaction: {transaction_id}"
        )

        return response