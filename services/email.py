import smtplib
import ssl
from email.message import EmailMessage

class EmailService:
    def __init__(self, sender, receiver, password):
        self.sender = sender
        self.receiver = receiver
        self.password = password

    def send_alert(self, subject, body):
        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = self.sender
        msg["To"] = self.receiver

        try:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                server.login(self.sender, self.password)
                server.send_message(msg)
            return True, "Email sent!"
        except Exception as e:
            return False, f"Failed: {str(e)}"