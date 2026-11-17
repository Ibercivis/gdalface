"""
Bearer-token authentication for the staff export API.

The token is sent in the `Authorization` header (never in the URL, which would
end up in access logs). Staff status is checked on every request, so removing
`is_staff` from a user cuts the access immediately, whatever tokens they hold.
"""
from django.utils import timezone
from rest_framework import authentication, exceptions
from rest_framework.permissions import BasePermission
from rest_framework.throttling import SimpleRateThrottle

from .models import ApiToken


class ApiTokenAuthentication(authentication.BaseAuthentication):
    keyword = 'Bearer'

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).split()
        if not header or header[0].lower() != self.keyword.lower().encode():
            return None
        if len(header) != 2:
            raise exceptions.AuthenticationFailed('Invalid token header.')
        try:
            raw = header[1].decode()
        except UnicodeError:
            raise exceptions.AuthenticationFailed('Invalid token header.')
        try:
            token = ApiToken.objects.select_related('user').get(
                token_hash=ApiToken.hash_token(raw), revoked=False)
        except ApiToken.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid or revoked token.')
        if not token.user.is_active:
            raise exceptions.AuthenticationFailed('Invalid or revoked token.')
        ApiToken.objects.filter(pk=token.pk).update(last_used=timezone.now())
        return (token.user, token)

    def authenticate_header(self, request):
        return self.keyword


class IsStaffToken(BasePermission):
    """Staff only, re-checked on every request."""
    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.is_staff)


class ApiTokenThrottle(SimpleRateThrottle):
    scope = 'export'
    THROTTLE_RATES = {'export': '60/min'}

    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return self.cache_format % {'scope': self.scope, 'ident': request.user.pk}
