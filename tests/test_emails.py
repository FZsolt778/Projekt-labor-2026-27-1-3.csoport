import asyncio
from datetime import date, time
from unittest.mock import AsyncMock, patch
import pytest
from server.email.client import get_fastmail, send_templated_email
from server.email.schemas import ParcelEmailSnapshot, UserEmailSnapshot
from server.models import Contact, Parcel, ParcelSize, ParcelStatus, User, UserRole
from server.src.config import ENV_CONFIG, settings


def _body_text(msg) -> str:
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            payload = part.get_payload(decode=True)
            if payload is not None:
                parts.append(payload.decode("utf-8", errors="replace"))
        return "\n".join(parts)
    payload = msg.get_payload(decode=True)
    if payload is not None:
        return payload.decode("utf-8", errors="replace")
    return str(msg.get_payload())


def test_smtp_config_defaults():
    cfg = ENV_CONFIG(
        _env_file=None,
        POSTGRES_USER="u",
        POSTGRES_PASSWORD="p",
        POSTGRES_DB="d",
        POSTGRES_HOST="localhost",
        POSTGRES_PORT=5432,
        DATABASE_URL="sqlite://",
        JWT_SECRET="secret",
        JWT_ALGORITHM="HS256",
        JWT_EXPIRE_MINUTES=30,
    )
    assert cfg.SMTP_ENABLED is False
    assert cfg.SMTP_HOST == "localhost"
    assert cfg.SMTP_PORT == 1025
    assert cfg.SMTP_FROM == "noreply@projektlabor.hu"
    assert cfg.SMTP_FROM_NAME == "ProjektLabor Futárszolgálat"
    assert cfg.SMTP_STARTTLS is False
    assert cfg.SMTP_SSL_TLS is False
    assert cfg.SMTP_USE_CREDENTIALS is False
    assert hasattr(settings, "SMTP_ENABLED")


def test_parcel_snapshot_detaches_from_orm():
    sender = Contact(
        last_name="Kovács", first_name="Anna", email="anna@teszt.hu",
        phone="+36301112233", postal_code="8200", city="Veszprém", street="Fő utca", house_number="1",
    )
    recipient = Contact(
        last_name="Nagy", first_name="Béla", email="bela@teszt.hu",
        phone=None, postal_code="1111", city="Budapest", street="Budafoki út", house_number="2",
    )
    parcel = Parcel(
        tracking_number="FC1234567890",
        size=ParcelSize.M,
        status=ParcelStatus.BOOKED,
        sender=sender,
        recipient=recipient,
        pickup_date=date(2026, 11, 20),
        pickup_window_start=time(8, 0),
        pickup_window_end=time(10, 0),
    )
    snap = ParcelEmailSnapshot.from_parcel(parcel)
    assert snap.tracking_number == "FC1234567890"
    assert snap.sender.email == "anna@teszt.hu"
    assert snap.recipient.full_name == "Nagy Béla"
    assert snap.pickup_window == "2026-11-20 08:00–10:00"
    assert snap.delivery_window is None

    user = User(
        last_name="Teszt", first_name="Elek", email="elek@teszt.hu",
        password_hash="x", role=UserRole.CUSTOMER,
    )
    usnap = UserEmailSnapshot.from_user(user)
    assert usnap.email == "elek@teszt.hu"
    assert usnap.full_name == "Teszt Elek"


def test_send_templated_email_records_and_swallows_errors(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_ENABLED", True)
    fm = get_fastmail(force_reload=True)
    fm.config.SUPPRESS_SEND = 1
    with fm.record_messages() as outbox:
        asyncio.run(
            send_templated_email(
                recipients=["teszt@teszt.hu", "TESZT@teszt.hu"],
                subject="Teszt tárgy",
                template_name="account_event.html",
                context={"title": "Üdv", "recipient_name": "Teszt Elek", "lead": "Sikeres teszt.", "details": []},
            )
        )
    assert len(outbox) == 1
    assert outbox[0]["Subject"] == "Teszt tárgy"
    assert "teszt@teszt.hu" in outbox[0]["To"]
    assert outbox[0]["To"].count("@") == 1
    assert "Sikeres teszt." in _body_text(outbox[0])

    with patch.object(fm, "send_message", new=AsyncMock(side_effect=RuntimeError("SMTP down"))):
        asyncio.run(
            send_templated_email(
                recipients=["teszt@teszt.hu"],
                subject="Hiba teszt",
                template_name="account_event.html",
                context={"title": "Üdv", "recipient_name": "Teszt Elek", "lead": "Szöveg", "details": []},
            )
        )


def _sample_parcel(*, same_email: bool = False, with_delivery: bool = True) -> Parcel:
    sender = Contact(
        last_name="Kovács", first_name="Anna", email="anna@teszt.hu",
        phone="+36301112233", postal_code="8200", city="Veszprém", street="Fő utca", house_number="1",
    )
    recipient = Contact(
        last_name="Nagy", first_name="Béla",
        email="anna@teszt.hu" if same_email else "bela@teszt.hu",
        phone=None, postal_code="1111", city="Budapest", street="Budafoki út", house_number="2",
    )
    return Parcel(
        tracking_number="FC9988776655",
        size=ParcelSize.L,
        status=ParcelStatus.BOOKED,
        sender=sender,
        recipient=recipient,
        pickup_date=date(2026, 11, 20),
        pickup_window_start=time(8, 0),
        pickup_window_end=time(10, 0),
        delivery_date=date(2026, 11, 21) if with_delivery else None,
        delivery_window_start=time(12, 0) if with_delivery else None,
        delivery_window_end=time(14, 0) if with_delivery else None,
    )


def test_notify_dispatchers_routing_and_none_bg(monkeypatch):
    from fastapi import BackgroundTasks
    from server.email.notifications import (
        notify_delivery_assigned,
        notify_parcel_booked,
        notify_parcel_in_warehouse,
        notify_parcel_schedule_updated,
        notify_pickup_assigned,
        notify_registered,
    )

    user = User(
        last_name="Teszt", first_name="Elek", email="elek@teszt.hu",
        password_hash="x", role=UserRole.CUSTOMER,
    )
    # None BackgroundTasks must be a safe no-op
    notify_registered(None, user)

    monkeypatch.setattr(settings, "SMTP_ENABLED", True)
    fm = get_fastmail(force_reload=True)
    fm.config.SUPPRESS_SEND = 1

    # Same sender/recipient email -> deduplicated to 1 recipient
    with fm.record_messages() as outbox:
        bg = BackgroundTasks()
        notify_parcel_booked(bg, _sample_parcel(same_email=True, with_delivery=False))
        asyncio.run(bg())
    assert len(outbox) == 1
    assert outbox[0]["To"].count("@") == 1
    assert "FC9988776655" in _body_text(outbox[0])

    # Pickup assigned -> sender only
    with fm.record_messages() as outbox:
        bg = BackgroundTasks()
        notify_pickup_assigned(bg, _sample_parcel(with_delivery=False))
        asyncio.run(bg())
    assert len(outbox) == 1
    assert "anna@teszt.hu" in outbox[0]["To"]
    assert "bela@teszt.hu" not in outbox[0]["To"]

    # Delivery assigned -> 2 separate personalized emails (sender & recipient)
    with fm.record_messages() as outbox:
        bg = BackgroundTasks()
        notify_delivery_assigned(bg, _sample_parcel(with_delivery=True))
        asyncio.run(bg())
    assert len(outbox) == 2
    assert "anna@teszt.hu" in outbox[0]["To"]
    assert "Kedves Kovács Anna!" in _body_text(outbox[0])
    assert "bela@teszt.hu" in outbox[1]["To"]
    assert "Kedves Nagy Béla!" in _body_text(outbox[1])
    assert "2026-11-21 12:00–14:00" in _body_text(outbox[1])

    # Schedule updated with cleared delivery_date -> 2 separate emails, renders "egyeztetés alatt"
    with fm.record_messages() as outbox:
        bg = BackgroundTasks()
        notify_parcel_schedule_updated(bg, _sample_parcel(with_delivery=False))
        asyncio.run(bg())
    assert len(outbox) == 2
    assert "egyeztetés alatt" in _body_text(outbox[0])
    assert "egyeztetés alatt" in _body_text(outbox[1])

    # Warehouse initial vs returned after failure -> distinct copy per recipient
    with fm.record_messages() as outbox:
        bg = BackgroundTasks()
        notify_parcel_in_warehouse(bg, _sample_parcel(), returned_after_failure=False)
        notify_parcel_in_warehouse(bg, _sample_parcel(), returned_after_failure=True)
        asyncio.run(bg())
    assert len(outbox) == 4
    assert _body_text(outbox[0]) != _body_text(outbox[2])
    assert _body_text(outbox[1]) != _body_text(outbox[3])


@pytest.fixture
def outbox(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_ENABLED", True)
    fm = get_fastmail(force_reload=True)
    fm.config.SUPPRESS_SEND = 1
    with fm.record_messages() as messages:
        yield messages


def test_email_register(client, outbox):
    res = client.post(
        "/auth/register",
        json={
            "last_name": "Kovács",
            "first_name": "László",
            "email": "laszlo@teszt.hu",
            "password": "jelszo1234",
        },
    )
    assert res.status_code == 201, res.text
    assert len(outbox) == 1
    assert "laszlo@teszt.hu" in outbox[0]["To"]
    assert "regisztráció" in outbox[0]["Subject"].lower()


def test_email_change_password(client, customer, outbox):
    from helpers import PASSWORD

    bad = client.post(
        "/auth/change-password",
        headers=customer.headers,
        json={"current_password": "rossz", "new_password": "ujjelszo123"},
    )
    assert bad.status_code == 400
    assert len(outbox) == 0

    ok = client.post(
        "/auth/change-password",
        headers=customer.headers,
        json={"current_password": PASSWORD, "new_password": "ujjelszo123"},
    )
    assert ok.status_code == 204
    assert len(outbox) == 1
    assert customer.email in outbox[0]["To"]
    assert "jelszó" in outbox[0]["Subject"].lower()


def test_email_update_me_email_change_only(client, customer, outbox):
    old_email = customer.email
    res_name = client.patch(
        "/users/me",
        headers=customer.headers,
        json={"first_name": "Módosított"},
    )
    assert res_name.status_code == 200
    assert len(outbox) == 0

    res_email = client.patch(
        "/users/me",
        headers=customer.headers,
        json={"email": "ujemail@teszt.hu"},
    )
    assert res_email.status_code == 200
    assert len(outbox) == 1
    assert old_email in outbox[0]["To"]
    assert "ujemail@teszt.hu" in outbox[0]["To"]
    assert "email" in outbox[0]["Subject"].lower()


def test_email_parcel_booked_guest_and_customer(client, customer, book, outbox):
    from helpers import parcel_body

    guest_res = client.post("/parcels", json=parcel_body())
    assert guest_res.status_code == 201
    cust_parcel = book(customer, sender_email=customer.email, recipient_email="cimzett2@teszt.hu")

    assert len(outbox) == 4
    assert guest_res.json()["tracking_number"] in outbox[0]["Subject"]
    assert "felado@teszt.hu" in outbox[0]["To"]
    assert "cimzett@teszt.hu" not in outbox[0]["To"]
    assert "Kedves Minta Feladó!" in _body_text(outbox[0])
    assert "cimzett@teszt.hu" in outbox[1]["To"]
    assert "Kedves Minta Címzett!" in _body_text(outbox[1])
    assert cust_parcel["tracking_number"] in outbox[2]["Subject"]
    assert customer.email in outbox[2]["To"]
    assert "cimzett2@teszt.hu" in outbox[3]["To"]


def test_email_customer_update_parcel(client, customer, book, outbox):
    from helpers import day

    parcel = book(customer, sender_email=customer.email, recipient_email="cimzett@teszt.hu")
    outbox.clear()

    # Size-only or phone-only change -> 0 emails
    res_size = client.patch(f"/parcels/my/{parcel['id']}", headers=customer.headers, json={"size": "L"})
    assert res_size.status_code == 200
    res_phone = client.patch(
        f"/parcels/my/{parcel['id']}", headers=customer.headers, json={"sender": {"phone": "+36301234567"}}
    )
    assert res_phone.status_code == 200
    assert len(outbox) == 0

    # Pickup date change -> 2 separate emails (sender & recipient)
    res_time = client.patch(
        f"/parcels/my/{parcel['id']}", headers=customer.headers, json={"pickup_date": day(4)}
    )
    assert res_time.status_code == 200
    assert len(outbox) == 2
    assert customer.email in outbox[0]["To"]
    assert "cimzett@teszt.hu" in outbox[1]["To"]


def test_email_admin_update_parcel(client, admin, customer, book, outbox):
    from helpers import day

    parcel = book(customer, sender_email=customer.email, recipient_email="cimzett@teszt.hu")
    outbox.clear()

    # Non-time edit -> 0 emails
    assert client.patch(f"/parcels/{parcel['id']}", headers=admin.headers, json={"size": "XL"}).status_code == 200
    assert len(outbox) == 0

    # Pickup date change -> sender only
    assert (
        client.patch(
            f"/parcels/{parcel['id']}", headers=admin.headers, json={"pickup_date": day(3)}
        ).status_code
        == 200
    )
    assert len(outbox) == 1
    assert customer.email in outbox[0]["To"]
    assert "cimzett@teszt.hu" not in outbox[0]["To"]
    outbox.clear()

    # Set delivery date/slot -> 2 separate emails (sender & recipient)
    assert (
        client.patch(
            f"/parcels/{parcel['id']}",
            headers=admin.headers,
            json={"delivery_date": day(5), "delivery_slot": "14:00-16:00"},
        ).status_code
        == 200
    )
    assert len(outbox) == 2
    assert customer.email in outbox[0]["To"]
    assert "cimzett@teszt.hu" in outbox[1]["To"]
    outbox.clear()

    # Clear delivery date/slot to None -> "egyeztetés alatt" without error
    assert (
        client.patch(
            f"/parcels/{parcel['id']}",
            headers=admin.headers,
            json={"delivery_date": None, "delivery_slot": None},
        ).status_code
        == 200
    )
    assert len(outbox) == 2
    assert "egyeztetés alatt" in _body_text(outbox[0])
    assert "egyeztetés alatt" in _body_text(outbox[1])


def test_email_admin_set_couriers(client, admin, courier, make_actor, customer, book, flow, outbox):
    from helpers import day

    courier2 = make_actor(UserRole.COURIER)
    parcel = book(customer, sender_email=customer.email, recipient_email="cimzett@teszt.hu")
    outbox.clear()

    # BOOKED -> PICKUP_ASSIGNED sends #2 to sender
    assert (
        client.patch(
            f"/parcels/{parcel['id']}/couriers",
            headers=admin.headers,
            json={"pickup_courier_id": courier.id},
        ).status_code
        == 200
    )
    assert len(outbox) == 1
    assert customer.email in outbox[0]["To"]
    assert "cimzett@teszt.hu" not in outbox[0]["To"]
    outbox.clear()

    # Courier swap or unassign -> 0 emails
    assert (
        client.patch(
            f"/parcels/{parcel['id']}/couriers",
            headers=admin.headers,
            json={"pickup_courier_id": courier2.id},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/parcels/{parcel['id']}/couriers",
            headers=admin.headers,
            json={"pickup_courier_id": None},
        ).status_code
        == 200
    )
    assert len(outbox) == 0

    # Move parcel to IN_WAREHOUSE and set delivery date via admin
    flow.to(parcel["id"], "in_warehouse")
    assert (
        client.patch(
            f"/parcels/{parcel['id']}",
            headers=admin.headers,
            json={"delivery_date": day(4), "delivery_slot": "10:00-12:00"},
        ).status_code
        == 200
    )
    outbox.clear()

    # IN_WAREHOUSE -> DELIVERY_ASSIGNED sends #5 separately to sender & recipient
    assert (
        client.patch(
            f"/parcels/{parcel['id']}/couriers",
            headers=admin.headers,
            json={"delivery_courier_id": courier.id},
        ).status_code
        == 200
    )
    assert len(outbox) == 2
    assert customer.email in outbox[0]["To"]
    assert "cimzett@teszt.hu" in outbox[1]["To"]


def test_email_parcel_cancelled(client, admin, customer, book, outbox):
    p1 = book(customer, sender_email=customer.email, recipient_email="c1@teszt.hu")
    p2 = book(customer, sender_email=customer.email, recipient_email="c2@teszt.hu")
    outbox.clear()

    assert client.post(f"/parcels/my/{p1['id']}/cancel", headers=customer.headers).status_code == 200
    assert client.post(f"/parcels/{p2['id']}/cancel", headers=admin.headers).status_code == 200
    assert len(outbox) == 4
    assert customer.email in outbox[0]["To"]
    assert "c1@teszt.hu" in outbox[1]["To"]
    assert "lemondva" in outbox[1]["Subject"].lower()
    assert customer.email in outbox[2]["To"]
    assert "c2@teszt.hu" in outbox[3]["To"]
    assert "lemondva" in outbox[3]["Subject"].lower()


def test_email_full_happy_path_lifecycle(customer, book, flow, outbox):
    parcel = book(customer, sender_email=customer.email, recipient_email="cimzett@teszt.hu")
    pid = parcel["id"]
    outbox.clear()

    flow.pickup_assigned(pid)
    assert len(outbox) == 1
    assert customer.email in outbox[0]["To"]
    assert "cimzett@teszt.hu" not in outbox[0]["To"]

    flow.picked_up(pid)
    assert len(outbox) == 3
    assert customer.email in outbox[1]["To"]
    assert "cimzett@teszt.hu" in outbox[2]["To"]

    flow.in_warehouse(pid)
    assert len(outbox) == 5
    assert "beérkezett a raktárba" in _body_text(outbox[3])
    assert "beérkezett a raktárba" in _body_text(outbox[4])

    flow.delivery_assigned(pid)
    assert len(outbox) == 7
    assert "cimzett@teszt.hu" in outbox[6]["To"]
    assert "10:00–12:00" in _body_text(outbox[6])

    flow.out_for_delivery(pid)
    assert len(outbox) == 9
    assert "kiszállítás alatt" in outbox[8]["Subject"].lower()

    flow.delivered(pid)
    assert len(outbox) == 11
    assert "kiszállítva" in outbox[10]["Subject"].lower()


def test_email_warehouse_assign_dedup_and_reschedule(client, logistician, courier, make_actor, customer, book, flow, outbox):
    from helpers import day

    courier2 = make_actor(UserRole.COURIER)
    parcel = book(customer, sender_email=customer.email, recipient_email="cimzett@teszt.hu")
    pid = parcel["id"]
    outbox.clear()

    # Initial pickup assign -> 1 email, repeat -> 0 emails
    flow.pickup_assigned(pid, courier)
    flow.pickup_assigned(pid, courier)
    assert len(outbox) == 1
    outbox.clear()

    flow.picked_up(pid, courier)
    flow.in_warehouse(pid)
    outbox.clear()

    # Initial delivery assign -> 2 separate emails (#5)
    flow.delivery_assigned(pid, courier, delivery_date=day(3), delivery_slot="10:00-12:00")
    assert len(outbox) == 2
    assert "beütemezve" in outbox[0]["Subject"].lower()
    outbox.clear()

    # Identical repeat OR courier-only swap (same date & slot) -> 0 emails
    flow.delivery_assigned(pid, courier, delivery_date=day(3), delivery_slot="10:00-12:00")
    flow.delivery_assigned(pid, courier2, delivery_date=day(3), delivery_slot="10:00-12:00")
    assert len(outbox) == 0

    # Date/slot change -> #6 schedule updated (2 separate emails)
    flow.delivery_assigned(pid, courier2, delivery_date=day(4), delivery_slot="14:00-16:00")
    assert len(outbox) == 2
    assert "módosítás" in outbox[0]["Subject"].lower()
    assert f"{day(4)} 14:00–16:00" in _body_text(outbox[1])


def test_email_courier_failures_and_retry_checkin(customer, book, flow, outbox):
    # 1. Pickup failure -> 1 personalized email per party (not 2 per party)
    p_pickup_fail = book(customer, sender_email=customer.email, recipient_email="c1@teszt.hu")
    flow.pickup_assigned(p_pickup_fail["id"])
    outbox.clear()
    flow.fail(p_pickup_fail["id"], note="Zárt kapu")
    assert len(outbox) == 2
    assert customer.email in outbox[0]["To"]
    assert "c1@teszt.hu" in outbox[1]["To"]
    assert "sikertelen csomagfelvétel" in outbox[0]["Subject"].lower()
    assert "Zárt kapu" in _body_text(outbox[0])

    # 2. Delivery failures up to MAX_FAILED_DELIVERIES (3)
    p_deliv = book(customer, sender_email=customer.email, recipient_email="c2@teszt.hu")
    pid = p_deliv["id"]
    flow.to(pid, "out_for_delivery")
    outbox.clear()

    # Attempt 1 -> 1 per party
    flow.fail(pid, note="Nem vette át 1")
    assert len(outbox) == 2
    assert "sikertelen kiszállítási" in outbox[0]["Subject"].lower()
    assert "1 / 3" in _body_text(outbox[0])
    outbox.clear()

    # Retry check-in -> distinct retry copy per party
    flow.in_warehouse(pid)
    assert len(outbox) == 2
    assert "visszaérkezett a raktárba" in _body_text(outbox[0]).lower()
    assert "visszaérkezett a raktárba" in _body_text(outbox[1]).lower()
    outbox.clear()

    # Attempt 2
    flow.delivery_assigned(pid)
    flow.out_for_delivery(pid)
    outbox.clear()
    flow.fail(pid, note="Nem vette át 2")
    assert len(outbox) == 2
    assert "2 / 3" in _body_text(outbox[0])
    flow.in_warehouse(pid)
    flow.delivery_assigned(pid)
    flow.out_for_delivery(pid)
    outbox.clear()

    # Attempt 3 -> auto-cancelled: 1 per party (not 2 per party)
    flow.fail(pid, note="Nem vette át 3")
    assert len(outbox) == 2
    assert "automatikusan lemondva" in outbox[0]["Subject"].lower()
    assert "Nem vette át 3" in _body_text(outbox[0])


def test_send_templated_email_skips_when_disabled_and_swallows_validation_errors(monkeypatch):
    import server.email.client as email_client

    monkeypatch.setattr(email_client, "_fastmail", None)
    monkeypatch.setattr(settings, "SMTP_ENABLED", False)
    monkeypatch.setattr(settings, "SMTP_FROM", "invalid-from")

    # Disabled SMTP must not even build ConnectionConfig / validate SMTP_FROM
    asyncio.run(
        send_templated_email(
            recipients=["teszt@teszt.hu"],
            subject="Teszt",
            template_name="account_event.html",
            context={"title": "T", "recipient_name": "R", "lead": "L", "details": []},
        )
    )

    # Enabled SMTP with invalid recipient must swallow MessageSchema ValidationError
    monkeypatch.setattr(settings, "SMTP_ENABLED", True)
    monkeypatch.setattr(settings, "SMTP_FROM", "noreply@projektlabor.hu")
    monkeypatch.setattr(email_client, "_fastmail", None)
    asyncio.run(
        send_templated_email(
            recipients=["not-an-email"],
            subject="Teszt",
            template_name="account_event.html",
            context={"title": "T", "recipient_name": "R", "lead": "L", "details": []},
        )
    )


def test_email_api_succeeds_when_smtp_fails(client, monkeypatch):
    from helpers import parcel_body
    import server.email.client as email_client

    monkeypatch.setattr(email_client, "_fastmail", None)
    monkeypatch.setattr(settings, "SMTP_ENABLED", True)
    fm = get_fastmail(force_reload=True)
    fm.config.SUPPRESS_SEND = 0

    with patch.object(fm, "send_message", new=AsyncMock(side_effect=RuntimeError("SMTP unreachable"))) as mock_send:
        res = client.post("/parcels", json=parcel_body())
    mock_send.assert_awaited()
    assert res.status_code == 201
    tracking = res.json()["tracking_number"]
    assert client.get(f"/parcels/track/{tracking}").status_code == 200

