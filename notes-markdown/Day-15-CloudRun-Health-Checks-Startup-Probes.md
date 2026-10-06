# Day 15 – Cloud Run Health Checks & Startup Probes

## Goal

Understand how Cloud Run checks whether the FastAPI container has started successfully and is ready to accept traffic.

## 1. Create a health endpoint

We already had health.py under app/routers.

```python
from fastapi import APIRouter

router = APIRouter()

@router.get("")
def health_check():
    return {
        "status": "healthy",
        "service": "new-learning-api"
    }
```

In main.py the router is registered as:

```python
app.include_router(health.router, prefix="/health")
```

So the endpoint is:

`/health`

Local test:

http://localhost:8000/health

Response:

```json
{
  "status": "healthy",
  "service": "new-learning-api"
}
```

This confirmed the application health endpoint was working locally.

## 2. Existing Cloud Run startup probe

Cloud Run already had a startup probe using:

`TCP 8080`

A TCP probe mainly checks:

“Can Cloud Run connect to the container on port 8080?”

It does not call our FastAPI /health endpoint.

## 3. Change the probe to HTTP

We changed the Cloud Run startup probe from TCP to HTTP and configured:

- Probe type: HTTP
- Path: /health
- Port: 8080

Now Cloud Run checks the actual application endpoint.

Conceptually:

```text
Cloud Run starts container
→ calls HTTP /health
→ FastAPI returns HTTP 200
→ Cloud Run considers the application successfully started.
```

## 4. First deployment failed

Our first HTTP startup-probe configuration used:

- Initial delay: 0 seconds
- Period: 240 seconds
- Timeout: 240 seconds
- Failure threshold: 1

The new Cloud Run revision failed.

Logs Explorer showed that the startup HTTP probe failed on port 8080 and path /health with CONNECTION_FAILED.

Important learning:

This was not a 404 or 500 response from /health.

Cloud Run could not connect to the application at the time it performed the startup check.

With initial delay 0 and failure threshold 1, the configuration was too aggressive for this experiment.

## 5. Corrected startup probe

We changed the settings to:

- Probe type: HTTP
- Path: /health
- Port: 8080
- Initial delay: 5 seconds
- Period: 10 seconds
- Timeout: 5 seconds
- Failure threshold: 3

Meaning:

1.  Start the container.
2.  Wait 5 seconds before the first health check.
3.  Call /health.
4.  If it fails, retry every 10 seconds.
5.  Allow up to 3 consecutive failures.

## 6. Deployment succeeded

After changing the startup-probe settings, Cloud Run successfully completed:

- Updating service
- Creating revision
- Routing traffic

This confirmed the new revision became healthy.

## 7. Final verification

We opened the deployed Cloud Run URL with /health.

It returned:

```json
{
  "status": "healthy",
  "service": "new-learning-api"
}
```

So the complete flow worked:

```text
Cloud Run
→ starts container
→ waits for startup delay
→ HTTP GET /health
→ FastAPI responds successfully
→ revision becomes ready
→ traffic is routed to the revision.
```

## Key concepts to remember

### Health endpoint
A lightweight endpoint used to tell the platform that the application is healthy.

### Startup probe
Used during application/container startup to determine whether the application has started successfully.

### TCP probe
Checks whether a connection can be made to the configured port.

### HTTP probe
Calls an HTTP endpoint such as /health. This checks the application more directly than only checking whether the port is open.

### Initial delay
How long Cloud Run waits before performing the first startup probe.

### Period
How often the probe runs.

### Timeout
How long Cloud Run waits for one probe attempt.

### Failure threshold
How many consecutive probe failures are allowed before startup is considered failed.

## Day 15 takeaway

A container process starting is not enough by itself. The platform needs a reliable way to know whether the application inside the container is actually ready.

For our FastAPI application, /health provides that signal.

The failed deployment was useful because it showed how incorrect probe timing can cause a revision to fail even when the application code itself works.
