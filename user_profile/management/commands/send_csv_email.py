"""
Send a bulk HTML email to a plain list of addresses read from a CSV file.

Unlike `send_bulk_email`, this command does NOT touch the database: recipients
are taken straight from the CSV, so it is meant for external lists (e.g. people
who registered for an event via Zoom but never created an account on the site).

CSV format
----------
One address per line, in the FIRST column. Extra columns and a leading blank
line are ignored. Example (semicolon-separated, as exported):

    ;;
    alice@example.org;;
    bob@example.com;;

Placeholders inside the HTML (optional)
---------------------------------------
    [first name]  -> "there" (we have no names for these recipients)

A small unsubscribe/contact footer (mailto) is injected before </body> if the
HTML does not already contain one.

Examples
--------
    # 1. See who would get it (no mail sent):
    python manage.py send_csv_email emails/email_21_05_reminder.html \\
        --csv "emails/registrados lost at night.csv" \\
        --subject "Reminder: Lost at Night workshop is tomorrow" --dry-run

    # 2. Send only to one address:
    python manage.py send_csv_email emails/email_21_05_reminder.html \\
        --csv "emails/registrados lost at night.csv" \\
        --subject "Reminder: Lost at Night workshop is tomorrow" \\
        --test-email frasanz@ibercivis.es

    # 3. Real bulk send:
    python manage.py send_csv_email emails/email_21_05_reminder.html \\
        --csv "emails/registrados lost at night.csv" \\
        --subject "Reminder: Lost at Night workshop is tomorrow"
"""

import re
import time
from pathlib import Path

from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.management.base import BaseCommand, CommandError
from django.utils.html import strip_tags


FIRST_NAME_PLACEHOLDER = "[first name]"
FIRST_NAME_FALLBACK = "there"

UNSUBSCRIBE_EMAIL = "contact@lostatnight.org"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

INJECTED_FOOTER = """\
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#000000;">
  <tr>
    <td align="center" style="padding: 8px 24px 24px 24px;">
      <p style="margin:0; color:#7a8099; font-size:11px; line-height:1.55; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
        Don't want to receive these messages?
        <a href="mailto:__UNSUB__?subject=Unsubscribe" style="color:#9aa0b4; text-decoration:underline;">Unsubscribe</a>.
      </p>
    </td>
  </tr>
</table>
""".replace("__UNSUB__", UNSUBSCRIBE_EMAIL)


class Command(BaseCommand):
    help = "Send a bulk HTML email to a list of addresses read from a CSV file (no DB lookup)."

    def add_arguments(self, parser):
        parser.add_argument("html_path", help="Path to the HTML file to send.")
        parser.add_argument("--csv", required=True, help="Path to the CSV file with recipient addresses.")
        parser.add_argument("--subject", required=True, help="Email subject line.")
        parser.add_argument("--from-email", default=None,
                            help="From address (default: settings.DEFAULT_FROM_EMAIL).")
        parser.add_argument("--dry-run", action="store_true",
                            help="List recipients and exit without sending.")
        parser.add_argument("--test-email", default=None,
                            help="Send only to this address (does not need to be in the CSV).")
        parser.add_argument("--limit", type=int, default=None,
                            help="Cap the number of recipients (after filtering).")
        parser.add_argument("--sleep", type=float, default=0.1,
                            help="Seconds to sleep between sends (default 0.1 = ~10/s).")

    def _read_recipients(self, csv_path):
        """Return a de-duplicated, order-preserving list of valid addresses."""
        raw = csv_path.read_text(encoding="utf-8", errors="replace")
        recipients, skipped, seen = [], [], set()
        for line in raw.splitlines():
            cell = line.split(";")[0].split(",")[0].strip().strip('"').strip()
            if not cell:
                continue
            if not EMAIL_RE.match(cell):
                skipped.append(cell)
                continue
            key = cell.lower()
            if key in seen:
                continue
            seen.add(key)
            recipients.append(cell)
        return recipients, skipped

    def handle(self, *args, **opts):
        html_path = Path(opts["html_path"])
        if not html_path.is_file():
            raise CommandError(f"HTML file not found: {html_path}")
        csv_path = Path(opts["csv"])
        if not csv_path.is_file():
            raise CommandError(f"CSV file not found: {csv_path}")

        template_html = html_path.read_text(encoding="utf-8")

        # Inject an unsubscribe/contact footer if none is present.
        if "unsubscribe" not in template_html.lower():
            if "</body>" not in template_html.lower():
                raise CommandError(
                    "No unsubscribe link found and HTML has no </body> tag — "
                    "cannot inject the unsubscribe footer."
                )
            self.stdout.write(self.style.WARNING(
                "No unsubscribe link found in HTML — injecting default mailto footer before </body>."
            ))
            idx = template_html.lower().rfind("</body>")
            template_html = template_html[:idx] + INJECTED_FOOTER + template_html[idx:]

        subject = opts["subject"]
        from_email = opts["from_email"] or None  # None -> Django uses DEFAULT_FROM_EMAIL
        dry_run = opts["dry_run"]
        test_email = (opts["test_email"] or "").strip().lower() or None
        limit = opts["limit"]
        sleep_s = max(0.0, opts["sleep"])

        recipients, skipped = self._read_recipients(csv_path)
        if skipped:
            self.stdout.write(self.style.WARNING(
                f"Skipped {len(skipped)} line(s) that did not look like an email: "
                + ", ".join(skipped[:10]) + (" …" if len(skipped) > 10 else "")
            ))

        if test_email:
            recipients = [test_email]
        elif limit:
            recipients = recipients[:limit]

        total = len(recipients)
        self.stdout.write(self.style.NOTICE(
            f"Recipients: {total} | dry-run: {dry_run} | test-email: {test_email or '-'} "
            f"| from: {from_email or '(DEFAULT_FROM_EMAIL)'} | subject: {subject!r}"
        ))

        if dry_run:
            for email in recipients:
                self.stdout.write(f"  - {email}")
            self.stdout.write(self.style.SUCCESS(
                f"DRY RUN: would send {total} email(s). No mail sent."
            ))
            return

        # Body is identical for every recipient (no per-user personalisation).
        html_body = template_html.replace(FIRST_NAME_PLACEHOLDER, FIRST_NAME_FALLBACK)
        text_body = strip_tags(html_body)

        connection = get_connection()
        connection.open()
        sent = 0
        failed = []

        try:
            for email in recipients:
                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=text_body,
                    from_email=from_email,
                    to=[email],
                    connection=connection,
                )
                msg.attach_alternative(html_body, "text/html")
                try:
                    msg.send()
                    sent += 1
                    if sent % 25 == 0 or sent == total:
                        self.stdout.write(f"  sent {sent}/{total}")
                except Exception as exc:  # noqa: BLE001 — keep going on individual failures
                    failed.append((email, str(exc)))
                    self.stderr.write(self.style.ERROR(f"  FAIL {email}: {exc}"))

                if sleep_s:
                    time.sleep(sleep_s)
        finally:
            connection.close()

        style = self.style.SUCCESS if not failed else self.style.WARNING
        self.stdout.write(style(f"Done. Sent: {sent}  Failed: {len(failed)}"))
        for email, err in failed:
            self.stdout.write(f"  failed: {email} — {err}")
