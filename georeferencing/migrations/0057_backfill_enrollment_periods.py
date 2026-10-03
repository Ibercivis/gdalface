"""
Backfill ChallengeEnrollmentPeriod from the single joined_at/left_at that each
ChallengeParticipant row carried so far.

Two data fixes are applied while doing so:
- A participant whose row is still open (left_at NULL) but who later joined
  another challenge implicitly left this one at that moment (the join flow has
  always auto-left the previous enrollment; a few legacy rows predate that).
  Their left_at is set to the next join time.
- The resulting period is flagged `backfilled=True`: it cannot know about
  intermediate leave/re-join stints, which were never recorded.
"""
from django.db import migrations


def forwards(apps, schema_editor):
    Participant = apps.get_model('georeferencing', 'ChallengeParticipant')
    Period = apps.get_model('georeferencing', 'ChallengeEnrollmentPeriod')
    by_user = {}
    for p in Participant.objects.all().order_by('joined_at'):
        by_user.setdefault(p.user_id, []).append(p)
    for rows in by_user.values():
        for i, p in enumerate(rows):
            next_join = rows[i + 1].joined_at if i + 1 < len(rows) else None
            left = p.left_at
            if next_join and (left is None or left > next_join):
                left = next_join
                if p.left_at is None:
                    p.left_at = left
                    p.save(update_fields=['left_at'])
            Period.objects.create(participant=p, joined_at=p.joined_at, left_at=left, backfilled=True)


def backwards(apps, schema_editor):
    apps.get_model('georeferencing', 'ChallengeEnrollmentPeriod').objects.filter(backfilled=True).delete()


class Migration(migrations.Migration):
    dependencies = [('georeferencing', '0056_challengeenrollmentperiod')]
    operations = [migrations.RunPython(forwards, backwards)]
