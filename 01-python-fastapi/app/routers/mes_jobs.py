import asyncio
import logging
from fastapi import HTTPException

from fastapi import APIRouter, BackgroundTasks, status
from pydantic import BaseModel

router = APIRouter(
    prefix="/mes/jobs",
    tags=["MES Jobs"]
)

# Day 25 - Learning-only in-memory job store.
# This is not shared across containers and is lost on restart.
jobs = {}


class JobRequest(BaseModel):
    order_id: str
    transaction_id: str


async def process_job(transaction_id: str):
    jobs[transaction_id]["status"] = "Processing"

    logging.info(f"Processing job: {transaction_id}")

    try:
        # Simulate MES processing.
        await asyncio.sleep(10)

        # Day 25 - Simulate a technical failure for one test transaction.
        if transaction_id == "TX572":
            raise Exception("Simulated MES database failure")

        jobs[transaction_id]["status"] = "Completed"

        logging.info(f"Job completed: {transaction_id}")

    except Exception as ex:
        jobs[transaction_id]["status"] = "Failed"
        jobs[transaction_id]["error"] = str(ex)

        logging.error(
            f"Job failed: {transaction_id}, Error: {ex}"
        )


@router.post("/submit", status_code=status.HTTP_202_ACCEPTED)
async def submit_job(
    request: JobRequest,
    background_tasks: BackgroundTasks
):
    jobs[request.transaction_id] = {
        "order_id": request.order_id,
        "status": "Pending"
    }

    background_tasks.add_task(
        process_job,
        request.transaction_id
    )

    return {
        "transaction_id": request.transaction_id,
        "status": "Accepted",
        "message": "Job accepted for processing"
    }



@router.get("/{transaction_id}")
async def get_job_status(transaction_id: str):

    if transaction_id not in jobs:
        raise HTTPException(
            status_code=404,
            detail="Job not found"
        )

    return {
        "transaction_id": transaction_id,
        "order_id": jobs[transaction_id]["order_id"],
        "status": jobs[transaction_id]["status"]
    }