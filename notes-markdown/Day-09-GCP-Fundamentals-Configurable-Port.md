# Day 09 - GCP fundamentals and configurable port
Date: 24-Sep-2026

## Concepts in this file
- Projects
- regions
- zones
- Artifact Registry
- Cloud Run
- GKE
- PORT
- os.getenv
- module startup
- --env-file
- port debugging

## ORIGINAL LEARNING NOTES

## Day 9 — GCP Fundamentals and Configurable Application Port

## GCP Basics

- Project: A boundary for organizing cloud resources, permissions and costs. Separate projects can be used for dev, test and production. Organizations and folders can sit above projects.
- Region: A geographical area, such as europe-west2.
- Zone: A deployment area within a region, such as europe-west2-a. A region contains multiple zones.

## Artifact Registry, Cloud Run and GKE

- Artifact Registry stores built container images so deployment services can access them.
- Cloud Run runs containerized applications while Google manages the underlying infrastructure and scaling.
- GKE provides managed Kubernetes for workloads needing Kubernetes features and greater control.
- Choosing Cloud Run or GKE depends on workload and control requirements, not simply application size.

## Our deployment path:

Code → docker build → Image → Artifact Registry → Cloud Run or GKE

## Configuring the Application Port

```python
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port)
```

- os.getenv reads an environment variable.
- If PORT is missing, the application uses 8000.
- Environment-variable values are strings, so int() converts the port to a number.
- 0.0.0.0 makes the server listen on all container network interfaces.
- Environment variables let us configure the same image without changing code or rebuilding.
- Cloud Run supplies PORT; our application must listen on that port.

## Docker Startup Command

```dockerfile
CMD ["python", "-m", "app.main"]
```

- -m runs app.main as a Python module, allowing its relative imports to work.
- Use app.main, without the .py extension.
- The __main__ guard starts Uvicorn only when the module is executed as the entry point.
- When Uvicorn imports app.main, the guarded startup block does not run again.

## Application Port versus Docker Port Mapping

## These are separate settings:

```text
PORT environment variable
    → Our code uses it to choose where Uvicorn listens.
```

```powershell
-p HOST_PORT:CONTAINER_PORT
```
```text
→ Docker forwards host traffic to a container port.
```

The -p option does NOT set the application's listening port.
The container port in the mapping must match where the application listens.

## Test 1 — Default Port

```powershell
docker run --rm -p 8001:8000 im-employee-api-1
```

```text
- No PORT environment variable supplied.
- Python uses the default: 8000.
- Docker forwards host 8001 → container 8000.
- http://localhost:8001/health returned a healthy response.
```

## Test 2 — Overridden Port

## Contents of .env:

```text
PORT=5000
```

## Command:

```powershell
docker run --name cn-employee-api-1 --env-file .env -p 8080:5000 im-employee-api-1
```

```text
- Docker reads .env and supplies PORT=5000 to the container.
- Python reads PORT and starts Uvicorn on 5000.
- Docker forwards host 8080 → container 5000.
- http://localhost:8080/health returned a healthy response.
```

## Lessons from Debugging

- docker run does not automatically load a local .env file. Supply --env-file .env or -e PORT=5000.
- os.getenv reads the process environment; it does not read .env files itself.
- For Docker's --env-file, write PORT=5000 without spaces around the equals sign.
- Changing values supplied through --env-file requires creating a new container, not rebuilding the image.
- Code or Dockerfile changes require rebuilding the image and creating a new container.
- There is no need to delete the old image before rebuilding with the same tag.
- --rm automatically removes the container when it exits; it does not remove the image.

## Recall Questions

1. Why use Artifact Registry?
To make built images available beyond our laptop for deployment.

2. Artifact Registry versus Cloud Run?
Artifact Registry stores images; Cloud Run runs applications from them.

3. Cloud Run versus GKE?
Cloud Run handles infrastructure for us. GKE provides Kubernetes features and more control.

4. Why environment variables?
To change runtime configuration while reusing the same application image.

5. What does -p 8001:8080 mean?
Forward host port 8001 to container port 8080.
The application must already be listening on container port 8080.

Day 9 completed: GCP fundamentals reviewed, configurable PORT implemented,
and default and overridden port tests passed locally.
