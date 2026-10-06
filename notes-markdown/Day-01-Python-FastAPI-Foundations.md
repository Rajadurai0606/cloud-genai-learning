# Day 01 - Python and FastAPI foundations
Date: Not recorded in the source

## Concepts in this file
- venv
- pip
- requirements.txt
- Python functions and type hints
- classes
- FastAPI routes
- Uvicorn
- Swagger

The opening undated section is filed as Day 1 because the next section
is explicitly Day 2. No date has been assumed.

## ORIGINAL LEARNING NOTES

## venv

venv = Python virtual environment.

It creates an isolated environment for a project so different projects
can use different package versions without interfering with each other.

## Example:

Project A -> FastAPI version X
Project B -> FastAPI version Y

## Create virtual environment:

```powershell
py -m venv .venv
```

## Activate it in PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

## pip

pip is Python's package installer.

## Example:

```powershell
pip install fastapi[standard]
```

## To save the packages currently installed in the project:

```powershell
pip freeze > requirements.txt
```

## Another developer can then install the same packages using:

```powershell
pip install -r requirements.txt
```

## Python function syntax

```python
def get_message(name: str) -> str:
    return f"Hello {name}"
```

## Python                          C#

## def                             method/function declaration

## name: str                       string name

```text
-> str                          return type hint: string
```

f"Hello {name}"                 $"Hello {name}"

## :                               starts the function/class block

## Indentation                     defines the code block

## Other examples:

```python
def get_age(age: int) -> int:

def get_salary(salary: float) -> float:
```

## Class

```python
class Employee:
    def __init__(self, id: str, name: str, age: int, salary: float):
        self.id = id
        self.name = name
        self.age = age
        self.salary = salary
```

__init__ is similar to a constructor in C#.

self is similar to "this" in C#.

## Create an object:

```python
employee = Employee(
    "EMP001",
    "Raja",
    37,
    50000.0
)
```

## Return an Employee object:

```python
def get_employee(empid: str) -> Employee:
    employee = Employee(
        empid,
        "Raja",
        37,
        50000.0
    )

    return employee
```

## FastAPI

FastAPI is a Python framework used to build REST APIs.

## Create the application:

```python
from fastapi import FastAPI

app = FastAPI()
```

We define routes/endpoints and the function below the route contains
the logic that handles the request.

## Example:

```python
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "new-learning-api"
    }

@app.get("/health")
```

## means:

When an HTTP GET request comes to /health,
FastAPI should execute the function below it.

## Uvicorn

Uvicorn is the web server that runs the FastAPI application.

## Simple mental model:

```text
Client / Browser
       |
       v
    Uvicorn
       |
       v
    FastAPI
       |
       v
Endpoint / Python function
```

## Swagger / docs

FastAPI automatically generates API documentation.

## Run the application and open:

http://127.0.0.1:8000/docs

## Swagger UI allows us to:

- see available API endpoints
- see HTTP methods such as GET
- execute/test the API
- see request and response details
