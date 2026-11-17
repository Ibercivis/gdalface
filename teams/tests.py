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


@override_settings(CACHES=LOCMEM_CACHE)
class TeamScoringTests(TestCase):
    """A member adds what they did while in the team; it stays banked on leave."""

    def setUp(self):
        self.alice = make_user('alice', cp=100, tasks=10)
        self.bob = make_user('bob', cp=50, tasks=5)
        self.carol = make_user('carol', cp=999, tasks=99, verified=False)
        self.client.force_login(self.alice)
        self.client.post(reverse('team_create'), {'name': 'Owls', 'is_open': '1'})
        self.team = Team.objects.get(name='Owls')

    def _bump(self, user, cp, tasks):
        p = UserProfile.objects.get(user=user)
        p.controlPointsDone += cp; p.geoattempts_done += tasks; p.save()

    def test_baseline_taken_on_join_and_delta_counts(self):
        self.assertEqual(self.team.stats()['control_points'], 0)   # 100 lifetime, 0 for the team
        self._bump(self.alice, 30, 3)
        st = self.team.stats()
        self.assertEqual((st['control_points'], st['tasks'], st['members']), (30, 3, 1))

    def test_unverified_member_does_not_score(self):
        self.client.force_login(self.carol)
        self.client.post(reverse('team_join'), {'slug': self.team.slug})
        self._bump(self.carol, 500, 50)
        self.assertEqual(self.team.stats()['control_points'], 0)
        self.assertEqual(self.team.stats()['members'], 2)

    def test_points_bank_on_leave_and_rejoin_starts_fresh(self):
        self._bump(self.alice, 30, 3)
        self.client.post(reverse('team_leave'))
        m = TeamMembership.objects.get(team=self.team, user=self.alice)
        self.assertEqual((m.banked_cp, m.banked_tasks), (30, 3))
        self.assertEqual(self.team.stats()['control_points'], 30)   # stays with the team
        self._bump(self.alice, 20, 2)                                # earned outside → not for the team
        self.client.post(reverse('team_join'), {'invite_code': self.team.invite_code})
        self.assertEqual(self.team.stats()['control_points'], 30)
        self._bump(self.alice, 5, 1)
        self.assertEqual(self.team.stats()['control_points'], 35)

    def test_ranking_api_uses_contributions(self):
        self._bump(self.alice, 30, 3)
        self.client.force_login(self.bob)
        self.client.post(reverse('team_create'), {'name': 'Bats'})
        self._bump(self.bob, 80, 8)
        data = self.client.get('/api/v1/ranking/teams/').json()
        self.assertEqual([(r['name'], r['control_points']) for r in data['rows']], [('Bats', 80), ('Owls', 30)])
        self.assertEqual(data['my_team_slug'], 'bats')
        self.assertEqual(data['my_team_rank'], 1)

    def test_period_ranking_counts_from_join_date(self):
        from datetime import date, timedelta
        from georeferencing.models import GeoAttemptsByUserByDay
        GeoAttemptsByUserByDay.objects.create(user=self.alice, date=date.today(), numberGeoAttempts=4, controlPoints=12)
        GeoAttemptsByUserByDay.objects.create(user=self.alice, date=date.today() - timedelta(days=3), numberGeoAttempts=9, controlPoints=50)  # before joining
        data = self.client.get('/api/v1/ranking/teams/?period=week').json()
        owls = next(r for r in data['rows'] if r['slug'] == 'owls')
        self.assertEqual((owls['tasks'], owls['control_points']), (4, 12))


@override_settings(CACHES=LOCMEM_CACHE)
class TeamPagesAndOwnerToolsTests(TestCase):
    def setUp(self):
        self.alice = make_user('alice'); self.bob = make_user('bob'); self.eve = make_user('eve')
        self.client.force_login(self.alice)
        self.client.post(reverse('team_create'), {'name': 'Owls', 'description': 'Night birds', 'is_open': '1'})
        self.team = Team.objects.get(name='Owls')

    def test_list_page_public_and_searchable(self):
        self.client.logout()
        r = self.client.get('/teams/')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Owls'); self.assertContains(r, 'Night birds')
        self.assertNotContains(self.client.get('/teams/?q=zzz'), 'Night birds')

    def test_invite_link_flow(self):
        url = f'/teams/join/?code={self.team.invite_code}'
        self.client.logout()
        r = self.client.get(url)
        self.assertEqual(r.status_code, 302); self.assertIn('/accounts/login', r['Location'])
        self.client.force_login(self.bob)
        r = self.client.get(url)
        self.assertEqual(r.status_code, 200); self.assertContains(r, 'Owls')
        r = self.client.post(reverse('team_join'), {'invite_code': self.team.invite_code})
        self.assertRedirects(r, f'/teams/{self.team.slug}/')
        self.assertTrue(TeamMembership.objects.filter(team=self.team, user=self.bob, left_at__isnull=True).exists())
        r = self.client.get('/teams/join/?code=nope', follow=True)
        self.assertContains(r, 'No team matches')

    def test_next_redirect_is_validated(self):
        r = self.client.post(reverse('team_join'), {'invite_code': 'bad', 'next': 'https://evil.example/x'})
        self.assertEqual(r['Location'], '/teams/')

    def test_create_default_is_invite_only_and_closed_join_refused(self):
        self.client.force_login(self.bob)
        self.client.post(reverse('team_create'), {'name': 'Secret'})
        secret = Team.objects.get(name='Secret')
        self.assertFalse(secret.is_open)
        self.client.force_login(self.eve)
        self.client.post(reverse('team_join'), {'slug': secret.slug})
        self.assertFalse(TeamMembership.objects.filter(team=secret, user=self.eve).exists())

    def test_owner_tools(self):
        # bob joins; alice (owner) edits, rotates the code, transfers, is removed-protected
        self.client.force_login(self.bob)
        self.client.post(reverse('team_join'), {'slug': self.team.slug})
        bob_m = TeamMembership.objects.get(team=self.team, user=self.bob)
        self.client.force_login(self.alice)
        old_code = self.team.invite_code
        self.client.post(reverse('team_edit', args=[self.team.slug]), {'name': 'Night Owls', 'description': 'd', 'is_open': '0'})
        self.team.refresh_from_db()
        self.assertEqual((self.team.name, self.team.is_open), ('Night Owls', False))
        self.client.post(reverse('team_rotate_code', args=[self.team.slug]))
        self.team.refresh_from_db(); self.assertNotEqual(self.team.invite_code, old_code)
        # non-owner cannot use tools
        self.client.force_login(self.bob)
        self.assertEqual(self.client.post(reverse('team_rotate_code', args=[self.team.slug])).status_code, 404)
        # transfer, then the new owner removes alice
        self.client.force_login(self.alice)
        self.client.post(reverse('team_transfer', args=[self.team.slug]), {'membership_id': bob_m.id})
        self.assertEqual(TeamMembership.objects.get(team=self.team, user=self.bob).role, 'owner')
        self.client.force_login(self.bob)
        alice_m = TeamMembership.objects.get(team=self.team, user=self.alice)
        self.client.post(reverse('team_remove_member', args=[self.team.slug]), {'membership_id': alice_m.id})
        alice_m.refresh_from_db(); self.assertIsNotNone(alice_m.left_at)
        # delete only when alone
        r = self.client.post(reverse('team_delete', args=[self.team.slug]))
        self.assertRedirects(r, '/teams/')
        self.assertFalse(Team.objects.filter(pk=self.team.pk).exists())

    def test_owner_leaving_passes_ownership_to_oldest_member(self):
        self.client.force_login(self.bob)
        self.client.post(reverse('team_join'), {'slug': self.team.slug})
        self.client.force_login(self.alice)
        self.client.post(reverse('team_leave'))
        self.assertEqual(self.team.owner().user, self.bob)

    def test_detail_page_hides_invisible_members(self):
        UserProfile.objects.filter(user=self.bob).update(visible=False)
        self.client.force_login(self.bob)
        self.client.post(reverse('team_join'), {'slug': self.team.slug})
        self.client.logout()
        r = self.client.get(f'/teams/{self.team.slug}/')
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, '>bob<'); self.assertContains(r, 'Invisible user')


@override_settings(CACHES=LOCMEM_CACHE)
class TeamListWeeklyTrendTests(TestCase):
    """/teams/ shows places gained/lost and new members/tasks/CP over 7 days."""

    def _team(self, name, owner, created_days_ago, cp_before, cp_week):
        from datetime import date, timedelta
        from django.utils import timezone
        from georeferencing.models import GeoAttemptsByUserByDay
        self.client.force_login(owner)
        self.client.post(reverse('team_create'), {'name': name, 'is_open': '1'})
        team = Team.objects.get(name=name)
        when = timezone.now() - timedelta(days=created_days_ago)
        Team.objects.filter(pk=team.pk).update(created_at=when)
        TeamMembership.objects.filter(team=team).update(joined_at=when)
        p = UserProfile.objects.get(user=owner)
        p.controlPointsDone += cp_before + cp_week
        p.geoattempts_done += 2 if cp_week else 0
        p.save()
        if cp_week:
            GeoAttemptsByUserByDay.objects.create(
                user=owner, date=date.today(), numberGeoAttempts=2, controlPoints=cp_week)
        return team

    def test_rank_change_and_weekly_deltas(self):
        from datetime import timedelta
        from django.core.cache import cache
        from django.utils import timezone
        cache.clear()
        alice, bob, eve = make_user('alice'), make_user('bob'), make_user('eve')
        User.objects.filter(pk__in=[alice.pk, bob.pk]).update(date_joined=timezone.now() - timedelta(days=40))
        self._team('Owls', alice, 30, cp_before=100, cp_week=0)     # was 1st
        self._team('Bats', bob, 30, cp_before=50, cp_week=80)       # was 2nd, now 1st
        self._team('Moths', eve, 2, cp_before=0, cp_week=10)        # created this week
        from .views import _rank_with_trend, _rows_with_weekly_trend
        rows = {r['team'].name: r for r in _rank_with_trend(_rows_with_weekly_trend())}
        self.assertEqual([rows[n]['rank'] for n in ('Bats', 'Owls', 'Moths')], [1, 2, 3])
        self.assertEqual(rows['Bats']['rank_change'], 1)
        self.assertEqual(rows['Owls']['rank_change'], -1)
        self.assertTrue(rows['Moths']['is_new'])
        self.assertEqual((rows['Bats']['new_cp'], rows['Bats']['new_tasks'], rows['Bats']['new_members']), (80, 2, 0))
        self.assertEqual((rows['Owls']['new_cp'], rows['Owls']['new_members']), (0, 0))
        self.assertEqual((rows['Moths']['new_cp'], rows['Moths']['new_members']), (10, 1))
        html = self.client.get('/teams/').content.decode()
        self.assertIn('▲1', html)
        self.assertIn('▼1', html)
        self.assertIn('+80', html)
        api = {r['name']: r for r in self.client.get('/api/v1/ranking/teams/?period=all&ordering=cp').json()['rows']}
        self.assertEqual((api['Bats']['rank_change'], api['Owls']['rank_change'], api['Bats']['new_cp']), (1, -1, 80))
        self.assertTrue(api['Moths']['is_new'])
        # People ranking, same ordering: bob (130) overtook alice (100) this week.
        people = {r['username']: r for r in self.client.get('/api/v1/ranking/?period=all&ordering=cp').json()['rows']}
        self.assertEqual((people['bob']['rank'], people['bob']['rank_change'], people['bob']['new_cp']), (1, 1, 80))
        self.assertEqual((people['alice']['rank'], people['alice']['rank_change'], people['alice']['new_cp']), (2, -1, 0))
        self.assertTrue(people['eve']['is_new'])
        # Ordered by tasks nobody had any before, so the order a week ago was the tie-break one.
        people = {r['username']: r for r in self.client.get('/api/v1/ranking/?period=all&ordering=tasks').json()['rows']}
        self.assertEqual((people['bob']['rank_change'], people['bob']['new_tasks']), (1, 2))
