#!/usr/bin/env python

from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
import os
import sys
import smtplib

EMAIL_LOG = os.path.join(os.path.expanduser("~"), "Documents", "email.log")
PRINTER_LOG = os.path.join(os.path.expanduser("~"), "Documents", "printer.log")

CREDENTIALS = os.path.join(os.path.expanduser("~"), "Documents", "sintonia.txt")

TOKEN = os.path.join(os.path.expanduser("~"), "Documents", "pipy_printer_token.txt")

SIGNATURE = """\
--
Raspberry Pi 3 (v0.1)
"""


class LogReporter(object):
    def __init__(self):
        self.email = None
        self.friends = []
        self.server = None

    # https://stackoverflow.com/a/3363254
    def send_report(self):
        msg = MIMEMultipart()
        msg["From"] = self.email
        msg["To"] = COMMASPACE.join(self.friends)
        msg["Date"] = formatdate(localtime=True)
        msg["Subject"] = "Error report"
        msg.attach(MIMEText(SIGNATURE))
        for filepath in (EMAIL_LOG, PRINTER_LOG):
            filename = os.path.basename(filepath)
            with open(filepath, "rb") as f:
                part = MIMEApplication(f.read(), Name=filename)
            part["Content-Disposition"] = 'attachment; filename="{}"'.format(filename)
            msg.attach(part)
        server.sendmail(self.email, self.friends, msg.as_string())

    def login(self):
        with open(CREDENTIALS, "r") as handle:
            lines = [line.rstrip("\n") for line in handle]
        self.email = lines[0]
        password = lines[1]
        self.friends = lines[2:]
        self.server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        self.server.ehlo()
        self.server.login(self.email, password)

    def logout(self):
        if self.server is not None:
            self.server.close()
        self.server = None

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.logout()


def main():
    if os.path.isfile(TOKEN):
        try:
            with LogReporter() as reporter:
                reporter.send_report()
        except Exception as e:
            return 1
        finally:
            os.remove(TOKEN)
            os.remove(EMAIL_LOG)
            os.remove(PRINTER_LOG)
    return 0


if __name__ == "__main__":
    sys.exit(main())
