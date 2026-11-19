# Demo data: about two years of operation with users, parcels and the full event log.
# Run from the project root after server.seed (DB must be running):
#   .venv\Scripts\python -m server.seed_demo            fill the database
#   .venv\Scripts\python -m server.seed_demo --remove   delete the generated data
# Generated people use *.example addresses (reserved, never deliverable), password Alma.123.
# The test accounts (admin@, raktaros@, futar@, ugyfel@teszt.hu) take part if they exist.
# Existing rows are never modified. Everything is written in one transaction.
import argparse
import math
import random
import sys
import time as clock
import unicodedata
import zlib
from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, func, insert, or_, select
from sqlalchemy.orm import Session

from server.models import Contact, Parcel, ParcelEvent, ParcelStatus, User, UserRole, Warehouse
from server.src.config import settings
from server.src.database import DBSession
from server.src.sec import hash_pass
from server.API.parcel.services import ADMIN_COURIER_NOTE, TRACKING_ALPHABET, TRACKING_PREFIX
from server.API.warehouse.services import IN_WAREHOUSE_STATUSES

S = ParcelStatus
PASSWORD = "Alma.123"
DEMO_SUFFIX = ".example"
STAFF_DOMAIN = "csomagfutar.example"
MAIL_DOMAINS = (
    ("gmail.example", 45), ("freemail.example", 20), ("outlook.example", 12),
    ("citromail.example", 10), ("yahoo.example", 7), ("t-online.example", 6),
)
DAYS = 730
LOCAL = ZoneInfo("Europe/Budapest")
TEST_EMAILS = {
    UserRole.ADMIN: "admin@teszt.hu",
    UserRole.LOGISTICIAN: "raktaros@teszt.hu",
    UserRole.COURIER: "futar@teszt.hu",
    UserRole.CUSTOMER: "ugyfel@teszt.hu",
}
# The test customer has no address in its profile, its parcels use this one
TEST_CUSTOMER_ADDRESS = ("8200", "Veszprém", "Egyetem utca", "10")
# Same order as add_event
MILESTONES = (
    (S.PICKED_UP, "picked_up_at"),
    (S.IN_WAREHOUSE, "warehouse_arrived_at"),
    (S.OUT_FOR_DELIVERY, "out_for_delivery_at"),
    (S.DELIVERED, "delivered_at"),
)
SLOTS = tuple((time(hour), time(hour + 2)) for hour in range(8, 20, 2))
PICKUP_SLOT_WEIGHTS = (12, 20, 17, 18, 20, 13)
DELIVERY_SLOT_WEIGHTS = (15, 20, 17, 17, 19, 12)
SIZES = (("S", 35), ("M", 38), ("L", 19), ("XL", 8))
# Days between booking and pickup
LEAD_DAYS = ((1, 35), (2, 25), (3, 15), (4, 8), (5, 6), (6, 4), (7, 3), (10, 2), (14, 2))
BOOKING_HOURS = (
    (7, 3), (8, 5), (9, 7), (10, 9), (11, 9), (12, 8), (13, 7), (14, 6), (15, 6),
    (16, 6), (17, 6), (18, 7), (19, 8), (20, 8), (21, 6), (22, 3),
)
PICKUP_FAIL_NOTES = (
    "A feladó nem volt elérhető a megadott idősávban",
    "A csomag nem volt átadásra előkészítve",
    "A feladó a helyszínen elállt a feladástól",
    "A megadott címen nem található a feladó",
)
DELIVERY_FAIL_NOTES = (
    "A címzett nem volt otthon",
    "A címzett telefonon nem volt elérhető",
    "A címzett megtagadta az átvételt",
    "Hiányos cím, a címzett nem található",
    "Nem lehetett bejutni az épületbe",
)

LAST_NAMES = (
    "Nagy", "Kovács", "Tóth", "Szabó", "Horváth", "Varga", "Kiss", "Molnár", "Németh", "Farkas",
    "Balogh", "Papp", "Takács", "Juhász", "Lakatos", "Mészáros", "Oláh", "Simon", "Rácz", "Fekete",
    "Szilágyi", "Török", "Fehér", "Balázs", "Gál", "Kis", "Szűcs", "Kocsis", "Pintér", "Fodor",
    "Szalai", "Sipos", "Magyar", "Lukács", "Gulyás", "Biró", "Király", "László", "Katona", "Jakab",
    "Sándor", "Boros", "Fazekas", "Kelemen", "Antal", "Orosz", "Somogyi", "Fülöp", "Veres", "Budai",
    "Vincze", "Hegedűs", "Deák", "Bálint", "Illés", "Pál", "Vass", "Szőke", "Fábián", "Vörös",
    "Lengyel", "Bognár", "Jónás", "Szekeres", "Hajdu", "Halász", "Major", "Bakos", "Kozma", "Csizmadia",
)
MALE_NAMES = (
    "László", "István", "József", "János", "Zoltán", "Sándor", "Gábor", "Ferenc", "Attila", "Péter",
    "Tamás", "Zsolt", "Tibor", "András", "Csaba", "Imre", "Lajos", "György", "Balázs", "Róbert",
    "Mihály", "Gergő", "Bence", "Máté", "Dávid", "Ádám", "Dániel", "Levente", "Márk", "Krisztián",
    "Norbert", "Roland", "Viktor", "Patrik", "Milán", "Dominik", "Botond", "Kristóf", "Olivér", "Richárd",
)
FEMALE_NAMES = (
    "Mária", "Erzsébet", "Katalin", "Éva", "Ilona", "Anna", "Zsuzsanna", "Margit", "Judit", "Ágnes",
    "Andrea", "Erika", "Krisztina", "Edit", "Gabriella", "Szilvia", "Mónika", "Anita", "Eszter", "Viktória",
    "Nikolett", "Melinda", "Tímea", "Dóra", "Réka", "Petra", "Hanna", "Zsófia", "Lili", "Luca",
    "Boglárka", "Fanni", "Noémi", "Kitti", "Bernadett", "Rita", "Orsolya", "Beáta", "Adrienn", "Barbara",
)
# Real team members' names are not generated
EXCLUDED_NAMES = {("Molnár", "Mihály"), ("Preil", "Patrik")}
# Veszprém county, weighted roughly by population
CITIES = (
    ("8200", "Veszprém", 30), ("8400", "Ajka", 10), ("8500", "Pápa", 11), ("8100", "Várpalota", 7),
    ("8230", "Balatonfüred", 6), ("8220", "Balatonalmádi", 4), ("8300", "Tapolca", 6), ("8420", "Zirc", 3),
    ("8330", "Sümeg", 2), ("8440", "Herend", 1.5), ("8460", "Devecser", 1.5), ("8174", "Balatonkenese", 1.2),
    ("8181", "Berhida", 1.5), ("8105", "Pétfürdő", 1.3), ("8192", "Hajmáskér", 1), ("8196", "Litér", 0.8),
    ("8248", "Nemesvámos", 1), ("8225", "Szentkirályszabadja", 0.6), ("8229", "Csopak", 0.6),
    ("8175", "Balatonfűzfő", 1.2), ("8253", "Révfülöp", 0.4), ("8258", "Badacsonytomaj", 0.6),
    ("8409", "Úrkút", 0.6), ("8441", "Márkó", 0.4), ("8413", "Eplény", 0.2), ("8191", "Öskü", 0.6),
)
STREETS = (
    "Petőfi Sándor utca", "Kossuth Lajos utca", "Rákóczi Ferenc utca", "Ady Endre utca", "Jókai Mór utca",
    "Táncsics Mihály utca", "Arany János utca", "Szabadság tér", "Dózsa György út", "Kinizsi Pál utca",
    "Bem József utca", "Széchenyi István utca", "Deák Ferenc utca", "Fő utca", "Béke utca",
    "Hunyadi János utca", "Vörösmarty Mihály utca", "Liszt Ferenc utca", "Bartók Béla utca", "Egry József utca",
    "Mártírok útja", "Szent István utca", "Kodály Zoltán utca", "Rózsa utca", "Ibolya utca",
    "Tavasz utca", "Erdő utca", "Kórház utca", "Iskola utca", "Vasút utca", "Hold utca", "Damjanich utca",
)


@dataclass
class Person:
    last_name: str
    first_name: str
    email: str
    phone: str | None
    postal_code: str
    city: str
    street: str
    house_number: str

    def contact(self, user_id: int | None) -> dict:
        return {
            "user_id": user_id, "last_name": self.last_name, "first_name": self.first_name,
            "email": self.email, "phone": self.phone, "postal_code": self.postal_code,
            "city": self.city, "street": self.street, "house_number": self.house_number,
        }


@dataclass
class Account:
    role: UserRole
    person: Person
    # Active periods, end inclusive (None: still active)
    periods: list[tuple[date, date | None]]
    weight: float = 1.0
    has_address: bool = True
    user_id: int | None = None
    existing: bool = False
    index: int = 0
    off_days: set = field(default_factory=set)

    @property
    def is_active(self) -> bool:
        return self.periods[-1][1] is None

    def active_on(self, day: date) -> bool:
        return any(start <= day and (end is None or day <= end) for start, end in self.periods)


@dataclass
class Story:
    sender: Person
    sender_acc: Account | None
    recipient: Person
    recipient_acc: Account | None
    size: str
    # (local time, status or None for a silent change, courier, actor, note, column changes)
    steps: list = field(default_factory=list)

    def add(self, when, status=None, courier=None, actor=None, note=None, **changes):
        if self.steps and when < self.steps[-1][0]:
            when = self.steps[-1][0]
        self.steps.append((when, status, courier, actor, note, changes))


def _weighted(rng: random.Random, pairs):
    values, weights = zip(*pairs)
    return rng.choices(values, weights=weights)[0]


def _ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def _easter(year: int) -> date:
    # Anonymous Gregorian algorithm
    a, (b, c) = year % 19, divmod(year, 100)
    d, e = divmod(b, 4)
    g = (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return date(year, month, day + 1)


def _holidays(years) -> set[date]:
    days = set()
    for year in years:
        easter = _easter(year)
        days |= {
            date(year, 1, 1), date(year, 3, 15), easter - timedelta(days=2), easter + timedelta(days=1),
            date(year, 5, 1), easter + timedelta(days=50), date(year, 8, 20), date(year, 10, 23),
            date(year, 11, 1), date(year, 12, 24), date(year, 12, 25), date(year, 12, 26),
        }
    return days


def _to_utc(local: datetime) -> datetime:
    # The DB stores naive UTC (now() in a UTC session), the client converts it back
    return local.replace(tzinfo=LOCAL).astimezone(timezone.utc).replace(tzinfo=None)


class Generator:
    def __init__(self, seed: int, now_local: datetime):
        self.rng = random.Random(seed)
        self.now = now_local
        self.today = now_local.date()
        self.start = self.today - timedelta(days=DAYS)
        self.holidays = _holidays(range(self.start.year, self.today.year + 2))
        self.emails: set[str] = set()
        self.customers: list[Account] = []
        self.couriers: list[Account] = []
        self.logisticians: list[Account] = []
        self.admins: list[Account] = []
        self.test_customer: Account | None = None
        self.guests: list[Person] = []
        self.stories: list[Story] = []
        self.warehouse_id: int | None = None
        self._on_duty: dict[date, list[Account]] = {}
        self._customer_pool: dict[date, tuple] = {}

    # --- Calendar ------------------------------------------------

    def operating(self, day: date) -> bool:
        return day.weekday() != 6 and day not in self.holidays

    def next_operating(self, day: date) -> date:
        day += timedelta(days=1)
        while not self.operating(day):
            day += timedelta(days=1)
        return day

    def prev_operating(self, day: date) -> date:
        day -= timedelta(days=1)
        while not self.operating(day):
            day -= timedelta(days=1)
        return day

    def at(self, day: date, hour: int, minute: int = 0) -> datetime:
        return datetime.combine(day, time(hour, minute))

    def between(self, first: datetime, last: datetime) -> datetime:
        if last <= first:
            return first + timedelta(seconds=self.rng.randint(30, 240))
        seconds = self.rng.uniform(0, (last - first).total_seconds())
        return first + timedelta(seconds=seconds)

    def within_hours(self, first: datetime, last: datetime, start_hour: int, end_hour: int) -> datetime:
        # A moment between first and last during the given hours of some day
        days = max((last.date() - first.date()).days, 0)
        for _ in range(20):
            day = first.date() + timedelta(days=self.rng.randint(0, days))
            when = self.between(self.at(day, start_hour), self.at(day, end_hour))
            if first < when < last:
                return when
        return first + timedelta(minutes=1)

    def volume(self, day: date) -> float:
        # Growing business, weekly rhythm, seasonal peaks
        base = 18 + 27 * (day - self.start).days / DAYS
        weekday = (1.15, 1.05, 1.0, 1.0, 1.1, 0.45, 0.0)[day.weekday()]
        season = (0.8, 0.85, 0.95, 1.0, 1.0, 0.95, 0.9, 0.85, 1.0, 1.05, 1.15, 1.0)[day.month - 1]
        if day.month == 11 and day.day >= 22:
            season = 1.45
        elif day.month == 12:
            season = 1.6 if day.day <= 20 else 1.2 if day.day <= 23 else 0.55
        elif day.month == 1 and day.day <= 6:
            season = 0.7
        return base * weekday * season

    # --- People --------------------------------------------------

    def _name(self) -> tuple[str, str]:
        while True:
            last = self.rng.choice(LAST_NAMES)
            first = self.rng.choice(MALE_NAMES if self.rng.random() < 0.5 else FEMALE_NAMES)
            if (last, first) not in EXCLUDED_NAMES:
                return last, first

    def _email(self, last: str, first: str, domain: str, unique: bool) -> str:
        last_a, first_a = _ascii(last), _ascii(first)
        patterns = (
            f"{last_a}.{first_a}", f"{first_a}.{last_a}", f"{last_a}{first_a}{self.rng.randint(60, 99)}",
            f"{first_a}.{last_a}{self.rng.randint(1, 99)}", f"{first_a[0]}{last_a}",
        )
        local = self.rng.choice(patterns)
        email = f"{local}@{domain}"
        counter = 2
        while email in self.emails:
            email = f"{local}{counter}@{domain}"
            counter += 1
        if unique:
            self.emails.add(email)
        return email

    def _phone(self) -> str:
        return f"+36 {self.rng.choice((20, 30, 70))} {self.rng.randint(100, 999)} {self.rng.randint(1000, 9999)}"

    def _address(self) -> tuple[str, str, str, str]:
        postal_code, city = _weighted(self.rng, ((c[:2], c[2]) for c in CITIES))
        number = str(self.rng.randint(1, 140))
        kind = self.rng.random()
        if kind < 0.1:
            number += "/" + self.rng.choice("ABC")
        elif kind < 0.2:
            number += f". {self.rng.randint(1, 4)}/{self.rng.randint(1, 12)}"
        return postal_code, city, self.rng.choice(STREETS), number

    def person(self, domain: str | None = None, unique: bool = False, phone_rate: float = 0.7) -> Person:
        last, first = self._name()
        domain = domain or _weighted(self.rng, MAIL_DOMAINS)
        return Person(last, first, self._email(last, first, domain, unique),
                      self._phone() if self.rng.random() < phone_rate else None, *self._address())

    def guest(self) -> Person:
        # Some guests book again with the same data
        if self.guests and self.rng.random() < 0.2:
            return self.rng.choice(self.guests)
        person = self.person()
        self.guests.append(person)
        return person

    def day_at(self, offset: int) -> date:
        return self.start + timedelta(days=offset)

    def _staff(self, role: UserRole, plan, phone_rate: float = 0.3) -> list[Account]:
        accounts = []
        for periods in plan:
            person = self.person(STAFF_DOMAIN, unique=True, phone_rate=phone_rate)
            accounts.append(Account(role, person, periods, has_address=False))
        return accounts

    def build_accounts(self, test_users: dict[UserRole, User]) -> list[Account]:
        rel = lambda first, last=None: [(self.day_at(first), None if last is None else self.day_at(last))]
        couriers = self._staff(UserRole.COURIER, [
            rel(0), rel(0), rel(0, 260), rel(0), rel(0, 400), rel(95), rel(180, 560),
            rel(270), rel(370), rel(430), rel(520), rel(610), rel(680),
        ], phone_rate=1.0)
        # Seasonal courier: every Christmas period, reactivated each year
        seasonal = []
        for year in range(self.start.year, self.today.year + 1):
            first, last = max(date(year, 11, 20), self.start), date(year + 1, 1, 8)
            if first <= self.today:
                seasonal.append((first, None if last >= self.today else last))
        if seasonal:
            couriers += self._staff(UserRole.COURIER, [seasonal], phone_rate=1.0)
        logisticians = self._staff(UserRole.LOGISTICIAN, [rel(0, 330), rel(300)])
        admins = self._staff(UserRole.ADMIN, [rel(0, 200), rel(0)])

        customers = []
        for n in range(420):
            joined = 0 if n < 70 else int(DAYS * math.sqrt(self.rng.random()) * 0.97)
            periods = [(self.day_at(joined), None)]
            if self.rng.random() < 0.06 and DAYS - joined > 90:
                periods = [(self.day_at(joined), self.day_at(self.rng.randint(joined + 30, DAYS - 20)))]
            # Most customers send rarely, five small web shops send a lot
            weight = self.rng.uniform(40, 90) if n < 5 else min(self.rng.paretovariate(1.3), 15.0)
            customers.append(Account(UserRole.CUSTOMER, self.person(unique=True), periods, weight,
                                     has_address=self.rng.random() < 0.85))
        # Two former customers registered again later with the same email
        for old in [c for c in customers if not c.is_active][:2]:
            back = old.periods[-1][1] + timedelta(days=self.rng.randint(40, 120))
            if back < self.today:
                customers.append(Account(UserRole.CUSTOMER, old.person, [(back, None)], old.weight, old.has_address))

        # Test accounts: active for the whole period
        whole = [(self.start, None)]
        for role, user in test_users.items():
            if role is UserRole.CUSTOMER:
                person = Person(user.last_name, user.first_name, user.email, user.phone, *TEST_CUSTOMER_ADDRESS)
            else:
                person = Person(user.last_name, user.first_name, user.email, user.phone, "", "", "", "")
            account = Account(role, person, whole, user_id=user.id, existing=True)
            if role is UserRole.COURIER:
                couriers.insert(0, account)
            elif role is UserRole.LOGISTICIAN:
                logisticians.insert(0, account)
            elif role is UserRole.ADMIN:
                admins.insert(0, account)
            else:
                self.test_customer = account

        for index, courier in enumerate(couriers):
            courier.index = index
            courier.off_days = self._off_days(courier)
        self.couriers, self.logisticians, self.admins, self.customers = couriers, logisticians, admins, customers
        new = [a for a in couriers + logisticians + admins + customers if not a.existing]
        # Insert order follows the join date, like real registrations
        return sorted(new, key=lambda a: a.periods[0][0])

    def _off_days(self, courier: Account) -> set[date]:
        # Two vacation weeks and a few sick days per year
        days = set()
        for year_start in range(0, DAYS + 1, 365):
            for _ in range(2):
                day = self.day_at(year_start + self.rng.randint(0, 364))
                for _ in range(5):
                    day = self.next_operating(day)
                    days.add(day)
            for _ in range(6):
                days.add(self.day_at(year_start + self.rng.randint(0, 364)))
        return days

    # --- Who works / acts on a day --------------------------------

    def couriers_on(self, day: date) -> list[Account]:
        if day not in self._on_duty:
            employed = [c for c in self.couriers if c.active_on(day)]
            working = [
                c for c in employed
                if day not in c.off_days and (day.weekday() != 5 or (c.index + day.isocalendar()[1]) % 2 == 0)
            ]
            self._on_duty[day] = working or employed
        return self._on_duty[day]

    def pick_courier(self, day: date, person: Person, exclude: Account | None = None) -> Account:
        on_duty = [c for c in self.couriers_on(day) if c is not exclude] or self.couriers_on(day)
        if self.rng.random() < 0.8:
            # Same street, usually the same courier (zones)
            zone = zlib.crc32(f"{person.city}|{person.street}".encode())
            return on_duty[zone % len(on_duty)]
        return self.rng.choice(on_duty)

    def logistician_on(self, day: date) -> Account:
        working = [a for a in self.logisticians if a.active_on(day)] or self.admins_on(day)
        return working[day.isocalendar()[1] % len(working)]

    def admins_on(self, day: date) -> list[Account]:
        return [a for a in self.admins if a.active_on(day)]

    def customer_pool(self, day: date):
        if day not in self._customer_pool:
            active = [c for c in self.customers if c.active_on(day)]
            cumulative, total = [], 0.0
            for customer in active:
                total += customer.weight
                cumulative.append(total)
            self._customer_pool[day] = (active, cumulative, total)
        return self._customer_pool[day]

    def pick_customer(self, day: date, weighted: bool) -> Account | None:
        active, cumulative, total = self.customer_pool(day)
        if not active:
            return None
        if not weighted:
            return self.rng.choice(active)
        return active[min(bisect_left(cumulative, self.rng.uniform(0, total)), len(active) - 1)]

    # --- Parcels -------------------------------------------------

    def generate(self) -> None:
        day = self.start
        last_pickup_day = self.today + timedelta(days=14)
        while day <= last_pickup_day:
            if self.operating(day):
                expected = self.volume(day)
                count = max(0, round(self.rng.gauss(expected, math.sqrt(expected))))
                for _ in range(count):
                    self.book(day)
                if self.test_customer is not None:
                    recent = (self.today - day).days <= 12
                    if self.rng.random() < (0.6 if recent else 0.13):
                        self.book(day, sender_acc=self.test_customer)
                    if self.rng.random() < (0.4 if recent else 0.1):
                        self.book(day, recipient_acc=self.test_customer)
            day += timedelta(days=1)

    def book(self, pickup_day: date, sender_acc: Account | None = None, recipient_acc: Account | None = None,
             booked_at: datetime | None = None, sender: Person | None = None, recipient: Person | None = None,
             size: str | None = None) -> None:
        if booked_at is None:
            booking_day = pickup_day - timedelta(days=_weighted(self.rng, LEAD_DAYS))
            hour = _weighted(self.rng, BOOKING_HOURS)
            booked_at = self.at(booking_day, hour, self.rng.randint(0, 59)) + timedelta(
                seconds=self.rng.randint(0, 59), microseconds=self.rng.randint(0, 999999))
        if booked_at < self.at(self.start, 0) or booked_at > self.now:
            return
        booking_day = booked_at.date()

        if sender is None:
            if sender_acc is None and self.rng.random() < 0.6:
                sender_acc = self.pick_customer(booking_day, weighted=True)
            sender = sender_acc.person if sender_acc is not None else self.guest()
        if recipient is None:
            if recipient_acc is None and self.rng.random() < 0.15:
                candidate = self.pick_customer(booking_day, weighted=False)
                if candidate is not None and candidate is not sender_acc and candidate.person is not sender:
                    recipient_acc = candidate
            recipient = recipient_acc.person if recipient_acc is not None else self.guest()
            if recipient is sender:
                recipient, recipient_acc = self.person(), None
        story = Story(sender, sender_acc, recipient, recipient_acc, size or _weighted(self.rng, SIZES))
        self.simulate(story, booked_at, pickup_day)
        self.stories.append(story)

    def _pickup_assign_time(self, pickup_day: date, after: datetime) -> datetime:
        # The day before in the afternoon, or the same morning for late bookings
        prev = self.prev_operating(pickup_day)
        when = self.between(self.at(prev, 15), self.at(prev, 17, 30))
        if when > after:
            return when
        return max(self.between(self.at(pickup_day, 6, 40), self.at(pickup_day, 7, 40)), after + timedelta(minutes=5))

    def _check_in_time(self, day: date, done_at: datetime) -> datetime:
        # Midday round for morning work, otherwise the evening return
        if done_at < self.at(day, 12, 45):
            return self.between(self.at(day, 13), self.at(day, 13, 45))
        return max(self.between(self.at(day, 20, 5), self.at(day, 21)), done_at + timedelta(minutes=10))

    def _new_pickup(self, pickup_day: date) -> tuple[date, int]:
        day = self.next_operating(pickup_day)
        if self.rng.random() < 0.4:
            day = self.next_operating(day)
        return day, _weighted(self.rng, zip(range(6), PICKUP_SLOT_WEIGHTS))

    def simulate(self, st: Story, booked_at: datetime, pickup_day: date) -> None:
        rng = self.rng
        sender_id = st.sender_acc.user_id if st.sender_acc is not None else None
        slot = _weighted(rng, zip(range(6), PICKUP_SLOT_WEIGHTS))
        st.add(booked_at, S.BOOKED, actor=sender_id, pickup_date=pickup_day,
               pickup_window_start=SLOTS[slot][0], pickup_window_end=SLOTS[slot][1])

        # Changes before pickup: the sender (registered, until the day before) or an admin
        action, action_at = None, None
        roll = rng.random()
        if st.sender_acc is not None and roll < 0.025:
            action = "cancel"
        elif st.sender_acc is not None and roll < 0.045:
            action = "edit"
        elif roll < 0.048:
            action = "admin_cancel"
        if action is not None:
            deadline = self.at(pickup_day - timedelta(days=1), 22)
            hours = (8, 17) if action == "admin_cancel" else (7, 22)
            action_at = self.within_hours(booked_at + timedelta(minutes=10), deadline, *hours)
            if deadline <= booked_at + timedelta(minutes=15) or (
                    action != "admin_cancel" and not st.sender_acc.active_on(action_at.date())):
                action = None
        admin_id = lambda when: rng.choice(self.admins_on(when.date())).user_id

        assign_at = self._pickup_assign_time(pickup_day, booked_at)
        if action == "edit" and action_at < assign_at:
            pickup_day, slot = self._new_pickup(pickup_day)
            st.add(action_at, pickup_date=pickup_day, pickup_window_start=SLOTS[slot][0],
                   pickup_window_end=SLOTS[slot][1])
            assign_at, action = self._pickup_assign_time(pickup_day, action_at), None
        if action in ("cancel", "admin_cancel") and action_at < assign_at:
            st.add(action_at, S.CANCELLED, actor=sender_id if action == "cancel" else admin_id(action_at))
            return

        courier = self.pick_courier(pickup_day, st.sender)
        st.add(assign_at, S.PICKUP_ASSIGNED, courier=courier.user_id,
               actor=self.logistician_on(assign_at.date()).user_id, pickup_courier_id=courier.user_id)
        if action in ("cancel", "admin_cancel"):
            st.add(action_at, S.CANCELLED, actor=sender_id if action == "cancel" else admin_id(action_at))
            return
        if action == "edit":
            # The assigned courier is detached, the logistician assigns again
            pickup_day, slot = self._new_pickup(pickup_day)
            st.add(action_at, S.BOOKED, actor=sender_id, note="Felvételi időpont módosítva", pickup_courier_id=None,
                   pickup_date=pickup_day, pickup_window_start=SLOTS[slot][0], pickup_window_end=SLOTS[slot][1])
            assign_at = self._pickup_assign_time(pickup_day, action_at)
            courier = self.pick_courier(pickup_day, st.sender)
            st.add(assign_at, S.PICKUP_ASSIGNED, courier=courier.user_id,
                   actor=self.logistician_on(assign_at.date()).user_id, pickup_courier_id=courier.user_id)

        start, end = SLOTS[slot]
        slot_start, slot_end = self.at(pickup_day, start.hour), self.at(pickup_day, end.hour)
        if rng.random() < 0.025 and assign_at < slot_start - timedelta(minutes=30):
            # Logistician reassigns in the morning before the pickup
            other = self.pick_courier(pickup_day, st.sender, exclude=courier)
            if other is not courier:
                when = self.between(max(assign_at + timedelta(minutes=10), self.at(pickup_day, 6, 50)),
                                    min(slot_start - timedelta(minutes=10), self.at(pickup_day, 7, 50)))
                courier = other
                st.add(when, S.PICKUP_ASSIGNED, courier=courier.user_id,
                       actor=self.logistician_on(when.date()).user_id, pickup_courier_id=courier.user_id)

        picked_at = self.between(slot_start + timedelta(minutes=5), slot_end - timedelta(minutes=5))
        if rng.random() < 0.02:
            note = rng.choice(PICKUP_FAIL_NOTES)
            st.add(picked_at, S.FAILED, courier=courier.user_id, actor=courier.user_id, note=note)
            st.add(picked_at, S.CANCELLED, actor=courier.user_id, note="Sikertelen felvétel")
            rebooked = picked_at + timedelta(hours=rng.uniform(1, 30))
            if rebooked.hour < 7:
                rebooked = rebooked.replace(hour=rng.randint(7, 9))
            if rng.random() < 0.5 and (st.sender_acc is None or st.sender_acc.active_on(rebooked.date())):
                lead = _weighted(rng, ((1, 5), (2, 3), (3, 2)))
                day = rebooked.date() + timedelta(days=lead)
                while not self.operating(day):
                    day += timedelta(days=1)
                self.book(day, st.sender_acc, st.recipient_acc, rebooked, st.sender, st.recipient, st.size)
            return
        st.add(picked_at, S.PICKED_UP, courier=courier.user_id, actor=courier.user_id)

        checked_in = self._check_in_time(pickup_day, picked_at)
        st.add(checked_in, S.IN_WAREHOUSE, courier=courier.user_id,
               actor=self.logistician_on(pickup_day).user_id, warehouse_id=self.warehouse_id)

        failures = 0
        while True:
            ready_day = checked_in.date()
            day = self.next_operating(ready_day)
            if rng.random() < 0.1:
                day = self.next_operating(day)
            if checked_in.hour < 15:
                assigned_at = self.between(self.at(ready_day, 15, 30), self.at(ready_day, 17, 30))
            else:
                assigned_at = self.between(self.at(day, 6, 30), self.at(day, 7, 10))
            slot = _weighted(rng, zip(range(6), DELIVERY_SLOT_WEIGHTS))
            start, end = SLOTS[slot]
            courier = self.pick_courier(day, st.recipient)
            st.add(assigned_at, S.DELIVERY_ASSIGNED, courier=courier.user_id,
                   actor=self.logistician_on(assigned_at.date()).user_id, delivery_courier_id=courier.user_id,
                   delivery_date=day, delivery_window_start=start, delivery_window_end=end)

            if start.hour < 14:
                out_at = self.between(self.at(day, 7, 20), self.at(day, 8, 5))
            else:
                out_at = self.between(self.at(day, 13, 15), self.at(day, 13, 55))
            if rng.random() < 0.02 and out_at - assigned_at > timedelta(minutes=20):
                other = self.pick_courier(day, st.recipient, exclude=courier)
                if other is not courier:
                    when = self.between(max(assigned_at + timedelta(minutes=5), self.at(day, 6, 40)),
                                        out_at - timedelta(minutes=10))
                    courier = other
                    st.add(when, S.DELIVERY_ASSIGNED, courier=courier.user_id,
                           actor=self.logistician_on(when.date()).user_id, delivery_courier_id=courier.user_id)
            st.add(out_at, S.OUT_FOR_DELIVERY, courier=courier.user_id, actor=courier.user_id)
            last = out_at

            if rng.random() < 0.004:
                # Admin swap on the road (e.g. the vehicle broke down)
                other = self.pick_courier(day, st.recipient, exclude=courier)
                if other is not courier:
                    last = out_at + timedelta(minutes=rng.randint(20, 80))
                    courier = other
                    st.add(last, S.OUT_FOR_DELIVERY, courier=courier.user_id, actor=admin_id(last),
                           note=ADMIN_COURIER_NOTE, delivery_courier_id=courier.user_id)

            slot_start, slot_end = self.at(day, start.hour), self.at(day, end.hour)
            attempt_at = self.between(max(slot_start + timedelta(minutes=3), last + timedelta(minutes=10)),
                                      slot_end - timedelta(minutes=2))
            if rng.random() < (0.94 if failures == 0 else 0.75):
                st.add(attempt_at, S.DELIVERED, courier=courier.user_id, actor=courier.user_id)
                return
            failures += 1
            st.add(attempt_at, S.FAILED, courier=courier.user_id, actor=courier.user_id,
                   note=rng.choice(DELIVERY_FAIL_NOTES))
            if failures >= settings.MAX_FAILED_DELIVERIES:
                st.add(attempt_at, S.CANCELLED, actor=courier.user_id, note=f"{failures} sikertelen kézbesítés")
                return
            # Back to the warehouse, the logistician assigns a new delivery
            checked_in = self._check_in_time(day, attempt_at)
            st.add(checked_in, S.IN_WAREHOUSE, courier=courier.user_id,
                   actor=self.logistician_on(day).user_id, delivery_courier_id=None)


def materialize(story: Story, now: datetime) -> tuple[dict, list[dict]] | None:
    # Applies the steps that already happened, with the same rules as add_event
    row = {
        "status": None, "warehouse_id": None, "pickup_courier_id": None, "delivery_courier_id": None,
        "delivery_date": None, "delivery_window_start": None, "delivery_window_end": None,
        "picked_up_at": None, "warehouse_arrived_at": None, "out_for_delivery_at": None, "delivered_at": None,
    }
    events = []
    for when, status, courier, actor, note, changes in story.steps:
        if when > now:
            break
        row.update(changes)
        if status is None:
            continue
        occurred_at = _to_utc(when)
        if row["status"] != status:
            row["status"] = status
            for index, (milestone, column) in enumerate(MILESTONES):
                if milestone == status:
                    row[column] = occurred_at
                    for _, later in MILESTONES[index + 1:]:
                        row[later] = None
                    break
        events.append({"status": status.value, "occurred_at": occurred_at, "courier_id": courier,
                       "actor_id": actor, "note": note})
    if not events:
        return None
    row["status"] = row["status"].value
    row["size"] = story.size
    row["created_at"] = events[0]["occurred_at"]
    return row, events


def _chunks(items: list, size: int = 5000):
    for start in range(0, len(items), size):
        yield items[start:start + size]


def _demo_contacts():
    return select(Contact.id).where(func.lower(Contact.email).like(f"%{DEMO_SUFFIX}"))


def _test_users(db: Session) -> dict[UserRole, User]:
    found = {}
    for role, email in TEST_EMAILS.items():
        user = db.scalar(select(User).where(func.lower(User.email) == email, User.is_active.is_(True)))
        if user is not None and user.role == role:
            found[role] = user
    return found


def fill(db: Session, seed: int = 2026, now_local: datetime | None = None) -> dict:
    started = clock.perf_counter()
    warehouse = db.scalar(select(Warehouse).order_by(Warehouse.id).limit(1))
    if warehouse is None:
        raise SystemExit("Nincs raktár, előbb futtasd: python -m server.seed")
    has_demo = db.scalar(select(User.id).where(func.lower(User.email).like(f"%{DEMO_SUFFIX}")).limit(1))
    if has_demo is not None or db.scalar(_demo_contacts().limit(1)) is not None:
        raise SystemExit("Már vannak demo adatok. Előbb töröld őket: python -m server.seed_demo --remove")

    gen = Generator(seed, now_local or datetime.now(LOCAL).replace(tzinfo=None))
    gen.warehouse_id = warehouse.id
    test_users = _test_users(db)
    # Generated people must not collide with existing active emails (booking links them by email)
    gen.emails |= {email.lower() for email in db.scalars(select(User.email))}
    accounts = gen.build_accounts(test_users)

    password_hash = hash_pass(PASSWORD)
    # Same keys in every row (bulk insert)
    user_rows = [{
        "last_name": a.person.last_name, "first_name": a.person.first_name, "email": a.person.email,
        "password_hash": password_hash, "phone": a.person.phone, "role": a.role.value, "is_active": a.is_active,
        "postal_code": a.person.postal_code if a.has_address else None,
        "city": a.person.city if a.has_address else None,
        "street": a.person.street if a.has_address else None,
        "house_number": a.person.house_number if a.has_address else None,
    } for a in accounts]
    ids = db.scalars(insert(User).returning(User.id, sort_by_parameter_order=True), user_rows).all()
    for account, user_id in zip(accounts, ids):
        account.user_id = user_id

    gen.generate()
    parcels = []
    for story in gen.stories:
        result = materialize(story, gen.now)
        if result is not None:
            parcels.append((story, *result))
    parcels.sort(key=lambda item: item[1]["created_at"])

    # Capacity check over the whole history, existing parcels in the warehouse included
    existing_inside = db.scalar(select(func.count()).select_from(Parcel).where(
        Parcel.warehouse_id == warehouse.id, Parcel.status.in_(IN_WAREHOUSE_STATUSES)))
    timeline = sorted(
        (event["occurred_at"], order, index, event["status"])
        for order, (_, _, events) in enumerate(parcels) for index, event in enumerate(events)
    )
    inside, peak, last_status = existing_inside, existing_inside, {}
    inside_values = {s.value for s in IN_WAREHOUSE_STATUSES}
    for _, order, _, status in timeline:
        inside += (status in inside_values) - (last_status.get(order) in inside_values)
        last_status[order] = status
        peak = max(peak, inside)
    if peak > warehouse.capacity:
        raise SystemExit(f"A generált múlt túllépné a raktár kapacitását ({peak} > {warehouse.capacity})")

    taken = set(db.scalars(select(Parcel.tracking_number)))
    contact_rows, parcel_rows = [], []
    for story, row, _ in parcels:
        contact_rows.append(story.sender.contact(story.sender_acc.user_id if story.sender_acc else None))
        contact_rows.append(story.recipient.contact(story.recipient_acc.user_id if story.recipient_acc else None))
        while True:
            number = TRACKING_PREFIX + "".join(gen.rng.choice(TRACKING_ALPHABET) for _ in range(10))
            if number not in taken:
                taken.add(number)
                break
        row["tracking_number"] = number
        parcel_rows.append(row)
    contact_ids = []
    for chunk in _chunks(contact_rows):
        contact_ids += db.scalars(insert(Contact).returning(Contact.id, sort_by_parameter_order=True), chunk).all()
    for index, row in enumerate(parcel_rows):
        row["sender_id"], row["recipient_id"] = contact_ids[2 * index], contact_ids[2 * index + 1]
    parcel_ids = []
    for chunk in _chunks(parcel_rows):
        parcel_ids += db.scalars(insert(Parcel).returning(Parcel.id, sort_by_parameter_order=True), chunk).all()

    # Event ids follow the time, as in a live system
    event_rows = []
    for _, order, index, _ in timeline:
        event = dict(parcels[order][2][index])
        event["parcel_id"] = parcel_ids[order]
        event_rows.append(event)
    for chunk in _chunks(event_rows):
        db.execute(insert(ParcelEvent), chunk)
    db.commit()

    statuses = {}
    for row in parcel_rows:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    return {
        "from": gen.start, "to": gen.today, "users": len(accounts),
        "inactive": sum(not a.is_active for a in accounts),
        "test_accounts": sorted(user.email for user in test_users.values()),
        "parcels": len(parcel_rows), "events": len(event_rows), "statuses": statuses,
        "peak": peak, "capacity": warehouse.capacity,
        "sample_courier": next(c.person.email for c in gen.couriers if not c.existing and c.is_active),
        "sample_customer": max((c for c in gen.customers if c.is_active), key=lambda c: c.weight).person.email,
        "seconds": clock.perf_counter() - started,
    }


def remove(db: Session) -> dict:
    rows = db.execute(select(Parcel.id, Parcel.sender_id, Parcel.recipient_id).where(or_(
        Parcel.sender_id.in_(_demo_contacts()), Parcel.recipient_id.in_(_demo_contacts())))).all()
    parcel_ids = [row.id for row in rows]
    contact_ids = [contact_id for row in rows for contact_id in (row.sender_id, row.recipient_id)]
    for chunk in _chunks(parcel_ids):
        db.execute(delete(ParcelEvent).where(ParcelEvent.parcel_id.in_(chunk)))
        db.execute(delete(Parcel).where(Parcel.id.in_(chunk)))
    for chunk in _chunks(contact_ids):
        db.execute(delete(Contact).where(Contact.id.in_(chunk)))

    # Demo users still referenced by other parcels (e.g. assigned in the app) are kept
    demo_users = list(db.scalars(select(User.id).where(func.lower(User.email).like(f"%{DEMO_SUFFIX}"))))
    used = set()
    for column in (Parcel.pickup_courier_id, Parcel.delivery_courier_id, ParcelEvent.actor_id, ParcelEvent.courier_id):
        used |= set(db.scalars(select(column).where(column.in_(demo_users)).distinct()))
    deletable = sorted(set(demo_users) - used)
    for chunk in _chunks(deletable):
        db.execute(delete(User).where(User.id.in_(chunk)))
    db.commit()
    return {"parcels": len(parcel_ids), "users": len(deletable), "kept_users": len(used)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Két évnyi demo adat (felhasználók, csomagok, eseménynapló)")
    parser.add_argument("--remove", action="store_true", help="a generált demo adatok törlése")
    parser.add_argument("--seed", type=int, default=2026, help="véletlen mag (azonos mag, azonos adatok)")
    args = parser.parse_args()

    with DBSession() as db:
        if args.remove:
            result = remove(db)
            print(f"Törölve: {result['parcels']} csomag (eseményekkel, kapcsolattartókkal), "
                  f"{result['users']} felhasználó")
            if result["kept_users"]:
                print(f"Megtartva {result['kept_users']} demo felhasználó, mert más csomagok hivatkoznak rájuk")
            return
        result = fill(db, args.seed)

    print(f"Időszak: {result['from']:%Y. %m. %d.} – {result['to']:%Y. %m. %d.}")
    print(f"Felhasználók: {result['users']} új ({result['inactive']} inaktív), jelszó: {PASSWORD}")
    if result["test_accounts"]:
        print("A múltban részt vesz: " + ", ".join(result["test_accounts"]))
    print(f"Csomagok: {result['parcels']}, események: {result['events']}")
    for status, count in sorted(result["statuses"].items(), key=lambda item: -item[1]):
        print(f"  {status}: {count}")
    print(f"Raktár csúcsterhelése: {result['peak']} / {result['capacity']} csomag")
    print(f"Példa belépés: {result['sample_courier']} (futár), {result['sample_customer']} (ügyfél)")
    print(f"Kész, {result['seconds']:.1f} mp")


if __name__ == "__main__":
    main()
