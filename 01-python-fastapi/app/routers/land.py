from fastapi import APIRouter
import os


api_key = os.getenv("API_KEY")

router = APIRouter()
@router.get("/")
def root():
    return {
    "message": "Employee API",
    "version": os.getenv("APP_VERSION","local"),
    "environment": os.getenv("APP_ENV","local"),
    "api_key_configured": bool(api_key)
}