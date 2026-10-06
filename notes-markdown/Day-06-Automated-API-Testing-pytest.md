# Day 06 - Automated API testing with pytest
Date: 19-Sep-2026

## Concepts in this file
- pytest
- TestClient
- HTTPX
- Arrange Act Assert
- generated IDs in tests
- response assertions
- test isolation limitation

## ORIGINAL LEARNING NOTES

## Day 6 - Automated API Testing with pytest

```powershell
pytest
```
Python testing framework used to automatically discover and run tests.

Naming convention:
Test files   -> test_*.py
Test methods -> test_*

Run tests from project root:
```powershell
py -m pytest -v
```

-m -> run pytest as a Python module
-v -> verbose output showing individual test results

FastAPI TestClient
TestClient is used as a client to invoke our FastAPI endpoints
during automated testing.

We pass our FastAPI app to TestClient.

It allows tests to call GET, POST, PUT, DELETE etc. without
manually starting Uvicorn.

Normal execution:
Browser/Swagger -> Uvicorn -> FastAPI -> Endpoint

Automated test:
```powershell
pytest -> TestClient -> FastAPI -> Endpoint
```

TestClient communicates with the FastAPI ASGI application
directly inside the test process. It does not require a real
Uvicorn server/network connection.

HTTPX
HTTPX is a Python HTTP client library.

FastAPI/Starlette TestClient is based on HTTPX, which provides
the underlying HTTP client functionality.

Simple understanding:
Uvicorn    -> Server
HTTPX      -> HTTP client library
TestClient -> Client used to test our FastAPI application

HTTPX and HTTP/2 are different:
HTTPX  -> Python library
HTTP/2 -> Version of HTTP protocol

HTTP/2 is not required for our current learning.

Basic Test Approach
Arrange -> prepare test data
Act     -> invoke API
Assert  -> verify expected result

```text
What we tested
    GET /health
        -> 200
```

```text
POST /employees
    -> 201
    -> validate returned employee fields
    -> verify generated ID exists
```

```text
GET /employees
    -> 200
    -> verify response is a list
```

```text
GET /employees/{id}
    -> create employee
    -> capture generated ID
    -> retrieve same employee
    -> verify returned data
```

```text
GET unknown employee
    -> 404
```

```text
DELETE /employees/{id}
    -> create employee
    -> capture generated ID
    -> delete employee
    -> 204
    -> GET same employee -> 404
```

## Important Testing Learnings

1. Do not hard-code generated IDs in tests.
Capture the ID returned by POST and use it for later requests.

2. Tests should create/control the data they depend on rather than
assuming an employee already exists.

3. Do not validate only the HTTP status code when behaviour also
matters.

Example:
DELETE -> 204
GET same employee -> 404

This confirms the employee was actually deleted.

4. Automated tests give repeatable verification and reduce the need
to manually test every scenario through Swagger.

Current Limitation
Tests currently share the application's in-memory employee data,
so tests can potentially affect each other.

Test isolation and pytest fixtures will be learned later when needed.
