#!/usr/bin/env python3
"""
test.py - simple synchronous runner to test utils.mailer.SimpleMailer

Usage examples:
  # dry run (no SMTP credentials needed)
  python test.py --to you@example.com --dry-run

  # real send (set SMTP_USER/SMTP_PASS in env or pass via CLI)
  python test.py --to you@example.com --email your-email@gmail.com --password your-app-password

Environment variables supported (used if CLI args missing):
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, TEST_TO
"""

import os
import sys
import argparse
from dotenv import load_dotenv

load_dotenv()

from utils.mailer import SimpleMailer


def build_parser():
    p = argparse.ArgumentParser(description="Send a test email using utils.mailer.SimpleMailer")
    p.add_argument("--to", "-t", help="Recipient email address", required=False)
    p.add_argument("--email", "-e", help="Sender email address (overrides SMTP_USER env)", required=False)
    p.add_argument("--password", "-p", help="Sender email password (or app password)", required=False)
    p.add_argument("--host", help="SMTP host (default from env or smtp.gmail.com)", default=os.getenv('SMTP_HOST', 'smtp.gmail.com'))
    p.add_argument("--port", type=int, help="SMTP port (default from env or 587)", default=int(os.getenv('SMTP_PORT', 587)))
    p.add_argument("--subject", help="Email subject", default="upwork_api test message")
    p.add_argument("--body", help="Email body", default="This is a test message from upwork_api SimpleMailer")
    p.add_argument("--dry-run", action="store_true", help="Don't actually send, just print the message")
    p.add_argument("--cc", help="CC recipients (comma-separated)", default=None)
    p.add_argument("--bcc", help="BCC recipients (comma-separated)", default=None)
    p.add_argument("--html", action="store_true", help="Treat body as HTML")
    p.add_argument("--attachments", help="Comma-separated file paths to attach", default=None)
    return p


def parse_list(s: str | None):
    if not s:
        return None
    return [x.strip() for x in s.split(',') if x.strip()]


def main():
    parser = build_parser()
    args = parser.parse_args()

    recipient = args.to or os.getenv('TEST_TO')
    print("Recipient:", recipient)
    sender = args.email or os.getenv('SMTP_USER')
    print("Sender:", sender)
    password = args.password or os.getenv('SMTP_PASS')
    host = args.host
    port = args.port

    if not recipient and not args.dry_run:
        print("Error: recipient not specified. Provide --to or set TEST_TO/TO env var, or use --dry-run.")
        return 1

    if (not sender or not password) and not args.dry_run:
        print("Error: sender email or password not provided. Use --email/--password or set SMTP_USER/SMTP_PASS env vars.")
        return 1

    cc = parse_list(args.cc) or None
    bcc = parse_list(args.bcc) or None
    attachments = parse_list(args.attachments) or None

    print("SMTP Host:", host)
    print("SMTP Port:", port)
    print("From:", sender)
    print("To:", recipient)
    if cc:
        print("CC:", cc)
    if bcc:
        print("BCC:", bcc)
    if attachments:
        print("Attachments:", attachments)

    if args.dry_run:
        print("Dry-run: not sending email")
        return 0

    mailer = SimpleMailer(smtp_host=host, smtp_port=port, email=sender, password=password)
    success = mailer.send(
        to=recipient,
        subject=args.subject,
        body=args.body,
        cc=cc,
        bcc=bcc,
        html=args.html,
        attachments=attachments,
    )

    if success:
        print("OK: email(s) sent")
        return 0
    else:
        print("ERROR: sending failed")
        return 2


if __name__ == '__main__':
    sys.exit(main())