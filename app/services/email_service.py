from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.config.settings import settings

async def send_email(to: str, subject: str, body: str):
    message = Mail(
        from_email="sdfarheen@example.com",
        to_emails=to,
        subject=subject,
        plain_text_content=body
    )
    try:
        sg = SendGridAPIClient(settings.EMAIL_API_KEY)
        sg.send(message)
        return True
    except Exception as e:
        print(e)
        return False
