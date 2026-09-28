from fastapi import APIRouter

router = APIRouter()
@router.get("/")
def root():
    return {
    "message": "Employee API",
    "version": "2.0"
}