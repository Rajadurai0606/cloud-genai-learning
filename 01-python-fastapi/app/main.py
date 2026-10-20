from fastapi import FastAPI
from .routers import employee,health,land
import uvicorn
import os
import logging
from google.cloud.logging_v2.handlers import StructuredLogHandler
from fastapi import FastAPI, HTTPException
import asyncio
from contextlib import asynccontextmanager


if os.getenv("K_SERVICE"):
    # Cloud Run - write structured JSON logs to stdout.
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(StructuredLogHandler())
else:
    # Local - normal readable console logs.
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(name)s - %(message)s"
    )

# Day 23 - Test application startup and graceful shutdown.
@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.info("Day 23 - Application started")

    yield

    logging.info("Day 23 - Application shutting down")
    logging.info("Day 23 - Application cleanup completed")

app = FastAPI(
    title="New Learning API",
    lifespan=lifespan
)

app.include_router(land.router, prefix="")
app.include_router(health.router, prefix="/health")
app.include_router(employee.router, prefix="/employees", tags=["employees"])


# Day 23 - Temporary endpoint to test Cloud Run request timeout.
# Remove after testing.
@app.get("/test-timeout")
async def test_timeout():
    await asyncio.sleep(25)

    return {
        "status": "completed",
        "message": "Request completed after 25 seconds"
    }


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)


        


        