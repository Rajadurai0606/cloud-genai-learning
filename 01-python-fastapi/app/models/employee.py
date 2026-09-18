from pydantic import BaseModel,Field

"""
should the client also send: id for update?
introduced EmployeeBase which will not expose id for
    adding employee
    updating employee
"""

class EmployeeBase(BaseModel):
    name: str = Field(min_length=3, description="Employee Name")
    age: int = Field(ge=18, description="Employee Age")
    department: str | None = Field(default=None)

class EmployeeModel(EmployeeBase):
    id: int = Field(description="Employee Id")