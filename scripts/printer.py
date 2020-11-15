#!/usr/bin/env python

import cups
import logging
import os
import shutil
import socket
# import subprocess
import sys
import time

PROC_NAME = "gmail"

PRINTER_NAME = "EPSON"

LOG = os.path.join(os.path.expanduser("~"), "Documents", "printer.log")

PRINT_DIR = os.path.join(os.path.expanduser("~"), "Documents", "print")

TOKEN = os.path.join(os.path.expanduser("~"), "Documents", "pipy_printer_token.txt")

STATUS_ERROR = "1"


def write_token(status=STATUS_ERROR):
    with open(TOKEN, "w") as f:
        f.write(status)


def connect_printer():
    logging.info("Connecting to printer.")
    printer = cups.Connection()
    printer.setPrinterErrorPolicy(PRINTER_NAME, "abort-job")
    logging.info("Printer connection established.")
    return printer


def prepare_printer(printer):
    logging.info("Checking printer status.")
    printer.cancelAllJobs(name=PRINTER_NAME)
    printer.acceptJobs(PRINTER_NAME)
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


# https://unix.stackexchange.com/a/63707
def print_files(printer):
    logging.info("Printing pending files.")
    for filename in os.listdir(PRINT_DIR):
        filepath = os.path.join(PRINT_DIR, filename)
        if os.path.isfile(filepath):
            logging.debug("Printing file: " + filepath)
            jobid = printer.printFile(PRINTER_NAME, filepath, PROC_NAME, {})
            while printer.getJobs().get(jobid, None) is not None:
                time.sleep(5)
            os.remove(filepath)
            logging.debug("Printed: " + filepath)
    logging.info("Printed all pending files.")


def main():
    # https://stackoverflow.com/a/7758075
    the_socket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        # The null byte (\0) means the socket is created
        # in the abstract namespace instead of being created
        # on the file system itself.
        # Works only in Linux.
        the_socket.bind("\0" + PROC_NAME)
    except socket.error:
        # lock exists
        return 1
    logging.basicConfig(filename=LOG, filemode="a", level=logging.DEBUG)
    try:
        printer = connect_printer()
        prepare_printer(printer)
        print_files(printer)
    except Exception as e:
        logging.exception("Uncaught exception: " + repr(e))
        write_token()
        return 1
    finally:
        logging.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
