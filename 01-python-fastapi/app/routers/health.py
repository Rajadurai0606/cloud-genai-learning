from fastapi import APIRouter

router = APIRouter()

@router.get("")
def health_check():
    return{
        "status": "healthy",
        "service": "new-learning-api"
    }