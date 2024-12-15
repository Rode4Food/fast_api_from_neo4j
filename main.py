import os
from neo4j import GraphDatabase, Transaction
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from contextlib import asynccontextmanager


# Проверка необходимых переменных окружения
required_env_vars = ["DB_URI", "DB_USERNAME", "DB_PASSWORD", "API_TOKEN"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    raise EnvironmentError(f"Не установлены переменные окружения: {', '.join(missing_vars)}")

# Чтение переменных окружения
DB_URI = os.getenv("DB_URI")
DB_USERNAME = os.getenv("DB_USERNAME")
DB_PASSWORD = os.getenv("DB_PASSWORD")
API_TOKEN = os.getenv("API_TOKEN")

# Настройка подключения к Neo4j
class Neo4jQueries:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        """Закрытие соединения с базой данных Neo4j."""
        self.driver.close()

    def get_all_nodes(self):
        """Получение всех узлов из базы данных."""
        query = "MATCH (n) RETURN n.id AS id, labels(n) AS label"
        with self.driver.session() as session:
            result = session.run(query)
            return [{"id": record["id"], "label": record["label"][0]} for record in result]

    def get_node_with_relationships(self, node_id):
        """Получение узла и его связей по ID узла."""
        query = """
        MATCH (n)-[r]-(m)
        WHERE n.id = $id
        RETURN n AS node, r AS relationship, m AS target_node
        """
        with self.driver.session() as session:
            result = session.run(query, id=node_id)
            nodes = [
                {
                    "node": {"id": record["node"].element_id, "label": record["node"].labels, "attributes": dict(record["node"])},
                    "relationship": {"type": record["relationship"].type, "attributes": dict(record["relationship"])},
                    "target_node": {"id": record["target_node"].element_id, "label": record["target_node"].labels, "attributes": dict(record["target_node"])}
                }
                for record in result
            ]
            return nodes

    def add_node_and_relationships(self, label, properties, relationships):
        """Добавление узла и связей в базу данных."""
        with self.driver.session() as session:
            session.execute_write(self._create_node_and_relationships, label, properties, relationships)

    @staticmethod
    def _create_node_and_relationships(tx, label, properties, relationships):
        """Создание узла и связей внутри транзакции."""
        create_node_query = f"CREATE (n:{label} $properties) RETURN n"
        node = tx.run(create_node_query, properties=properties).single()["n"]
        node_id = node.element_id

        for relationship in relationships:
            tx.run("""
                MATCH (n), (m)
                WHERE n.id = $node_id AND m.id = $target_id
                CREATE (n)-[r:RELATIONSHIP_TYPE]->(m)
                SET r = $relationship_attributes
            """, node_id=node_id, target_id=relationship['target_id'], relationship_attributes=relationship['attributes'])

    def delete_node(self, node_id):
        """Удаление узла и его связей по ID."""
        with self.driver.session() as session:
            session.execute_write(self._delete_node, node_id)

    @staticmethod
    def _delete_node(tx, node_id):
        """Удаление узла и его связей внутри транзакции."""
        tx.run("MATCH (n) WHERE n.id = $id DETACH DELETE n", id=node_id)

# Создание FastAPI приложения
app = FastAPI()

# Модель данных для узла
class Node(BaseModel):
    label: str
    properties: dict
    relationships: list

# OAuth2 токен для авторизации
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Функция проверки токена
def get_current_token(token: str = Depends(oauth2_scheme)):
    print(f"Получен токен: {token}")  # Логирование токена
    if token != API_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )
    return token

# Точки доступа для взаимодействия с базой данных Neo4j
@app.get("/nodes")
async def get_all_nodes():
    db = Neo4jQueries(DB_URI, DB_USERNAME, DB_PASSWORD)
    nodes = db.get_all_nodes()
    db.close()
    return nodes

@app.get("/nodes/{id}")
async def get_node(id: int):
    db = Neo4jQueries(DB_URI, DB_USERNAME, DB_PASSWORD)
    node = db.get_node_with_relationships(id)
    db.close()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node

@app.post("/nodes", dependencies=[Depends(get_current_token)])
async def add_node(node: Node):
    db = Neo4jQueries(DB_URI, DB_USERNAME, DB_PASSWORD)
    db.add_node_and_relationships(node.label, node.properties, node.relationships)
    db.close()
    return {"message": "Node and relationships added successfully"}

@app.delete("/nodes/{id}", dependencies=[Depends(get_current_token)])
async def delete_node(id: int):
    db = Neo4jQueries(DB_URI, DB_USERNAME, DB_PASSWORD)
    db.delete_node(id)
    db.close()
    return {"message": "Node and relationships deleted successfully"}