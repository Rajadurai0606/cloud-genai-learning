from app.main import app
from fastapi.testclient import TestClient

#pass the app which is FastAPI
client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200

def test_create_employee():
    json = {"name": "David","age": 30, "department" : "Controls"}
    response = client.post("/employees",json=json)
    assert response.status_code == 201
    #print(response.json())
    data = response.json()
    assert data["name"] == "David"
    assert data["age"] == 30
    assert data["department"] == "Controls"
    assert "id" in data

def test_read_employees():
    response = client.get("/employees")
    assert response.status_code == 200 
    assert isinstance(response.json(), list)
    #just checking if returned as a list

def test_read_employee():
    json = {"name": "Mathew","age": 45, "department" : "Controls"}
    post_response = client.post("/employees", json=json)
    created_data = post_response.json()
    assert post_response.status_code == 201
    get_response = client.get(f"/employees/{created_data["id"]}")
    get_data = get_response.json()
    assert get_response.status_code == 200
    assert get_data["name"] == "Mathew"
    assert get_data["age"] == 45
    assert get_data["department"] == "Controls"

def test_employee_not_found():
    response = client.get("/employees/9999")
    assert response.status_code == 404
    print(response.json())  

def test_delete_employee():
    json = {"name": "Tim","age": 40, "department" : "Controls"}
    post_response = client.post("/employees", json=json)
    assert post_response.status_code == 201
    data = post_response.json()
    response = client.delete(f"/employees/{data["id"]}")
    assert response.status_code == 204
    get_response = client.get(f"/employees/{data["id"]}")
    assert get_response.status_code == 404
    #print(response)
    