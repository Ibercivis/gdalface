"""
Which address the sign-in pages count against.

`django-allauth` allows so many failed sign-ins, password resets and
confirmation mails per client address, and 65.14.2 stopped trusting
`X-Forwarded-For` to say what that address is: anybody can send one, so
trusting it hands an attacker a fresh allowance per request.

Distrusting it entirely is no better here. Behind nginx every visitor arrives
from the proxy, so one address carries the whole site and ten failed sign-ins a
minute is an allowance strangers exhaust for each other. `settings.py` trusts
exactly one proxy, which is the deployment, and these cases are what that
means.
"""
# Each case's name is the sentence it asserts, so a docstring under it would
# say the same thing twice.
# pylint: disable=missing-function-docstring

from allauth.account.adapter import get_adapter
from django.test import RequestFactory, TestCase

# nginx, and the address it listens on behind.
PROXY = "127.0.0.1"

# Somebody signing in, as nginx sees them.
CLIENT = "203.0.113.7"

# What that somebody would rather be counted as.
FORGED = "198.51.100.1"


class TheAddressASignInIsCountedAgainst(TestCase):
    """What allauth's rate limits key on."""

    def counted(self, **headers):
        request = RequestFactory().get("/accounts/login/", REMOTE_ADDR=PROXY, **headers)
        return get_adapter().get_client_ip(request)

    def test_it_is_the_client_behind_the_proxy_rather_than_the_proxy(self):
        self.assertEqual(self.counted(HTTP_X_FORWARDED_FOR=CLIENT), CLIENT)

    def test_a_header_the_client_sent_itself_does_not_become_the_address(self):
        """nginx appends, so the address it saw is the last entry.

        A client that sends its own `X-Forwarded-For` only prepends to what
        arrives, and allauth reads from the right.
        """
        self.assertEqual(
            self.counted(HTTP_X_FORWARDED_FOR=f"{FORGED}, {CLIENT}"), CLIENT
        )

    def test_with_no_proxy_in_front_it_is_the_address_the_request_came_from(self):
        self.assertEqual(self.counted(), PROXY)
