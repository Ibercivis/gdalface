"""
allauth adapters.

The site has two ways in and they answer the question "may this person create an
account here?" differently, which is the whole reason these classes exist.
`gdalface/settings.py` names both.
"""

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    """Email-and-password sign-in, with sign-up closed.

    Accounts that already exist keep signing in with their password, and
    nothing about that flow changes: the password form, the mandatory address
    confirmation and the password reset all behave as they always did.

    What is closed is the creation of *new* local accounts. Somebody arriving
    for the first time signs in with an Ibercivis account instead, which is the
    point of serving this site alongside the other Ibercivis citizen science
    sites: one account for all of them rather than one more password here.
    """

    def is_open_for_signup(self, request):
        """No: the sign-up form creates nothing."""
        return False


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Signing in with an Ibercivis account, which does create accounts.

    This class exists only to say so. allauth's own social adapter answers
    `is_open_for_signup` by asking the account adapter above, which says no —
    so without this, closing the local sign-up form would also close the one
    way in that remains, and the site would accept nobody new at all.
    """

    def is_open_for_signup(self, request, sociallogin):
        """Yes: arriving from Ibercivis is how an account is made now."""
        return True
