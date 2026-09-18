from fastapi import FastAPI
from .routers import employee,health,land

print("hello")

app = FastAPI(
    title="New Learning API",
)

app.include_router(land.router, prefix="")
app.include_router(health.router, prefix="/health")
app.include_router(employee.router, prefix="/employees", tags=["employees"])


        


        