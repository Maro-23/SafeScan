import threading
import smtplib
import ssl
from email.message import EmailMessage
from tkinter import Label

class EmailService:
    def __init__(self, sender, receiver, password, status_label=None):
        self.sender = sender
        self.receiver = receiver
        self.password = password
        self.status_label = status_label

    def _update_status(self, message, color):
        if self.status_label:
            self.status_label.config(text=message, fg=color)
            self.status_label.master.update_idletasks()

    def send_alert(self, subject, body):
        """Thread-safe email sending with UI updates"""
        def _send_thread():
            try:
                self._update_status("Sending...", "blue")
                
                msg = EmailMessage()
                msg.set_content(body)
                msg["Subject"] = subject
                msg["From"] = self.sender
                msg["To"] = self.receiver

                context = ssl.create_default_context()
                with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
                    server.login(self.sender, self.password)
                    server.send_message(msg)
                
                self._update_status("Email sent!", "green")
                print(f"Email sent")
            except Exception as e:
                self._update_status(f"Failed: {str(e)}", "red")
            finally:
                if self.status_label:
                    self.status_label.after(3000, lambda: self._update_status("", "black"))

        threading.Thread(target=_send_thread, daemon=True).start()