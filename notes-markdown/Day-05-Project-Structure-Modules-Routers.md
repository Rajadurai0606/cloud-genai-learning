# Day 05 - Project structure modules and routers
Date: 17-Sep-2026

## Concepts in this file
- Modules
- packages
- __init__.py
- relative imports
- import errors
- APIRouter
- Uvicorn module path

## ORIGINAL LEARNING NOTES

## Day 5 - Refactor FastAPI Project Structure

Goal:
Split the single main.py application into separate modules/packages
without changing the existing API behaviour.

## Python Module

A Python .py file is called a module.

Examples:
main.py
employee.py
health.py

## Python Package

A package is used to organize related Python modules into directories.

Current structure:

app/
main.py

models/
__init__.py
employee.py

routers/
__init__.py
employee.py
health.py
land.py

## __init__.py

__init__.py is the package initialization file.

For the current project, keep __init__.py empty.

It can later be used for package initialization or to expose
selected objects from the package, but this is not required now.

Modern Python also supports some packages without __init__.py,
but we do not need that concept for the current project.

## Relative Imports

. means current package.

Example from app/main.py:

from .routers import employee, health, land

main.py is inside the app package.

Therefore .routers means:
app -> routers

.. means go to the parent package.

Example from app/routers/employee.py:

from ..models.employee import EmployeeModel, EmployeeBase

employee.py is inside:
app -> routers

.. moves back to:
app

then models.employee points to:
app -> models -> employee.py

## Import Error Learned

Initially __init__.py contained:

```python
from employee import *
```

Python tried to find a top-level module named employee and raised:

ModuleNotFoundError: No module named 'employee'

The wildcard imports were not required, so __init__.py files
were left empty.

## APIRouter

Employee endpoints were moved out of main.py into an employee router.

APIRouter groups related API endpoints.

main.py registers the routers using:

```python
app.include_router(...)
```

This keeps main.py focused on creating/configuring the FastAPI
application rather than containing all endpoint implementations.

## Uvicorn Command

```powershell
uvicorn app.main:app --reload
```

Meaning:

app       -> Python package
main      -> main.py module
app       -> FastAPI object created inside main.py
--reload  -> restart development server when code changes

## Result

FastAPI application is now separated into:
- application startup/configuration
- routers/endpoints
- Pydantic models

Existing CRUD API behaviour still works after refactoring.
