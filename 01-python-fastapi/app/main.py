from fastapi import FastAPI
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

@app.post("/employees")
def add_employee(employee: Employee):
    print("will be implementing to connect with db and add employee details later")
    # convert into dictionary
    print(employee.model_dump())
    # converts into json foramt
    print(employee.model_dump_json())
    # to view schema
    print(employee.model_json_schema())
    return employee