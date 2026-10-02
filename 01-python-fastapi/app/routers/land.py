from fastapi import APIRouter
import os
import logging

api_key = os.getenv("API_KEY")

logger = logging.getLogger(__name__)

router = APIRouter()
@router.get("/")
def root():
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