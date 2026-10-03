"""
Send a bulk HTML email to all users with a verified email address.

Reusable for any campaign: pass an HTML file plus a subject; the command
substitutes the placeholders below per recipient and sends through the
configured EMAIL_BACKEND (Amazon SES in this project).

Placeholders inside the HTML:
    [first name]       -> user.first_name (falls back to "there" if empty)
    [unsubscribe_url]  -> personalised /newsletter/unsubscribe/<token>/ URL

If [unsubscribe_url] is missing from the HTML, a small GDPR-compliant
footer with the unsubscribe link is injected before </body>.

Examples
--------
    # 1. See who would get it (no mail sent):
    python manage.py send_bulk_email emails/file.html \\
        --subject "Workshop invite" --dry-run

    # 2. Send only to one address (must be verified):
    python manage.py send_bulk_email emails/file.html \\
        --subject "Workshop invite" --test-email frasanz@ibercivis.es

    # 3. Real bulk send:
    python manage.py send_bulk_email emails/file.html \\
        --subject "Workshop invite"
"""

import time
from pathlib import Path

from allauth.account.models import EmailAddress
from django.contrib.sites.models import Site
from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse
from django.utils.html import strip_tags

from user_profile.models import UserProfile


FIRST_NAME_PLACEHOLDER = "[first name]"
UNSUBSCRIBE_PLACEHOLDER = "[unsubscribe_url]"
FIRST_NAME_FALLBACK = "there"

INJECTED_FOOTER = """\
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#000000;">
  <tr>
    <td align="center" style="padding: 8px 24px 24px 24px;">
      <p style="margin:0; color:#7a8099; font-size:11px; line-height:1.55; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
        Don't want to receive these messages?
        <a href="[unsubscribe_url]" style="color:#9aa0b4; text-decoration:underline;">Unsubscribe</a>.
      </p>
    </td>
  </tr>
</table>
"""


class Command(BaseCommand):
    help = "Send a bulk HTML email to verified users (substitutes [first name] and [unsubscribe_url])."

    def add_arguments(self, parser):
        parser.add_argument("html_path", help="Path to the HTML file to send.")
        parser.add_argument("--subject", required=True, help="Email subject line.")
        parser.add_argument("--from-email", default=None,
                            help="From address (default: settings.DEFAULT_FROM_EMAIL).")
        parser.add_argument("--dry-run", action="store_true",
                            help="List recipients and exit without sending.")
        parser.add_argument("--test-email", default=None,
                            help="Send only to this address (must be a verified user).")
        parser.add_argument("--country", default=None,
                            help="Only users whose profile country is this ISO code (e.g. ES).")
        parser.add_argument("--exclude-country", default=None,
                            help="Skip users whose profile country is this ISO code.")
        parser.add_argument("--email-domain", default=None,
                            help="Only addresses ending with this (e.g. .es). Combined with --country as OR.")
        parser.add_argument("--exclude-email-domain", default=None,
                            help="Skip addresses ending with this. Combined with --exclude-country as OR.")
        parser.add_argument("--limit", type=int, default=None,
                            help="Cap the number of recipients (after filtering).")
        parser.add_argument("--sleep", type=float, default=0.1,
                            help="Seconds to sleep between sends (default 0.1 = ~10/s).")

    def handle(self, *args, **opts):
        html_path = Path(opts["html_path"])
        if not html_path.is_file():
            raise CommandError(f"HTML file not found: {html_path}")

        template_html = html_path.read_text(encoding="utf-8")

        if UNSUBSCRIBE_PLACEHOLDER not in template_html:
            if "</body>" not in template_html.lower():
                raise CommandError(
                    f"{UNSUBSCRIBE_PLACEHOLDER} not found and HTML has no </body> tag — "
                    "cannot inject the unsubscribe footer."
                )
            self.stdout.write(self.style.WARNING(
                f"{UNSUBSCRIBE_PLACEHOLDER} not found in HTML — injecting default footer before </body>."
            ))
            # Case-preserving replace on the first </body> occurrence.
            idx = template_html.lower().rfind("</body>")
            template_html = template_html[:idx] + INJECTED_FOOTER + template_html[idx:]

        subject = opts["subject"]
        from_email = opts["from_email"] or None  # None -> Django uses DEFAULT_FROM_EMAIL
        dry_run = opts["dry_run"]
        test_email = (opts["test_email"] or "").strip().lower() or None
        limit = opts["limit"]
        sleep_s = max(0.0, opts["sleep"])

        domain = Site.objects.get_current().domain.rstrip("/")
        scheme = "http" if domain.startswith(("localhost", "127.")) else "https"
        base_url = f"{scheme}://{domain}"

        qs = (
            EmailAddress.objects
            .filter(verified=True)
            .select_related("user")
            .order_by("user_id")
        )
        if test_email:
            qs = qs.filter(email__iexact=test_email)
            if not qs.exists():
                raise CommandError(
                    f"--test-email {test_email} is not a verified address."
                )

        # Audience filters: include = country OR e-mail domain; exclude likewise.
        inc_country = (opts.get("country") or "").upper() or None
        inc_domain = (opts.get("email_domain") or "").lower() or None
        exc_country = (opts.get("exclude_country") or "").upper() or None
        exc_domain = (opts.get("exclude_email_domain") or "").lower() or None
        countries = dict(UserProfile.objects.filter(user_id__in=[e.user_id for e in qs])
                         .values_list("user_id", "country")) if (inc_country or exc_country) else {}

        def matches(ea):
            c = str(countries.get(ea.user_id) or "").upper()
            d = ea.email.lower()
            if inc_country or inc_domain:
                if not ((inc_country and c == inc_country) or (inc_domain and d.endswith(inc_domain))):
                    return False
            if (exc_country and c == exc_country) or (exc_domain and d.endswith(exc_domain)):
                return False
            return True

        seen_user_ids = set()
        recipients = []
        for ea in qs:
            if ea.user_id in seen_user_ids or not matches(ea):
                continue
            seen_user_ids.add(ea.user_id)
            recipients.append(ea)
            if limit and len(recipients) >= limit:
                break

        total = len(recipients)
        self.stdout.write(self.style.NOTICE(
            f"Recipients: {total} | dry-run: {dry_run} | test-email: {test_email or '-'} "
            f"| from: {from_email or '(DEFAULT_FROM_EMAIL)'}"
        ))

        if dry_run:
            for ea in recipients:
                first_name = (ea.user.first_name or "").strip() or FIRST_NAME_FALLBACK
                self.stdout.write(f"  - {ea.email}  ({first_name})")
            self.stdout.write(self.style.SUCCESS(
                f"DRY RUN: would send {total} email(s). No mail sent."
            ))
            return

        connection = get_connection()
        connection.open()
        sent = 0
        failed = []

        try:
            for ea in recipients:
                user = ea.user
                profile, _created = UserProfile.objects.get_or_create(user=user)
                if not profile.newsletter_token:
                    profile.ensure_newsletter_token()
                    profile.save(update_fields=["newsletter_token"])

                unsubscribe_path = reverse(
                    "newsletter_unsubscribe", kwargs={"token": profile.newsletter_token}
                )
                unsubscribe_url = f"{base_url}{unsubscribe_path}"
                first_name = (user.first_name or "").strip() or FIRST_NAME_FALLBACK

                html_body = (
                    template_html
                    .replace(FIRST_NAME_PLACEHOLDER, first_name)
                    .replace(UNSUBSCRIBE_PLACEHOLDER, unsubscribe_url)
                )
                text_body = strip_tags(html_body)

                msg = EmailMultiAlternatives(
                    subject=subject,
                    body=text_body,
                    from_email=from_email,
                    to=[ea.email],
                    connection=connection,
                )
                msg.attach_alternative(html_body, "text/html")

                try:
                    msg.send()
                    sent += 1
                    if sent % 25 == 0 or sent == total:
                        self.stdout.write(f"  sent {sent}/{total}")
                except Exception as exc:  # noqa: BLE001 — we want to keep going
                    failed.append((ea.email, str(exc)))
                    self.stderr.write(self.style.ERROR(f"  FAIL {ea.email}: {exc}"))

                if sleep_s:
                    time.sleep(sleep_s)
        finally:
            connection.close()

        style = self.style.SUCCESS if not failed else self.style.WARNING
        self.stdout.write(style(f"Done. Sent: {sent}  Failed: {len(failed)}"))
        if sent and not test_email:
            # Mark the mailing on the staff panel charts so its effect can be read.
            try:
                from georeferencing.models import StatsEvent
                StatsEvent.objects.create(
                    kind='email', title=f'Mailing sent: {subject}',
                    note=f'{sent} sent, {len(failed)} failed. Template: {opts["html_path"]}',
                )
            except Exception:
                pass
        for email, err in failed:
            self.stdout.write(f"  failed: {email} — {err}")
