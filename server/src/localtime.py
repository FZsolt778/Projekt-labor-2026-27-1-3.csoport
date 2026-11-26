from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("Europe/Budapest")


def day_start_utc(day: date) -> datetime:
    return datetime.combine(day, time.min, LOCAL_TZ).astimezone(timezone.utc).replace(tzinfo=None)


def local_date(moment: datetime) -> date:
    return moment.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ).date()


def local_today() -> date:
    return datetime.now(LOCAL_TZ).date()
