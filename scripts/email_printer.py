#!/usr/bin/env python

import cups
import codecs
from datetime import datetime
import imaplib
import logging
import os
import shutil
import smtplib
import subprocess
import time

from gmail import Gmail

PRINTER_NAME = "EPSON"

REPOSITORY = os.path.join(os.path.expanduser("~"), "code", "pipy_printer")

LOG = os.path.join(os.path.expanduser("~"), "Documents", "email.log")

PRINT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "print")

CREDENTIALS = os.path.join(os.path.expanduser("~"), "Documents", "sintonia.txt")

REPORT = """\
From: {}
To: {}
Subject: {}


{}
--
Raspberry Pi 3
"""

def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class EmailPrinter(object):
    def __init__(self):
        self.error_state = False
        self.counter = 1
        with open(CREDENTIALS, "r") as handle:
            lines = [line.rstrip("\n") for line in handle]
            self.email = lines[0]
            self.user = self.email.split("@")[0]
            self.password = lines[1]
            self.friends = lines[2:]
            self.gmail = None
            self.printer = None

    def login(self):
        if not self.gmail or not self.gmail.logged_in:
            logging.info("Logging in to Gmail.")
            self.gmail = Gmail()
            self.gmail.login(self.user, self.password)
        return self.gmail.logged_in

    def logout(self):
        if self.gmail and self.gmail.logged_in:
            logging.info("Logging out of Gmail.")
            self.gmail.logout()
        self.gmail = None

    def hourly_loop(self):
        logging.info("Initiating hourly loop.")
        shutil.rmtree(PRINT_DIR)
        os.makedirs(PRINT_DIR)
        self.printer = cups.Connection()
        self.printer.setPrinterErrorPolicy(PRINTER_NAME, "abort-job")
        logging.debug("Printer connection established.")
        self._iterate(retry = 3)
        for i in xrange(3):  # every ~15 mins
            time.sleep(14 * 60)
            self._iterate(retry = 3)
        self.logout()
        self.printer = None

    def send_report(self):
        body = "Error report"
        with open(LOG, "r") as f:
            body = f.read()
        self._send_email("Traceback " + now_string(), body)

    def _iterate(self, retry = 0):
        if self.login():
            try:
                logging.debug("Iterating at {}".format(now_string()))
                self._prepare_printer()
                self._fetch_friend_messages()
            except imaplib.IMAP4.abort as ia:
                self.logout()
                if retry > 0:
                    self._iterate(retry = retry - 1)
                else:
                    self.error_state = True
                    logging.exception("IMAP abort during iteration.")
            except Exception as e:
                self.error_state = True
                logging.exception("Exception during iteration.")

    def _fetch_friend_messages(self):
        logging.info("Fetching friend messages.")
        for friend in self.friends:
            logging.debug("Fetching messages for {}".format(friend))
            msgs = self.gmail.inbox().mail(unread = True, sender = friend)
            if msgs:
                for msg in msgs:
                    msg.fetch()
                    self._execute_friend_command(msg)
                    self._print_message(msg)
            else:
                logging.debug("No messages to download.")

    def _execute_friend_command(self, msg):
        if msg.subject:
            if msg.subject.startswith("[cmd]"):
                cmd = msg.subject[6:].strip()
                logging.debug("Executing {}".format(cmd))
                code = subprocess.call(cmd, shell = True)
                if code == 0:
                    logging.info("Friend command executed successfully.")
                else:
                    self.error_state = True
                    logging.warning("Friend command returned {}.".format(code))
            elif msg.subject.startswith("[ping]"):
                self._send_email("[pong]", now_string())
            msg.read()

    def _print_message(self, msg):
        if msg.subject and msg.subject.startswith("[bot]"):
            logging.debug("Found message: {}".format(msg.subject))
            if msg.body:
                fid = os.path.join(PRINT_DIR, str(self.counter) + ".txt")
                logging.debug("Writing message body to {}".format(fid))
                self.counter += 1
                with codecs.open(fid, "w", encoding = "utf-8") as f:
                    f.write(unicode(msg.body, "utf-8").strip())
                self.printer.printFile(PRINTER_NAME, fid, "PYTHON GMAIL", {})
                time.sleep(8)
            for attachment in msg.attachments:
                if not attachment.name is None:
                    attachment.name = "".join(attachment.name.split())
                    fid = os.path.join(PRINT_DIR, attachment.name)
                    logging.debug("Found attachment {}".format(attachment.name))
                    attachment.save(PRINT_DIR)
                    self.printer.printFile(PRINTER_NAME, fid, "PYTHON GMAIL", {})
                    time.sleep(5)
            msg.read()

    def _prepare_printer(self):
        logging.info("Checking printer status.")
        try:
            self.printer.cancelAllJobs(name = PRINTER_NAME)
            self.printer.acceptJobs(PRINTER_NAME)
            """
            status = subprocess.check_output("/usr/bin/lpq")
            if "EPSON is not ready" in status:
                logging.warning("Printer is not ready!")
                logging.info("Resuming printer...")
                code = subprocess.call(["/usr/bin/cancel", "-a", PRINTER_NAME])
                if code == 0:
                    logging.debug("Cancelled all printer jobs.")
                else:
                    logging.warning("cancel returned {}.".format(code))
                code = subprocess.call(["/usr/sbin/cupsenable", PRINTER_NAME])
                if code == 0:
                    logging.debug("CUPS printer enabled.")
                else:
                    logging.warning("cupsenable returned {}.".format(code))
            """
        except Exception as e:
            self.error_state = True
            logging.exception("Exception when checking printer status.")

    def _send_email(self, subject, body):
        try:
            server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
            server.ehlo()
            server.login(self.email, self.password)
            for friend in self.friends:
                email = REPORT.format(self.email, friend, subject, body)
                server.sendmail(self.email, friend, email)
            server.close()
        except Exception as e:
            self.error_state = True
            logging.exception("Exception when sending email.")


def self_update():
    wd = os.getcwd()
    os.chdir(REPOSITORY)
    subprocess.call(["/usr/bin/git", "pull"])
    os.chdir(wd)


def main():
    has_previous = os.path.isfile(LOG)
    email_printer = EmailPrinter()
    init_error = None
    try:
        if has_previous:
            email_printer.send_report()
            os.remove(LOG)
    except Exception as e:
        try:
            email_printer._send_email("Initialization error", str(e))
        except Exception as ee:
            return 1
    logging.basicConfig(filename = LOG, level = logging.DEBUG)
    logging.info("Initialization complete.")
    try:
        email_printer.hourly_loop()
        logging.info("Hourly loop complete.")
    except Exception as e:
        logging.exception("Uncaught exception.")
        email_printer.error_state = True
    finally:
        logging.shutdown()
        email_printer.logout()
        if not email_printer.error_state:
            os.remove(LOG)
    self_update()


if __name__ == "__main__":
    main()
