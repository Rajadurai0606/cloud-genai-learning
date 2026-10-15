from fastapi import FastAPI
from .routers import employee,health,land
import uvicorn
import os
import logging
from google.cloud.logging_v2.handlers import StructuredLogHandler
from fastapi import FastAPI, HTTPException


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

app = FastAPI(
    title="New Learning API",
)

app.include_router(land.router, prefix="")
app.include_router(health.router, prefix="/health")
app.include_router(employee.router, prefix="/employees", tags=["employees"])

# Day 21 - Temporary endpoint to test Cloud Monitoring 5xx alerts.
# Remove after testing.
@app.get("/test-500")
def test_server_error():
    raise HTTPException(
        status_code=500,
        detail="Intentional error for Cloud Monitoring testing"
    )


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)


        


        