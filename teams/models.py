"""
Teams: self-organised groups (classrooms, astronomy clubs, offices…) whose
members' contributions are summed into a team leaderboard.

Mirrors the ChallengeParticipant enrollment pattern: a row per (team, user),
re-joining reuses the row, and a partial unique constraint guarantees at most
one *active* membership per user across all teams.
"""
import secrets

from django.conf import settings
from django.db import models
from django.utils.text import slugify
from django.utils.translation import gettext_lazy as _


def _invite_code():
    # 8 hex chars: short enough to read out loud in a classroom.
    return secrets.token_hex(4)


class Team(models.Model):
    name = models.CharField(max_length=60, unique=True, verbose_name=_("Name"))
    slug = models.SlugField(max_length=80, unique=True)
    description = models.TextField(blank=True, verbose_name=_("Description"))
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='teams_created',
    )
    # Open teams accept one-click joins; closed teams require the invite code.
    is_open = models.BooleanField(default=True, verbose_name=_("Open to everyone"))
    invite_code = models.CharField(max_length=16, unique=True, default=_invite_code)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:70] or 'team'
            slug = base
            n = 2
            while Team.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f'{base}-{n}'
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def active_memberships(self):
        return self.memberships.filter(left_at__isnull=True)

    def stats(self):
        """All-time totals over the *current* members' lifetime counters."""
        from user_profile.models import UserProfile
        return UserProfile.objects.filter(
            user__team_memberships__team=self,
            user__team_memberships__left_at__isnull=True,
        ).aggregate(
            members=models.Count('id'),
            tasks=models.Sum('geoattempts_done'),
            control_points=models.Sum('controlPointsDone'),
            time_spent=models.Sum('time_spent'),
        )


class TeamMembership(models.Model):
    ROLE_OWNER = 'owner'
    ROLE_MEMBER = 'member'
    ROLE_CHOICES = [
        (ROLE_OWNER, _('Owner')),
        (ROLE_MEMBER, _('Member')),
    ]

    team = models.ForeignKey(
        Team, on_delete=models.CASCADE, related_name='memberships',
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='team_memberships',
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default=ROLE_MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['team', 'user'],
                name='unique_member_per_team',
            ),
            # At most one active team per user (same pattern as challenges).
            models.UniqueConstraint(
                fields=['user'],
                condition=models.Q(left_at__isnull=True),
                name='one_active_team_per_user',
            ),
        ]
        indexes = [
            models.Index(fields=['team', 'left_at']),
        ]

    @property
    def is_active(self):
        return self.left_at is None

    def __str__(self):
        state = 'left' if self.left_at else 'active'
        return f'{self.user} -> {self.team} ({self.role}, {state})'
