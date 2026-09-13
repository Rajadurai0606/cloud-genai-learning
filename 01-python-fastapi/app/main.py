from fastapi import FastAPI

app = FastAPI(
    title="New Learning API",
)

@app.get("/")
def root():
    return "hello Raja"

@app.get("/health")
def health_check():
    return{
        "status": "healthy",
        "service": "new-learning-api"
    }