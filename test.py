import os
import pytest
from fastapi.testclient import TestClient
from main import app

# Тестовый клиент для FastAPI
client = TestClient(app)

# Токен авторизации
VALID_TOKEN = os.getenv("API_TOKEN", "your_api_token_here")
INVALID_TOKEN = "INVALID_TOKEN"

# Тест: получение всех узлов
def test_get_all_nodes():
    response = client.get("/nodes", headers={"Authorization": f"Bearer {VALID_TOKEN}"})
    assert response.status_code == 200, "Ожидается статус 200"
    assert isinstance(response.json(), list), "Ответ должен быть списком узлов"

def test_get_node_with_relationships():
    node_id = 1  # Убедитесь, что у вас есть узел с таким ID
    response = client.get(f"/nodes/{node_id}", headers={"Authorization": f"Bearer {VALID_TOKEN}"})
    if response.status_code == 404:
        print(f"Узел с ID {node_id} не найден. Проверьте тестовые данные.")
    else:
        assert response.status_code == 200, "Ожидается статус 200"
        assert "node" in response.json()[0], "Ответ должен содержать данные узла"

def test_add_node():
    node_data = {
        "label": "TestNode",
        "properties": {"id": 2, "name": "New Test Node"},
        "relationships": [{"target_id": 1, "attributes": {"type": "linked"}}],
    }
    response = client.post("/nodes", json=node_data, headers={"Authorization": f"Bearer {VALID_TOKEN}"})
    assert response.status_code == 200, "Ожидается статус 200"
    assert response.json() == {"message": "Node and relationships added successfully"}

def test_delete_node():
    node_id = 2  # ID узла, который был добавлен в тесте test_add_node
    response = client.delete(f"/nodes/{node_id}", headers={"Authorization": f"Bearer {VALID_TOKEN}"})
    assert response.status_code == 200, "Ожидается статус 200"
    assert response.json() == {"message": "Node and relationships deleted successfully"}

    # Проверим, что узел действительно удален
    response = client.get(f"/nodes/{node_id}", headers={"Authorization": f"Bearer {VALID_TOKEN}"})
    assert response.status_code == 404, "Удаленный узел не должен существовать"

