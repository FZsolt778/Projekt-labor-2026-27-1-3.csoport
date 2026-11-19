import logging
from pathlib import Path
from typing import Any
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema, MessageType
from server.src.config import settings

logger = logging.getLogger(__name__)
TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

_fastmail: FastMail | None = None


def _build_config() -> ConnectionConfig:
    return ConnectionConfig(
        MAIL_USERNAME=settings.SMTP_USER,
        MAIL_PASSWORD=settings.SMTP_PASSWORD.get_secret_value(),
        MAIL_FROM=settings.SMTP_FROM,
        MAIL_PORT=settings.SMTP_PORT,
        MAIL_SERVER=settings.SMTP_HOST,
        MAIL_FROM_NAME=settings.SMTP_FROM_NAME,
        MAIL_STARTTLS=settings.SMTP_STARTTLS,
        MAIL_SSL_TLS=settings.SMTP_SSL_TLS,
        USE_CREDENTIALS=settings.SMTP_USE_CREDENTIALS,
        VALIDATE_CERTS=True,
        TEMPLATE_FOLDER=TEMPLATES_DIR,
    )


def get_fastmail(*, force_reload: bool = False) -> FastMail:
    global _fastmail
    if _fastmail is None or force_reload:
        _fastmail = FastMail(_build_config())
    return _fastmail


def _deduplicate_recipients(recipients: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for email in recipients:
        cleaned = email.strip()
        key = cleaned.lower()
        if cleaned and key not in seen:
            seen.add(key)
            unique.append(cleaned)
    return unique


async def send_templated_email(
    recipients: list[str],
    subject: str,
    template_name: str,
    context: dict[str, Any],
) -> None:
    unique_recipients = _deduplicate_recipients(recipients)
    if not unique_recipients:
        return

    if not settings.SMTP_ENABLED and (_fastmail is None or not _fastmail.config.SUPPRESS_SEND):
        return

    try:
        fm = get_fastmail()
        if not settings.SMTP_ENABLED and not fm.config.SUPPRESS_SEND:
            return
        message = MessageSchema(
            subject=subject,
            recipients=unique_recipients,
            template_body=context,
            subtype=MessageType.html,
        )
        await fm.send_message(message, template_name=template_name)
    except Exception:
        logger.exception(
            "Nem sikerült az email küldése (subject=%r, recipients=%r)",
            subject,
            unique_recipients,
        )
