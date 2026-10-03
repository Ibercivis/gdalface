from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from user_profile.models import UserProfile

from .models import Team, TeamMembership

User = get_user_model()


def make_user(username, cp=0, tasks=0, verified=True):
    user = User.objects.create_user(username=username, password='x', email=f'{username}@x.org')
    if verified:
        from allauth.account.models import EmailAddress
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    # A post_save signal may have created the profile already.
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.controlPointsDone = cp
    profile.geoattempts_done = tasks
    profile.save()
    return user


LOCMEM_CACHE = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                            'LOCATION': 'teams-tests'}}

@override_settings(CACHES=LOCMEM_CACHE)
class TeamLifecycleTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice', cp=100, tasks=10)
        self.bob = make_user('bob', cp=50, tasks=5)

    def test_create_team_enrolls_creator_as_owner(self):
        self.client.force_login(self.alice)
        resp = self.client.post(reverse('team_create'), {'name': 'Night Owls'})
        team = Team.objects.get(name='Night Owls')
        self.assertRedirects(resp, f'/teams/{team.slug}/')
        m = TeamMembership.objects.get(team=team, user=self.alice)
        self.assertTrue(m.is_active)
        self.assertEqual(m.role, TeamMembership.ROLE_OWNER)

    def test_create_rejects_short_and_duplicate_names(self):
        self.client.force_login(self.alice)
        self.client.post(reverse('team_create'), {'name': 'ab'})
        self.assertEqual(Team.objects.count(), 0)
        self.client.post(reverse('team_create'), {'name': 'Night Owls'})
        self.client.force_login(self.bob)
        self.client.post(reverse('team_create'), {'name': 'night owls'})
        self.assertEqual(Team.objects.count(), 1)

    def test_join_by_code_switches_active_team(self):
        t1 = Team.objects.create(name='One', creator=self.alice)
        t2 = Team.objects.create(name='Two', creator=self.bob)
        self.client.force_login(self.alice)
        self.client.post(reverse('team_join'), {'invite_code': t1.invite_code})
        self.client.post(reverse('team_join'), {'invite_code': t2.invite_code})
        active = TeamMembership.objects.filter(user=self.alice, left_at__isnull=True)
        self.assertEqual(active.count(), 1)
        self.assertEqual(active.first().team, t2)

    def test_join_closed_team_by_slug_refused(self):
        t = Team.objects.create(name='Closed', is_open=False, creator=self.bob)
        self.client.force_login(self.alice)
        self.client.post(reverse('team_join'), {'slug': t.slug})
        self.assertFalse(
            TeamMembership.objects.filter(user=self.alice, team=t).exists())

    def test_leave_team(self):
        t = Team.objects.create(name='One', creator=self.alice)
        self.client.force_login(self.alice)
        self.client.post(reverse('team_join'), {'invite_code': t.invite_code})
        self.client.post(reverse('team_leave'))
        self.assertFalse(
            TeamMembership.objects.filter(user=self.alice, left_at__isnull=True).exists())

    def test_team_detail_page_renders(self):
        t = Team.objects.create(name='Render Me', creator=self.alice)
        TeamMembership.objects.create(team=t, user=self.alice)
        resp = self.client.get(f'/teams/{t.slug}/')
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Render Me')




@override_settings(CACHES=LOCMEM_CACHE)
class TeamsRankingApiTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice', cp=100, tasks=10)
        self.bob = make_user('bob', cp=50, tasks=5)
        self.carol = make_user('carol', cp=30, tasks=3)
        self.t1 = Team.objects.create(name='Alpha')
        self.t2 = Team.objects.create(name='Beta')
        TeamMembership.objects.create(team=self.t1, user=self.alice)
        TeamMembership.objects.create(team=self.t2, user=self.bob)
        TeamMembership.objects.create(team=self.t2, user=self.carol)

    def test_ranking_sums_active_members(self):
        from django.core.cache import cache
        cache.clear()
        resp = self.client.get('/api/v1/ranking/teams/')
        data = resp.json()
        self.assertEqual(data['total_teams'], 2)
        self.assertEqual(data['rows'][0]['name'], 'Alpha')  # 100 cp > 80 cp
        self.assertEqual(data['rows'][0]['control_points'], 100)
        self.assertEqual(data['rows'][1]['control_points'], 80)
        self.assertEqual(data['rows'][1]['members'], 2)

    def test_left_members_do_not_count(self):
        from django.core.cache import cache
        from django.utils import timezone
        TeamMembership.objects.filter(user=self.alice).update(left_at=timezone.now())
        cache.clear()
        data = self.client.get('/api/v1/ranking/teams/').json()
        alpha = next(r for r in data['rows'] if r['name'] == 'Alpha')
        self.assertEqual(alpha['control_points'], 0)
        self.assertEqual(alpha['members'], 0)

    def test_my_team_rank(self):
        from django.core.cache import cache
        cache.clear()
        self.client.force_login(self.bob)
        data = self.client.get('/api/v1/ranking/teams/').json()
        self.assertEqual(data['my_team_slug'], self.t2.slug)
        self.assertEqual(data['my_team_rank'], 2)
