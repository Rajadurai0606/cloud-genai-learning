from fastapi import APIRouter
import os

router = APIRouter()
@router.get("/")
def root():
    return {
    "message": "Employee API",
    "version": os.getenv("APP_VERSION","local"),
    "environment": os.getenv("APP_ENV","local")
}