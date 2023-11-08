import smtplib
import os
from dotenv import load_dotenv


def send_letter(result, to_email):
    try:
        load_dotenv()
        email = os.getenv("EMAIl")
        password = os.getenv("EMAIl_PASSWORD")

        server = smtplib.SMTP('smtp.yandex.com', 587)
        server.starttls()
        server.login(email, password)

        subject = "Pok"
        body = result
        msg = 'From: {}\r\nTo: {}\r\nSubject: {}\n\n{}'.format(
            email, to_email, subject, body
        )
        server.sendmail(email, to_email, msg)
        server.quit()
        return 0
    except Exception as e:
        print(e)
        return e
