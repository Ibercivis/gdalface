"""
The personal area.

What `/user-profile/` says about who is signed in. Signing in with an Ibercivis
account is asserted in `gdalface/tests_ibercivis_account.py`, which is where the
fixtures below come from.
"""
# Each case's name is the sentence it asserts, so a docstring under it would
# say the same thing twice.
# pylint: disable=missing-function-docstring

from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import get_user_model
from django.test import TestCase

from gdalface.tests_ibercivis_account import IBERCIVIS_SAYS, visible_markup

User = get_user_model()


class ThePersonalAreaOfAnIbercivisAccount(TestCase):
    """Somebody who arrived from the shared sign-in service."""

    def setUp(self):
        self.account = User.objects.create_user(
            username="arrival", email=IBERCIVIS_SAYS["email"]
        )
        SocialAccount.objects.create(
            user=self.account, provider="ibercivis", uid=IBERCIVIS_SAYS["sub"]
        )
        self.client.force_login(self.account)

    def test_it_shows_the_identifier_the_ibercivis_account_is_known_by(self):
        page = self.client.get("/user-profile/")

        self.assertIn(IBERCIVIS_SAYS["sub"], visible_markup(page))


class ThePersonalAreaOfALocalAccount(TestCase):
    """Somebody who signs in with a password, as most accounts here do."""

    def setUp(self):
        self.account = User.objects.create_user(
            username="volunteer9", email="volunteer9@lostatnight.invalid"
        )
        self.client.force_login(self.account)

    def test_it_mentions_no_ibercivis_account(self):
        page = self.client.get("/user-profile/")

        self.assertNotIn("Ibercivis account", visible_markup(page))
