"""
Delete accounts that never verified their e-mail and never did anything.

Between April and July 2026 ~4,500 accounts were created by bots: no verified
e-mail, no login, no contribution. They inflate "registered users" and keep
receiving verification mails. This removes them, with strict guards:

  kept if: staff or superuser · any verified e-mail · ever logged in ·
           any DONE task · profile counters > 0 · owns a batch ·
           in a challenge or team · social account · younger than --older-than

Dry-run by default. --apply deletes; --backup writes a JSON list of the deleted
accounts (id, username, e-mail, date_joined) next to the DB backups first.
"""
import json
import os
from datetime import timedelta

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from georeferencing.models import Batch, ChallengeParticipant, GeoAttempt, StatsEvent
from teams.models import TeamMembership


class Command(BaseCommand):
    help = 'Delete never-verified, never-active accounts (dry-run unless --apply).'

    def add_arguments(self, p):
        p.add_argument('--older-than', type=int, default=7, help='days since sign-up (default 7)')
        p.add_argument('--apply', action='store_true')
        p.add_argument('--backup', default='/home/ubuntu/gdalface-backups',
                       help='directory for the JSON list of deleted accounts')

    def candidates(self, older_than):
        User = get_user_model()
        cutoff = timezone.now() - timedelta(days=older_than)
        qs = (User.objects
              .filter(date_joined__lt=cutoff, is_staff=False, is_superuser=False, last_login__isnull=True)
              .exclude(id__in=EmailAddress.objects.filter(verified=True).values('user_id'))
              .exclude(id__in=GeoAttempt.objects.filter(status='DONE', assignedUser__isnull=False).values('assignedUser_id'))
              .exclude(userprofile__controlPointsDone__gt=0)
              .exclude(userprofile__geoattempts_done__gt=0)
              .exclude(id__in=Batch.objects.values('user_id'))
              .exclude(id__in=ChallengeParticipant.objects.values('user_id'))
              .exclude(id__in=TeamMembership.objects.values('user_id'))
              .exclude(socialaccount__isnull=False))
        return qs.distinct()

    def handle(self, *args, **o):
        User = get_user_model()
        qs = self.candidates(o['older_than'])
        n = qs.count()
        total = User.objects.count()
        self.stdout.write(f'users={total} candidates={n} (never verified, never logged in, no activity, '
                          f'older than {o["older_than"]} days) keep={total - n}')
        by_month = {}
        for d in qs.values_list('date_joined', flat=True):
            by_month[d.strftime('%Y-%m')] = by_month.get(d.strftime('%Y-%m'), 0) + 1
        self.stdout.write('by sign-up month: ' + ' '.join(f'{k}={v}' for k, v in sorted(by_month.items())))
        if not o['apply']:
            self.stdout.write('DRY RUN, nothing deleted')
            return
        os.makedirs(o['backup'], exist_ok=True)
        path = os.path.join(o['backup'], f'purged_unverified_users_{timezone.now():%Y%m%d_%H%M}.json')
        rows = list(qs.values('id', 'username', 'email', 'date_joined'))
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(rows, fh, default=str, ensure_ascii=False)
        deleted = 0
        for chunk_start in range(0, len(rows), 500):
            ids = [r['id'] for r in rows[chunk_start:chunk_start + 500]]
            deleted += User.objects.filter(id__in=ids).delete()[1].get('auth.User', 0)
        StatsEvent.objects.create(kind='other', title=f'Purged {deleted} never-verified accounts',
                                  note=f'purge_unverified_users --older-than {o["older_than"]}. List: {path}')
        self.stdout.write(f'DELETED {deleted} users. Backup list: {path}. Users now: {User.objects.count()}')
