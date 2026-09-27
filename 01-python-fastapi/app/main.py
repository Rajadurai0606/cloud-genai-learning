from fastapi import FastAPI
from .routers import employee,health,land
import uvicorn
import os

print("hello")

app = FastAPI(
    title="New Learning API",
)

app.include_router(land.router, prefix="")
app.include_router(health.router, prefix="/health")
app.include_router(employee.router, prefix="/employees", tags=["employees"])

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)


        


        