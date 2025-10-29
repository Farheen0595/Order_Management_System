import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from app.config.settings import settings



SENDGRID_API_KEY = settings.SENDGRID_API_KEY


def send_order_email(to_email, subject, body):
    message = Mail(
        from_email="sdfarheen05@gmail.com",
        to_emails=to_email,
        subject=subject,
        html_content=f"<strong>{body}</strong>"
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(f"✅ Email sent! Status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")



if __name__ == '__main__':


    send_order_email("sdfarheen05@gmail.com","Order Confirmation","Order Confirmed")