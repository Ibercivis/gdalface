"""
Signing in with an Ibercivis account.

Lost at Night accepts a second way in: the shared sign-in service the Ibercivis
citizen science sites use. These tests cover what that costs the sign-in pages
the site already had — the local sign-up form is closed, and the
email-and-password sign-in is untouched — and what arriving from Ibercivis
leaves behind in the database.

They are deliberately offline: no case here talks to the sign-in service. What
they assert is this site's own behaviour, given an Ibercivis account
configured. Signing in for real is exercised by hand, and the end-to-end test that drives
two sites in a browser lives with the sign-in service.
"""
# Each case's name is the sentence it asserts, so a docstring under it would
# say the same thing twice.
# pylint: disable=missing-function-docstring

import re

from allauth.account.models import EmailAddress
from allauth.core import context
from allauth.socialaccount.adapter import get_adapter as get_social_adapter
from allauth.socialaccount.helpers import complete_social_login
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth import SESSION_KEY, get_user_model
from django.contrib.auth.middleware import AuthenticationMiddleware
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core import mail
from django.core.cache import cache
from django.test import RequestFactory, TestCase, override_settings

User = get_user_model()

NEWCOMER = {
    "email": "newcomer@lostatnight.invalid",
    "password1": "a-password-nobody-uses",
    "password2": "a-password-nobody-uses",
}


IBERCIVIS_ACCOUNT = {
    "openid_connect": {
        "SCOPE": ["openid", "email"],
        "OAUTH_PKCE_ENABLED": True,
        "APPS": [
            {
                "provider_id": "ibercivis",
                "name": "Ibercivis",
                "client_id": "lostatnight",
                "secret": "not-a-secret",
                "settings": {
                    "server_url": "http://ibercivis.test/realms/citsci",
                    "fetch_userinfo": False,
                    # As `gdalface/settings.py` declares it: an address this
                    # provider affirms does not sign into an account that
                    # already holds it. Without this key the site's global
                    # `SOCIALACCOUNT_EMAIL_AUTHENTICATION` would, and the case
                    # below is what notices.
                    "email_authentication": False,
                },
            }
        ],
    }
}

# What the sign-in service says about somebody who has just signed in, in the
# shape its userinfo endpoint answers in. The identifier is the only thing it
# promises never changes, and it says nothing about how the person proved who
# they are — with a Google account, with an ORCID, with a password held there.
IBERCIVIS_SAYS = {
    "sub": "3d7ba8aa-1f1e-4b0e-9a3f-1d2c3b4a5e6f@ibercivis.es",
    "email": "arrival@lostatnight.invalid",
    "email_verified": True,
}

IBERCIVIS_SIGN_IN_PATH = "/accounts/oidc/ibercivis/login/"

# The password the accounts this site already has were created with.
PASSWORD = "the-password-they-already-had"


def visible_markup(page):
    """A page's markup with the HTML comments taken out.

    Django renders its own tags inside `<!-- -->` just as it does anywhere
    else, so a commented-out `{% include %}` still puts its links in the
    response — where a person reading the page sees nothing. An assertion on
    the raw response passes on those links, which is why these tests read the
    page this way instead.
    """
    return re.sub(r"<!--.*?-->", "", page.content.decode(), flags=re.DOTALL)


class SignInCase(TestCase):
    """Base for every case here, for one reason.

    allauth refuses to send a second confirmation to the same address within
    three minutes, and it counts that in the cache, which no test rolls back.
    Without clearing it, a case asserting that no mail was sent passes because
    an earlier case used the address rather than because nothing sent one.
    """

    def setUp(self):
        cache.clear()


class LocalSignUpIsClosed(SignInCase):
    """The sign-up form the site used to offer accepts nobody.

    Verification is mandatory here, so an account created by the form could not
    sign in until its address was confirmed. That is why neither assertion is
    "the newcomer cannot sign in": that holds while the form still works, and
    would pass against an open door.
    """

    def test_the_sign_up_form_creates_no_account(self):
        self.client.post("/accounts/signup/", NEWCOMER)

        self.assertFalse(User.objects.filter(email=NEWCOMER["email"]).exists())

    def test_the_sign_up_form_sends_no_confirmation_mail(self):
        self.client.post("/accounts/signup/", NEWCOMER)

        self.assertEqual(mail.outbox, [])


# What an Ibercivis account looks like to this site, declared here rather than
# read from the environment: these tests must say what they assume. The real
# values come from `gdalface/settings.py`, and the one check this cannot make —
# that the two agree — is made by signing in for real.




@override_settings(SOCIALACCOUNT_PROVIDERS=IBERCIVIS_ACCOUNT)
class ArrivingWithAnIbercivisAccount(SignInCase):
    """The door the closed sign-up form must not have closed."""

    def arrive(self, **says):
        """Hand the site what the sign-in service said, and let it finish."""
        request = RequestFactory().get("/accounts/oidc/ibercivis/login/callback/")
        SessionMiddleware(lambda _: None).process_request(request)
        AuthenticationMiddleware(lambda _: None).process_request(request)
        MessageMiddleware(lambda _: None).process_request(request)
        request.session.save()

        # Outside a real request allauth has no request to read, because the
        # middleware that hands it one never ran. This is what that middleware
        # does.
        with context.request_context(request):
            provider = get_social_adapter().get_provider(request, "ibercivis")
            arrival = provider.sociallogin_from_response(
                request, {**IBERCIVIS_SAYS, **says}
            )
            complete_social_login(request, arrival)
        return request

    def test_a_newcomer_arriving_from_ibercivis_gets_an_account(self):
        request = self.arrive()

        self.assertTrue(request.user.is_authenticated)
        self.assertEqual(request.user.email, IBERCIVIS_SAYS["email"])

    def test_an_address_the_service_affirms_is_not_confirmed_again(self):
        request = self.arrive(email_verified=True)

        self.assertEqual(mail.outbox, [])
        self.assertTrue(request.user.is_authenticated)

    def test_an_address_the_service_does_not_affirm_is_not_confirmed_here(self):
        """Nobody confirms it, which is what `SOCIALACCOUNT_EMAIL_VERIFICATION` says.

        That setting is `'none'`: this site sends no confirmation of its own
        for an account arriving from a provider, because Google has confirmed
        the address before it says so. The Ibercivis sign-in service answers
        the same question in `email_verified`, and when it answers no, the
        account is still created and signed in on an address nobody checked.

        This case asserted a confirmation mail until the site was served from
        a tree that had the setting. It is left asserting what the site does,
        rather than what it ought to do: deciding that is not a branch
        refresh's business.
        """
        request = self.arrive(
            email_verified=False, email="unaffirmed@lostatnight.invalid"
        )

        self.assertEqual(mail.outbox, [])
        self.assertTrue(request.user.is_authenticated)

    def test_the_site_proves_it_asked_for_the_code_it_exchanges(self):
        """PKCE, which the sign-in service refuses a request without.

        allauth leaves it off unless it is asked for, and the failure is not
        subtle: the service answers the very first redirect with
        `Missing parameter: code_challenge_method` and nobody signs in.
        """
        request = RequestFactory().get("/accounts/oidc/ibercivis/login/")
        with context.request_context(request):
            provider = get_social_adapter().get_provider(request, "ibercivis")
            asked = provider.get_pkce_params()

        self.assertEqual(asked.get("code_challenge_method"), "S256")
        self.assertIn("code_challenge", asked)

    def test_the_identifier_is_the_key_and_the_address_is_not(self):
        first = self.arrive()
        second = self.arrive(email="renamed@lostatnight.invalid")

        self.assertEqual(first.user.pk, second.user.pk)

    def test_an_address_already_in_use_here_gets_no_second_account(self):
        """What the sign-in page has to be honest about.

        An address is one account on this site, so somebody who already signs
        in here with a password cannot arrive at the same address from
        Ibercivis and be handed a second account. allauth answers without
        saying whether the address exists — it writes to the address itself,
        which is the only party entitled to know — and signs nobody in.
        """
        held = User.objects.create_user(
            username="held", email=IBERCIVIS_SAYS["email"], password=PASSWORD
        )
        EmailAddress.objects.create(
            user=held, email=held.email, verified=True, primary=True
        )

        request = self.arrive()

        self.assertFalse(request.user.is_authenticated)
        self.assertFalse(SocialAccount.objects.exists())
        self.assertEqual(
            list(User.objects.filter(email=held.email).values_list("username", flat=True)),
            ["held"],
        )
        self.assertEqual([message.to for message in mail.outbox], [[held.email]])


@override_settings(SOCIALACCOUNT_PROVIDERS=IBERCIVIS_ACCOUNT)
class TheSignInPage(SignInCase):
    """What somebody arriving at /accounts/login/ is offered."""

    def page(self):
        return visible_markup(self.client.get("/accounts/login/"))

    def test_it_offers_an_ibercivis_account(self):
        self.assertIn(IBERCIVIS_SIGN_IN_PATH, self.page())

    def test_it_no_longer_offers_to_create_an_account_here(self):
        self.assertNotIn("/accounts/signup/", self.page())



@override_settings(SOCIALACCOUNT_PROVIDERS=IBERCIVIS_ACCOUNT)
class TheSignUpPage(SignInCase):
    """Whoever still reaches the old sign-up address is sent on."""

    def page(self):
        return visible_markup(self.client.get("/accounts/signup/"))

    def test_it_sends_a_newcomer_to_ibercivis(self):
        self.assertIn(IBERCIVIS_SIGN_IN_PATH, self.page())

    def test_it_says_that_an_ibercivis_account_is_a_separate_account(self):
        self.assertIn("separate account", self.page())

    def test_it_says_what_happens_at_an_address_already_in_use_here(self):
        self.assertIn("cannot sign you in", self.page())


class TheWayInThatAlreadyExisted(SignInCase):
    """Email and password, for the accounts this site already has.

    Nothing in this file's subject is allowed to change any of it, and the
    sign-up form being closed is the change most likely to.
    """

    def setUp(self):
        super().setUp()
        self.account = User.objects.create_user(
            username="volunteer9",
            email="volunteer9@lostatnight.invalid",
            password=PASSWORD,
        )

    def sign_in(self):
        return self.client.post(
            "/accounts/login/",
            {"login": self.account.email, "password": PASSWORD},
        )

    def test_a_confirmed_account_signs_in_with_its_password(self):
        EmailAddress.objects.create(
            user=self.account, email=self.account.email, verified=True, primary=True
        )

        response = self.sign_in()

        self.assertIn(SESSION_KEY, self.client.session)
        self.assertEqual(response.status_code, 302)

    def test_an_unconfirmed_account_is_still_asked_to_confirm(self):
        EmailAddress.objects.create(
            user=self.account, email=self.account.email, verified=False, primary=True
        )

        self.sign_in()

        self.assertNotIn(SESSION_KEY, self.client.session)
        self.assertEqual(len(mail.outbox), 1)


@override_settings(SOCIALACCOUNT_PROVIDERS={})
class WithNoIbercivisAccountConfigured(SignInCase):
    """How the sign-in pages behave where there is no service to reach.

    The local development stack is exactly this case: it starts this site on
    its own, with no sign-in service beside it. Both pages have to render
    anyway, and neither may offer a button that leads nowhere.
    """

    def test_the_sign_in_page_still_renders(self):
        page = self.client.get("/accounts/login/")

        self.assertEqual(page.status_code, 200)
        self.assertNotIn(IBERCIVIS_SIGN_IN_PATH, visible_markup(page))

    def test_the_closed_sign_up_page_still_renders(self):
        page = self.client.get("/accounts/signup/")

        self.assertEqual(page.status_code, 200)
        self.assertNotIn(IBERCIVIS_SIGN_IN_PATH, visible_markup(page))
