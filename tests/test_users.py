from helpers import PASSWORD
from server.models import UserRole


def test_list_filters(client, admin, make_actor):
    courier = make_actor(UserRole.COURIER, email="futar@teszt.hu")
    make_actor(UserRole.COURIER, is_active=False)
    make_actor(UserRole.CUSTOMER)

    def ids(**params):
        response = client.get("/users", headers=admin.headers, params=params)
        assert response.status_code == 200
        return {user["id"] for user in response.json()["items"]}

    assert ids(role="courier", is_active=True) == {courier.id}
    assert len(ids(role="courier")) == 2
    assert ids(search="FUTAR@") == {courier.id}


def test_admin_edits_user_and_password(client, admin, make_actor):
    user = make_actor(UserRole.CUSTOMER)
    response = client.patch(f"/users/{user.id}", headers=admin.headers,
                            json={"first_name": "Béla", "role": "courier", "password": "ujjelszo123"})
    assert response.status_code == 200
    assert (response.json()["first_name"], response.json()["role"]) == ("Béla", "courier")
    login = client.post("/auth/login", data={"username": user.email, "password": "ujjelszo123"})
    assert login.status_code == 200 and login.json()["role"] == "courier"


def test_admin_sees_inactive_user(client, admin, make_actor):
    user = make_actor(UserRole.CUSTOMER, is_active=False)
    response = client.get(f"/users/{user.id}", headers=admin.headers)
    assert response.status_code == 200 and response.json()["is_active"] is False
    assert client.get("/users/999", headers=admin.headers).status_code == 404


def test_admin_cannot_lock_himself_out(client, admin):
    for body in ({"is_active": False}, {"role": "customer"}):
        assert client.patch(f"/users/{admin.id}", headers=admin.headers, json=body).status_code == 409
    assert client.delete(f"/users/{admin.id}", headers=admin.headers).status_code == 409
    # Other own fields can change
    assert client.patch(f"/users/{admin.id}", headers=admin.headers, json={"first_name": "Főnök"}).status_code == 200


def test_busy_courier_is_protected(client, flow, book, admin, courier):
    parcel = book()
    flow.pickup_assigned(parcel["id"])
    assert client.delete(f"/users/{courier.id}", headers=admin.headers).status_code == 409
    for body in ({"is_active": False}, {"role": "customer"}):
        assert client.patch(f"/users/{courier.id}", headers=admin.headers, json=body).status_code == 409

    for step in ("picked_up", "in_warehouse", "delivery_assigned", "out_for_delivery", "delivered"):
        getattr(flow, step)(parcel["id"])
    # Nothing open any more
    assert client.delete(f"/users/{courier.id}", headers=admin.headers).status_code == 204


def test_reactivation_checks_the_email(client, admin, make_actor):
    old = make_actor(UserRole.CUSTOMER, email="anna@teszt.hu", is_active=False)
    make_actor(UserRole.CUSTOMER, email="Anna@teszt.hu")
    response = client.patch(f"/users/{old.id}", headers=admin.headers, json={"is_active": True})
    assert response.status_code == 409


def test_profile_email_must_be_free(client, customer, make_actor):
    other = make_actor(UserRole.CUSTOMER)
    response = client.patch("/users/me", headers=customer.headers, json={"email": other.email.upper()})
    assert response.status_code == 409
    own = client.patch("/users/me", headers=customer.headers, json={"email": "uj.cim@teszt.hu"})
    assert own.status_code == 200 and own.json()["email"] == "uj.cim@teszt.hu"
    login = client.post("/auth/login", data={"username": "uj.cim@teszt.hu", "password": PASSWORD})
    assert login.status_code == 200
