"""Email service for sending SMTP emails."""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent.parent / "notifications" / "templates"
_jinja_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)


class EmailService:
    def __init__(self) -> None:
        self._settings = get_settings()

    def _is_configured(self) -> bool:
        return bool(
            self._settings.smtp_host
            and self._settings.smtp_port
            and self._settings.smtp_from_email
        )

    def render_template(self, template_name: str, **context: str) -> str:
        template = _jinja_env.get_template(template_name)
        return template.render(**context)

    def send_html(
        self,
        to_email: str,
        subject: str,
        html_body: str,
    ) -> dict:
        if not self._is_configured():
            logger.info(
                "SMTP not configured — email skipped (to=%s, subject=%s)",
                to_email,
                subject,
            )
            return {"status": "skipped", "reason": "smtp_not_configured"}

        from_email = self._settings.smtp_from_email
        from_name = self._settings.smtp_from_name

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name} <{from_email}>"
        msg["To"] = to_email

        msg.attach(MIMEText(html_body, "html"))

        try:
            with smtplib.SMTP(self._settings.smtp_host, self._settings.smtp_port, timeout=10) as server:
                if self._settings.smtp_port == 587:
                    server.starttls()
                if self._settings.smtp_user and self._settings.smtp_password:
                    server.login(self._settings.smtp_user, self._settings.smtp_password)
                server.sendmail(from_email, [to_email], msg.as_string())

            logger.info("Email sent successfully: to=%s subject=%s", to_email, subject)
            return {"status": "sent", "to": to_email}
        except smtplib.SMTPException as exc:
            logger.exception("SMTP error sending email to %s", to_email)
            raise
        except Exception as exc:
            logger.exception("Unexpected error sending email to %s", to_email)
            raise
