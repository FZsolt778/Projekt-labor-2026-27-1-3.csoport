import os

# GUI tests without a window
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  

from itertools import count

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from helpers import PASSWORD, WAREHOUSE_CAPACITY, Actor, Flow, parcel_body
from server.main import app
from server.models import User, UserRole, Warehouse
from server.src.database import Base, get_db
from server.src.sec import create_access_token, hash_pass

PASSWORD_HASH = hash_pass(PASSWORD)  


@pytest.fixture
def db():
    # clean memory database for every test
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP INDEX uq_users_email"))
        conn.execute(text("CREATE UNIQUE INDEX uq_users_email ON users (lower(email)) WHERE is_active = 1"))
    session = sessionmaker(bind=engine, autoflush=False)()
    session.add(Warehouse(name="Teszt raktár", capacity=WAREHOUSE_CAPACITY))
    session.commit()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(db):
    # The API uses the test database instead of PostgreSQL
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def make_actor(db):
    numbers = count(1)

    def _make(role: UserRole = UserRole.CUSTOMER, email: str | None = None, **fields) -> Actor:
        n = next(numbers)
        user = User(last_name="Teszt", first_name=f"{role.value}{n}",
                    email=email or f"{role.value}{n}@teszt.hu",
                    password_hash=PASSWORD_HASH, role=role, **fields)
        db.add(user)
        db.commit()
        return Actor(user, {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"})
    return _make


@pytest.fixture
def customer(make_actor) -> Actor:
    return make_actor(UserRole.CUSTOMER)


@pytest.fixture
def courier(make_actor) -> Actor:
    return make_actor(UserRole.COURIER)


@pytest.fixture
def logistician(make_actor) -> Actor:
    return make_actor(UserRole.LOGISTICIAN)


@pytest.fixture
def admin(make_actor) -> Actor:
    return make_actor(UserRole.ADMIN)


@pytest.fixture
def book(client):
    # Books a parcel (when guest, actor is None)
    def _book(actor: Actor | None = None, **kwargs) -> dict:
        response = client.post("/parcels", json=parcel_body(**kwargs),
                               headers=actor.headers if actor else None)
        assert response.status_code == 201, response.text
        return response.json()
    return _book


@pytest.fixture
def flow(client, logistician, courier) -> Flow:
    return Flow(client, logistician, courier)


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication
    return QApplication.instance() or QApplication([])
