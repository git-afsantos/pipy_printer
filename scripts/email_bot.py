#!/usr/bin/env python

import imaplib
import logging
import os
import smtplib
import subprocess
import sys

from gmail import Gmail

PRINT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "print")

LOG = os.path.join(os.path.expanduser("~"), "Documents", "email.log")

CREDENTIALS = os.path.join(os.path.expanduser("~"), "Documents", "sintonia.txt")

TOKEN = os.path.join(os.path.expanduser("~"), "Documents", "pipy_printer_token.txt")

STATUS_ERROR = "1"


EMAIL_TEXT = """\
From: "{}" <{}>
To: {}
Subject: {}


{}
--
Raspberry Pi 3 (v0.1)
"""


class EmailSender(object):
    def __init__(self, email, user="Raspberry Pi 3"):
        self.user = user
        self.email = email
        self.server = None
        self.logged_in = False

    def login(self, password):
        logging.debug("Logging in to SMTP server with " + self.email)
        self.server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        self.server.ehlo()
        self.server.login(self.email, self.password)
        self.logged_in = True

    def logout(self):
        logging.debug("Logging out of SMTP server.")
        self.server.close()
        self.server = None

    def send(self, dest, subject, body):
        logging.debug("Sending email to " + dest)
        email = EMAIL_TEXT.format(self.user, self.email, dest, subject, body)
        return self.server.sendmail(self.email, dest, email)


class EmailBot(object):
    def __init__(self):
        self.email = None
        self.friends = []
        self.gmail = None
        self.outbox = None

    @property
    def logged_in(self):
        return (self.gmail and self.gmail.logged_in
                and self.outbox and self.outbox.logged_in)

    def login(self):
        with open(CREDENTIALS, "r") as handle:
            lines = [line.rstrip("\n") for line in handle]
        self.email = lines[0]
        gmail_user = self.email.split("@")[0]
        password = lines[1]
        self.friends = lines[2:]
        logging.info("Logging in to Gmail.")
        self.gmail = Gmail()
        self.gmail.login(gmail_user, password)
        self.outbox = EmailSender(self.email)
        self.outbox.login(password)
        return self.gmail.logged_in and self.outbox.logged_in

    def logout(self):
        if self.gmail and self.gmail.logged_in:
            logging.info("Logging out of Gmail.")
            self.gmail.logout()
        self.gmail = None
        if self.outbox and self.outbox.logged_in:
            self.outbox.logout()
        self.outbox = None

    def fetch_messages(self):
        logging.info("Fetching messages from inbox.")
        n = 0
        for friend in self.friends:
            logging.debug("Fetching messages for {}".format(friend))
            msgs = self.gmail.inbox().mail(unread=True, sender=friend)
            for msg in msgs:
                msg.fetch()
                if not msg.subject:
                    continue
                logging.debug("Found message: {}".format(msg.subject))
                n += 1
                if msg.subject.startswith("[cmd]"):
                    self._execute_friend_command(friend, msg)
                elif msg.subject.startswith("[ping]"):
                    self.outbox.send(friend, "[pong]", "")
                    msg.read()
                elif msg.subject.startswith("[bot]"):
                    self._save_message(msg)
                else:
                    logging.debug("Ignored message.")
        logging.info("Fetched {} messages.".format(n))
        return n

    def _execute_friend_command(self, friend, msg):
        cmd = msg.subject[6:].strip()
        logging.debug("Executing {}".format(cmd))
        try:
            output = subprocess.check_output(cmd, shell=True)
            logging.info("Friend command executed successfully.")
            self.outbox.send(friend, "Re: " + msg.subject, output)
        except subprocess.CalledProcessError as e:
            logging.error("Friend command raised an error: " + repr(e))
            logging.debug("Error code: " + str(e.returncode))
            logging.debug("Output:\n" + e.output)
        msg.read()

    def _save_message(self, msg):
        for attachment in msg.attachments:
            if not attachment.name is None:
                attachment.name = "".join(attachment.name.split())
                logging.debug("Found attachment: " + attachment.name)
                attachment.save(PRINT_DIR)
                filepath = os.path.join(PRINT_DIR, attachment.name)
                logging.debug("Saved attachment at: " + filepath)
        msg.read()

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.logout()


def write_token(status=STATUS_ERROR):
    with open(TOKEN, "w") as f:
        f.write(status)


def main():
    logging.basicConfig(filename=LOG, filemode="a", level=logging.DEBUG)
    logging.info("Starting email fetcher.")
    try:
        with EmailBot() as bot:
            if bot.logged_in:
                bot.fetch_messages()
            else:
                logging.error("Unable to log in.")
    except imaplib.IMAP4.abort as ia:
        logging.exception("IMAP abort: " + repr(ia))
        return 1
    except Exception as e:
        logging.exception("Uncaught exception: " + repr(e))
        write_token()
        return 1
    finally:
        logging.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
