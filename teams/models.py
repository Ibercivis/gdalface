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
        """Team totals = Σ contribution() over memberships (active deltas +
        banked stints) of verified users, plus the active member count."""
        from georeferencing.metrics import verified_user_ids
        verified = set(verified_user_ids())
        tasks = cp = secs = 0
        members = 0
        for m in self.memberships.all():
            if m.left_at is None:
                members += 1
            if m.user_id not in verified:
                continue
            c = m.contribution()
            tasks += c['tasks']; cp += c['cp']; secs += c['seconds']
        return {'members': members, 'tasks': tasks, 'control_points': cp, 'time_spent': secs}

    def owner(self):
        return self.active_memberships().filter(role=TeamMembership.ROLE_OWNER).select_related('user').first()

    def rotate_invite_code(self):
        self.invite_code = _invite_code()
        self.save(update_fields=['invite_code'])
        return self.invite_code


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

    # Scoring. A member's contribution to the team is what they did *while a
    # member*: profile counters now minus the snapshot taken when they joined.
    # When they leave, that difference is banked on the row so the team keeps
    # the points earned inside it; re-joining takes a fresh baseline.
    baseline_tasks = models.IntegerField(default=0)
    baseline_cp = models.IntegerField(default=0)
    baseline_seconds = models.BigIntegerField(default=0)
    banked_tasks = models.IntegerField(default=0)
    banked_cp = models.IntegerField(default=0)
    banked_seconds = models.BigIntegerField(default=0)

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

    def _profile_counters(self):
        from user_profile.models import UserProfile
        p = UserProfile.objects.filter(user_id=self.user_id).values(
            'geoattempts_done', 'controlPointsDone', 'time_spent').first()
        if not p:
            return 0, 0, 0
        return p['geoattempts_done'] or 0, p['controlPointsDone'] or 0, p['time_spent'] or 0

    def take_baseline(self):
        self.baseline_tasks, self.baseline_cp, self.baseline_seconds = self._profile_counters()

    def contribution(self):
        """{'tasks','cp','seconds'} this membership adds to the team: banked
        from earlier stints plus the live delta if currently active."""
        tasks, cp, secs = self.banked_tasks, self.banked_cp, self.banked_seconds
        if self.left_at is None:
            t, c, s = self._profile_counters()
            tasks += max(0, t - self.baseline_tasks)
            cp += max(0, c - self.baseline_cp)
            secs += max(0, s - self.baseline_seconds)
        return {'tasks': tasks, 'cp': cp, 'seconds': secs}

    def close(self, at=None):
        """Leave: bank the live delta and stamp left_at."""
        from django.utils import timezone
        if self.left_at is not None:
            return
        live = self.contribution()
        self.banked_tasks, self.banked_cp, self.banked_seconds = live['tasks'], live['cp'], live['seconds']
        self.left_at = at or timezone.now()
        self.save(update_fields=['banked_tasks', 'banked_cp', 'banked_seconds', 'left_at'])

    def __str__(self):
        state = 'left' if self.left_at else 'active'
        return f'{self.user} -> {self.team} ({self.role}, {state})'
