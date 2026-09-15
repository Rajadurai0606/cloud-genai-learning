from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

app = FastAPI(
    title="New Learning API",
)

class Employee(BaseModel):
    id: str = Field(description="Employee Id")
    name: str = Field(min_length=3, description="Employee Name")
    age: int = Field(ge=18, description="Employee Age")
    department: str | None = Field(default=None)

@app.get("/")
def root():
    return "hello Raja"

@app.get("/health")
def health_check():
    return{
        "status": "healthy",
        "service": "new-learning-api"
    }

employees: list[Employee] = []

def get_employee_or_404(emp_id: str) -> Employee:
    for emp in employees:
        if emp.id == emp_id:
            return emp
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail=f"Employee Id - {emp_id} not found")

@app.post("/employees",status_code = status.HTTP_201_CREATED)
def add_employee(employee: Employee):
    for emp in employees:
            if emp.id == employee.id:
                 raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Employee Id - {employee.id} already exist")
    employees.append(employee)
    return employee

#path parameter
# returns a specific employee
@app.get("/employees/{id}", status_code=status.HTTP_200_OK)
def get_employee(id: str):
     return get_employee_or_404(id)

#returs all employees
@app.get("/employees")
def get_employees() -> list[Employee]:
     return employees


        