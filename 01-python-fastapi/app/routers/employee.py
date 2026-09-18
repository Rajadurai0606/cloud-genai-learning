from fastapi import HTTPException, APIRouter,status
from ..models.employee import EmployeeModel, EmployeeBase

router = APIRouter()

## API Endpoints

## root

emp1 = EmployeeModel(id=1,name="Raja",age=37, department="MES")
emp2 = EmployeeModel(id=2,name="Steve",age=47, department="engineering")

employees: list[EmployeeModel] = []

employees.append(emp1)
employees.append(emp2)

def get_employee_or_404(emp_id: int) -> EmployeeModel:
    for emp in employees:
        if emp.id == emp_id:
            return emp
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail=f"Employee Id - {emp_id} not found")

"""
need check if there is a simple way like employees.orderBy(x => x.id)
"""
def get_new_emp_id() -> int:
    max_id: int = 0

    for emp in employees:
        if emp.id > max_id:
            max_id = emp.id

    return max_id + 1

### Create Employee
@router.post("",status_code = status.HTTP_201_CREATED)
def add_employee(employee_base: EmployeeBase):
    print(f"existing length - {len(employees)}")
    new_id = get_new_emp_id()
    employee_model = EmployeeModel(id=new_id,name=employee_base.name,age=employee_base.age,department=employee_base.department)
    employees.append(employee_model)
    return employee_model

#path parameter
### Get Employee by ID
@router.get("/{id}", status_code=status.HTTP_200_OK)
def get_employee(id: int):
     return get_employee_or_404(id)

### Get All Employees
@router.get("")
def get_employees() -> list[EmployeeModel]:
     return employees

@router.put("/{id}", status_code=status.HTTP_200_OK)
def update_employee(id: int, updated_employee: EmployeeBase):
    for index, emp in enumerate(employees):
        if emp.id == id:
            updated_employee_model = EmployeeModel(id=id,name=updated_employee.name,age=updated_employee.age,department=updated_employee.department)
            employees[index] = updated_employee_model
            return updated_employee_model
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,detail=f"Employee Id - {id} not found")

"""
i wanted to use the existing method and update somthing like this but it's not available
def update_employee(id: str, updated_employee: Employee):
    existing_emp = get_employee_or_404(id)
    existing_emp.update(model_dump())
"""

@router.delete("/{id}",status_code=status.HTTP_204_NO_CONTENT)
def delete_employee(id: int):
     existing_emp = get_employee_or_404(id)
     employees.remove(existing_emp)