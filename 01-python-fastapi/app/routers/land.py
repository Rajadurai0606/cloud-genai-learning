from fastapi import APIRouter
import os
import logging
import socket
import time
import uuid

INSTANCE_ID = str(uuid.uuid4())[:8]

api_key = os.getenv("API_KEY")

logger = logging.getLogger(__name__)


router = APIRouter()
@router.get("/")
def root():
    #logger.info(f"Initial call before delay - instance={INSTANCE_ID}")
    #time.sleep(10) #10 sec delay
    #logger.info(f"Request handled by instance={INSTANCE_ID}")
    logger.info(
        "Landing enpoint called version=%s, environment=%s",
        os.getenv("APP_VERSION","local"),
        os.getenv("APP_ENV","local")
    )

    logger.info("This is an INFO log")
    logger.warning("This is a WARNING log")
    logger.error("This is an ERROR log")

    return {
    "message": "Employee API",
    "version": os.getenv("APP_VERSION","local"),
    "environment": os.getenv("APP_ENV","local"),
    "api_key_configured": bool(api_key)
}

@router.get("/cpu-test")
def cpu_test():
    logger.info("CPU test started")

    total = 0

    for i in range(50_000_000):
        total += i * i

    logger.info("CPU test completed")

    return {
        "message": "CPU test completed",
        "result": total
    }