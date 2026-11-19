from fastapi import BackgroundTasks
from server.email.client import send_templated_email
from server.email.schemas import ParcelEmailSnapshot, UserEmailSnapshot
from server.models import Parcel, User


def _schedule(
    bg: BackgroundTasks | None,
    recipients: list[str],
    subject: str,
    template_name: str,
    context: dict,
) -> None:
    if bg is None or not recipients:
        return
    bg.add_task(send_templated_email, recipients, subject, template_name, context)


def _schedule_parcel_event(
    bg: BackgroundTasks | None,
    snap: ParcelEmailSnapshot,
    *,
    subject_prefix: str,
    title: str,
    sender_lead: str,
    recipient_lead: str | None = None,
    details: list[tuple[str, str]],
    footer_note: str | None = None,
    notify_sender: bool = True,
    notify_recipient: bool = True,
) -> None:
    if bg is None:
        return

    targets: list[tuple[str, str, str]] = []
    if notify_sender:
        targets.append((snap.sender.email, snap.sender.full_name, sender_lead))
    if notify_recipient and (
        not notify_sender or snap.recipient.email.lower() != snap.sender.email.lower()
    ):
        targets.append((snap.recipient.email, snap.recipient.full_name, recipient_lead or sender_lead))

    subject = f"[{snap.tracking_number}] {subject_prefix}"
    for email, name, lead in targets:
        _schedule(
            bg,
            [email],
            subject,
            "parcel_event.html",
            {
                "title": title,
                "recipient_name": name,
                "lead": lead,
                "tracking_number": snap.tracking_number,
                "details": details,
                "footer_note": footer_note,
            },
        )


def _base_parcel_details(snap: ParcelEmailSnapshot) -> list[tuple[str, str]]:
    return [
        ("Méret", snap.size),
        ("Feladó", f"{snap.sender.full_name} ({snap.sender.address_line})"),
        ("Címzett", f"{snap.recipient.full_name} ({snap.recipient.address_line})"),
    ]


# Account notifications

def notify_registered(bg: BackgroundTasks | None, user: User) -> None:
    if bg is None:
        return
    snap = UserEmailSnapshot.from_user(user)
    _schedule(
        bg,
        [snap.email],
        "Sikeres regisztráció — ProjektLabor Futárszolgálat",
        "account_event.html",
        {
            "title": "Üdvözlünk a ProjektLabor rendszerében!",
            "recipient_name": snap.full_name,
            "lead": "Fiókod sikeresen létrejött. Mostantól nyomon követheted feladott és érkező csomagjaidat.",
            "details": [("Email cím", snap.email)],
            "footer_note": None,
        },
    )


def notify_password_changed(bg: BackgroundTasks | None, user: User) -> None:
    if bg is None:
        return
    snap = UserEmailSnapshot.from_user(user)
    _schedule(
        bg,
        [snap.email],
        "Jelszó módosítva — ProjektLabor Futárszolgálat",
        "account_event.html",
        {
            "title": "Jelszócsere visszaigazolása",
            "recipient_name": snap.full_name,
            "lead": "Fiókod jelszavát sikeresen megváltoztatták.",
            "details": [("Fiók", snap.email)],
            "footer_note": "Ha nem te végezted ezt a módosítást, kérjük lépj kapcsolatba az ügyfélszolgálattal.",
        },
    )


def notify_email_changed(bg: BackgroundTasks | None, user: User, old_email: str) -> None:
    if bg is None:
        return
    snap = UserEmailSnapshot.from_user(user)
    _schedule(
        bg,
        [old_email, snap.email],
        "Email cím módosítva — ProjektLabor Futárszolgálat",
        "account_event.html",
        {
            "title": "Email cím módosítás értesítés",
            "recipient_name": snap.full_name,
            "lead": "Fiókodhoz tartozó email cím megváltozott.",
            "details": [("Korábbi email", old_email), ("Új email", snap.email)],
            "footer_note": "Ha nem te kezdeményezted a módosítást, azonnal jelezd az adminisztrátornak.",
        },
    )


# Parcel lifecycle notifications

def notify_parcel_booked(bg: BackgroundTasks | None, parcel: Parcel) -> None:
    if bg is None:
        return
    snap = ParcelEmailSnapshot.from_parcel(parcel)
    _schedule_parcel_event(
        bg,
        snap,
        subject_prefix="Csomag előjegyezve",
        title="Csomag előjegyzés visszaigazolása",
        sender_lead="Köszönjük! Csomagfeladási előjegyzésedet sikeresen rögzítettük a rendszerben.",
        recipient_lead=f"Értesítünk, hogy {snap.sender.full_name} csomagot jegyzett elő a részedre.",
        details=[
            *_base_parcel_details(snap),
            ("Tervezett felvétel", snap.pickup_window),
        ],
    )


def notify_pickup_assigned(bg: BackgroundTasks | None, parcel: Parcel) -> None:
    if bg is None:
        return
    snap = ParcelEmailSnapshot.from_parcel(parcel)
    _schedule_parcel_event(
        bg,
        snap,
        subject_prefix="Felvételhez futár kiosztva",
        title="Csomagfelvétel beütemezve",
        sender_lead="Futárunkat kijelöltük a csomagod felvételére a tervezett időpontban.",
        details=[
            ("Tervezett felvétel", snap.pickup_window),
            ("Felvételi cím", snap.sender.address_line),
        ],
        notify_sender=True,
        notify_recipient=False,
    )


def notify_parcel_picked_up(bg: BackgroundTasks | None, parcel: Parcel) -> None:
    if bg is None:
        return
    snap = ParcelEmailSnapshot.from_parcel(parcel)
    _schedule_parcel_event(
        bg,
        snap,
        subject_prefix="Csomag felvéve",
        title="A futár felvette a csomagot",
        sender_lead="Futárunk átvette tőled a csomagot, amely jelenleg az elosztó raktárunkba tart.",
        recipient_lead=f"A részedre feladott csomagot ({snap.sender.full_name}) futárunk felvette, és elindult vele az elosztó raktárunkba.",
        details=_base_parcel_details(snap),
    )


def notify_parcel_in_warehouse(
    bg: BackgroundTasks | None,
    parcel: Parcel,
    *,
    returned_after_failure: bool = False,
) -> None:
    if bg is None:
        return
    snap = ParcelEmailSnapshot.from_parcel(parcel)
    if returned_after_failure:
        subject_prefix = "Csomag visszaérkezett a raktárba"
        title = "Csomag visszaérkezett a raktárba"
        sender_lead = "A sikertelen kézbesítési kísérletet követően a csomagod visszaérkezett az elosztó raktárunkba."
        recipient_lead = "A sikertelen kézbesítési kísérletet követően a részedre érkező csomag visszaérkezett az elosztó raktárunkba, hamarosan új időpontot ütemezünk."
    else:
        subject_prefix = "Csomag raktárban"
        title = "Csomag beérkezett a raktárba"
        sender_lead = "A feladott csomagod megérkezett elosztó raktárunkba, hamarosan ütemezzük a kiszállítását."
        recipient_lead = "A részedre érkező csomag megérkezett elosztó raktárunkba, hamarosan ütemezzük a kiszállítását."
    _schedule_parcel_event(
        bg,
        snap,
        subject_prefix=subject_prefix,
        title=title,
        sender_lead=sender_lead,
        recipient_lead=recipient_lead,
        details=_base_parcel_details(snap),
    )


def notify_delivery_assigned(bg: BackgroundTasks | None, parcel: Parcel) -> None:
    if bg is None:
        return
    snap = ParcelEmailSnapshot.from_parcel(parcel)
    _schedule_parcel_event(
        bg,
        snap,
        subject_prefix="Kiszállítás időpontja beütemezve",
        title="Kiszállítás kiosztva",
        sender_lead="Beütemeztük a csomagod kiszállítását a címzetthez a megadott időpontban.",
        recipient_lead="Beütemeztük a részedre érkező csomag kiszállítását a megadott időpontban.",
        details=[
            ("Várható kiszállítás", snap.delivery_window or "egyeztetés alatt"),
            ("Kézbesítési cím", snap.recipient.address_line),
            ("Feladó", snap.sender.full_name),
        ],
        notify_sender=True,
        notify_recipient=True,
    )


def notify_parcel_schedule_updated(
    bg: BackgroundTasks | None,
    parcel: Parcel,
    *,
    notify_sender: bool = True,
    notify_recipient: bool = True,
    note: str | None = None,
) -> None:
    if bg is None:
        return
    snap = ParcelEmailSnapshot.from_parcel(parcel)
    details = [
        *_base_parcel_details(snap),
        ("Tervezett felvétel", snap.pickup_window),
        ("Tervezett kiszállítás", snap.delivery_window or "egyeztetés alatt"),
    ]
    if note:
        details.append(("Megjegyzés", note))
    _schedule_parcel_event(
        bg,
        snap,
        subject_prefix="Időpont / adat módosítás visszaigazolása",
        title="Csomagadatok frissítve",
        sender_lead="A csomagodhoz tartozó időpont vagy szállítási adat módosult.",
        recipient_lead="A részedre érkező csomag időpontja vagy szállítási adata módosult.",
        details=details,
        notify_sender=notify_sender,
        notify_recipient=notify_recipient,
    )


def notify_parcel_out_for_delivery(bg: BackgroundTasks | None, parcel: Parcel) -> None:
    if bg is None:
        return
    snap = ParcelEmailSnapshot.from_parcel(parcel)
    _schedule_parcel_event(
        bg,
        snap,
        subject_prefix="Csomag kiszállítás alatt",
        title="A csomag kiszállítás alatt van",
        sender_lead="Futárunk elindult a csomagoddal a címzetthez.",
        recipient_lead="Futárunk elindult hozzád a csomaggal, hamarosan kézbesítjük.",
        details=[
            ("Várható kiszállítás", snap.delivery_window or "egyeztetés alatt"),
            ("Kézbesítési cím", snap.recipient.address_line),
        ],
    )


def notify_parcel_delivered(bg: BackgroundTasks | None, parcel: Parcel) -> None:
    if bg is None:
        return
    snap = ParcelEmailSnapshot.from_parcel(parcel)
    _schedule_parcel_event(
        bg,
        snap,
        subject_prefix="Csomag kiszállítva",
        title="Sikeres kézbesítés",
        sender_lead="A csomagodat sikeresen átadtuk a címzettnek.",
        recipient_lead="Csomagodat sikeresen kézbesítettük. Köszönjük, hogy minket választottál!",
        details=_base_parcel_details(snap),
    )


def notify_pickup_failed(
    bg: BackgroundTasks | None,
    parcel: Parcel,
    *,
    reason: str | None,
) -> None:
    if bg is None:
        return
    snap = ParcelEmailSnapshot.from_parcel(parcel)
    details = list(_base_parcel_details(snap))
    if reason:
        details.append(("Indoklás", reason))
    _schedule_parcel_event(
        bg,
        snap,
        subject_prefix="Sikertelen csomagfelvétel",
        title="A csomag felvétele sikertelen volt",
        sender_lead="A futár nem tudta felvenni a csomagodat, ezért a megbízás lezárásra (törlésre) került.",
        recipient_lead="A részedre előjegyzett csomag felvétele sikertelen volt, ezért a megbízás lezárásra (törlésre) került.",
        details=details,
        footer_note="Amennyiben továbbra is szeretnéd feladni a csomagot, kérjük rögzíts új előjegyzést.",
    )


def notify_delivery_failed(
    bg: BackgroundTasks | None,
    parcel: Parcel,
    *,
    reason: str | None,
    attempt: int,
    max_attempts: int,
) -> None:
    if bg is None:
        return
    snap = ParcelEmailSnapshot.from_parcel(parcel)
    details = [
        *_base_parcel_details(snap),
        ("Próbálkozás", f"{attempt} / {max_attempts}"),
    ]
    if reason:
        details.append(("Indoklás", reason))
    _schedule_parcel_event(
        bg,
        snap,
        subject_prefix="Sikertelen kiszállítási kísérlet",
        title="A csomag kézbesítése sikertelen volt",
        sender_lead="Futárunk megkísérelte a csomagod kézbesítését a címzettnek, de az átadás nem sikerült.",
        recipient_lead="Futárunk megkísérelte a csomagod kézbesítését, de az átadás nem sikerült.",
        details=details,
        footer_note="A csomag visszakerül a raktárba, és hamarosan új kiszállítási időpontot ütemezünk.",
    )


def notify_parcel_auto_cancelled(
    bg: BackgroundTasks | None,
    parcel: Parcel,
    *,
    reason: str | None,
    max_attempts: int,
) -> None:
    if bg is None:
        return
    snap = ParcelEmailSnapshot.from_parcel(parcel)
    details = [
        *_base_parcel_details(snap),
        ("Sikertelen kísérletek száma", str(max_attempts)),
    ]
    if reason:
        details.append(("Utolsó indoklás", reason))
    _schedule_parcel_event(
        bg,
        snap,
        subject_prefix="Csomag automatikusan lemondva",
        title="Automatikus lemondás",
        sender_lead=f"A csomagod kézbesítése {max_attempts} alkalommal sikertelen volt, ezért automatikusan lemondásra került.",
        recipient_lead=f"A részedre érkező csomag kézbesítése {max_attempts} alkalommal sikertelen volt, ezért automatikusan lemondásra került.",
        details=details,
    )


def notify_parcel_cancelled(bg: BackgroundTasks | None, parcel: Parcel) -> None:
    if bg is None:
        return
    snap = ParcelEmailSnapshot.from_parcel(parcel)
    _schedule_parcel_event(
        bg,
        snap,
        subject_prefix="Csomag lemondva",
        title="A csomag lemondásra került",
        sender_lead="A csomagod szállítási megbízását lemondták.",
        recipient_lead="A részedre érkező csomag szállítási megbízását lemondták.",
        details=_base_parcel_details(snap),
    )
