"""Feature-driven test cases for the UpEngage (Slido-like) application.

Every test encodes the intended behaviour of a Slido-style feature so that a
passing suite guarantees the feature works. Failing tests point at bugs.

Coverage:
    * Auth          - register, login, protected pages
    * Events        - host creates events, guests join by code
    * Q&A           - submit / order / upvote / mark answered / enable+disable
    * Polls         - multiple-choice, rating, word-cloud, voting once per session
    * WebSockets    - live connect, broadcasts, host-only guards
    * Frontend glue - websocket URLs rendered in templates (event code vs title)
"""

import asyncio

from django.contrib.auth.models import User
from django.test import TestCase, TransactionTestCase, Client
from django.urls import reverse

from rest_framework.test import APIClient

from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from up_engage_project.asgi import application

from .models import (
    Event,
    Question,
    QuestionUpvote,
    Poll,
    PollOption,
    Vote,
    WordCloudResponse,
    RatingResponse,
)


def _create_user(username):
    return User.objects.create_user(username=username, password='testpass123')


class AuthFlowTests(TestCase):
    """Register, login and access control for hosts."""

    def setUp(self):
        self.user = _create_user('host1')
        self.client = Client()

    def test_register_creates_account(self):
        response = self.client.get('/auth/register/')
        self.assertEqual(response.status_code, 200)
        response = self.client.post('/auth/register/', {
            'username': 'newhost',
            'password1': 'SuperSecret123!',
            'password2': 'SuperSecret123!',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.filter(username='newhost').count(), 1)

    def test_login_redirects_to_dashboard(self):
        response = self.client.post('/auth/login/', {
            'username': 'host1',
            'password': 'testpass123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('dashboard'), response.url)

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_profile_requires_login(self):
        response = self.client.get(reverse('profile'))
        self.assertEqual(response.status_code, 302)


class EventFlowTests(TestCase):
    """Hosts create events; guests join them with an event code."""

    def setUp(self):
        self.host = _create_user('host_event')
        self.api = APIClient()
        self.api.force_authenticate(user=self.host)

    def test_create_event_returns_short_uppercase_code(self):
        response = self.api.post('/api/events/', {
            'title': 'Math Review',
            'description': 'For period 3',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        code = response.json()['event_code']
        self.assertEqual(len(code), 4)
        self.assertEqual(code, code.upper())

    def test_join_event_code_is_case_insensitive(self):
        event = Event.objects.create(title='Quiz', host=self.host, event_code='ABCD')
        response = self.client.post(reverse('home'), {'event_code': 'abcd'})
        self.assertEqual(response.status_code, 302)
        self.assertIn(f'/event/{event.event_code}/', response.url)

    def test_join_inactive_event_fails(self):
        event = Event.objects.create(title='Gone', host=self.host, event_code='GONE')
        event.is_active = False
        event.save()
        response = self.client.post(reverse('home'), {'event_code': event.event_code})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Event not found')

    def test_anonymous_cannot_create_event(self):
        anon = APIClient()
        response = anon.post('/api/events/', {'title': 'Nope'}, format='json')
        self.assertIn(response.status_code, (401, 403))

    def test_non_host_cannot_toggle_event_active(self):
        event = Event.objects.create(title='Mine', host=self.host, event_code='MINE')
        other = _create_user('other_host')
        other_api = APIClient()
        other_api.force_authenticate(user=other)
        response = other_api.post(f'/api/events/{event.event_code}/toggle_active/')
        self.assertEqual(response.status_code, 403)
        event.refresh_from_db()
        self.assertTrue(event.is_active)


class EventDeleteTests(TestCase):
    """Hosts delete their own events from the dashboard's kebab menu."""

    def setUp(self):
        self.host = _create_user('host_del')
        self.api = APIClient()
        self.api.force_authenticate(user=self.host)
        self.event = Event.objects.create(
            title='Cleanup Session', host=self.host, event_code='DEL1', is_active=True)

    def test_host_can_delete_own_event(self):
        response = self.api.delete(f'/api/events/{self.event.event_code}/')
        self.assertEqual(response.status_code, 204)
        self.assertFalse(Event.objects.filter(pk=self.event.pk).exists())

    def test_delete_removes_associated_content(self):
        poll = Poll.objects.create(
            event=self.event, question_text='Bye', poll_type='multiple-choice')
        PollOption.objects.create(poll=poll, text='Yes')
        Question.objects.create(event=self.event, text='Bye too', author_session_id='s1')
        response = self.api.delete(f'/api/events/{self.event.event_code}/')
        self.assertEqual(response.status_code, 204)
        self.assertEqual(Poll.objects.filter(pk=poll.pk).count(), 0)
        self.assertEqual(Question.objects.filter(event=self.event).count(), 0)

    def test_non_host_cannot_delete_event(self):
        other = _create_user('other_del')
        other_api = APIClient()
        other_api.force_authenticate(user=other)
        response = other_api.delete(f'/api/events/{self.event.event_code}/')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())

    def test_anonymous_cannot_delete_event(self):
        anon = APIClient()
        response = anon.delete(f'/api/events/{self.event.event_code}/')
        self.assertIn(response.status_code, (401, 403))
        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())

    def test_dashboard_renders_delete_menu(self):
        client = Client()
        client.force_login(self.host)
        response = client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('fas fa-ellipsis-v', html)
        self.assertIn('delete-event-btn', html)
        self.assertIn(f'data-event-code="{self.event.event_code}"', html)
        self.assertIn('id="deleteEventModal"', html)
        self.assertIn('id="confirmDeleteEvent"', html)


class DashboardStatsTests(TestCase):
    """Dashboard event cards show rating poll results: the average, not just a count."""

    def setUp(self):
        self.host = _create_user('host_stats')
        self.event = Event.objects.create(title='Rated', host=self.host, event_code='RATE')
        self.client = Client()
        self.client.force_login(self.host)

    def _dashboard_row(self):
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)
        return response, next(
            e for e in response.context['events'] if e.event_code == self.event.event_code)

    def test_dashboard_shows_average_rating(self):
        poll = Poll.objects.create(
            event=self.event, question_text='How was it?', poll_type='rating')
        for i, r in enumerate((3, 5, 4)):
            RatingResponse.objects.create(poll=poll, rating=r, author_session_id=f's{i}')
        response, row = self._dashboard_row()
        self.assertEqual(row.rating_count, 3)
        self.assertEqual(round(float(row.avg_rating), 2), 4.0)
        self.assertContains(response, '4.0 avg')
        self.assertContains(response, '3 ratings')

    def test_dashboard_hides_rating_stat_when_no_ratings(self):
        Poll.objects.create(
            event=self.event, question_text='No answers yet', poll_type='rating')
        response, row = self._dashboard_row()
        self.assertIsNone(row.avg_rating)
        self.assertEqual(row.rating_count, 0)
        self.assertNotContains(response, 'avg ·')

    def test_dashboard_counts_are_not_multiplied_by_joins(self):
        Poll.objects.create(event=self.event, question_text='Q1?', poll_type='multiple-choice')
        Poll.objects.create(event=self.event, question_text='Q2?', poll_type='rating')
        Question.objects.create(event=self.event, text='A1', author_session_id='s1')
        Question.objects.create(event=self.event, text='A2', author_session_id='s1')
        _, row = self._dashboard_row()
        self.assertEqual(row.question_count, 2)
        self.assertEqual(row.poll_count, 2)


class QnAFlowTests(TestCase):
    """Live Q&A: submit, order by upvotes, upvote, mark answered, QA toggle."""

    def setUp(self):
        self.host = _create_user('host_qa')
        self.event = Event.objects.create(
            title='Biology Live', host=self.host, event_code='BIOL', is_active=True)
        self.anon = APIClient()
        self.anon.get('/')  # create a participant session

    def test_submit_question_records_participant_session(self):
        response = self.anon.post(
            f'/api/events/{self.event.event_code}/questions/',
            {'text': 'What is a cell?'}, format='json')
        self.assertEqual(response.status_code, 201)
        q = Question.objects.get(text='What is a cell?')
        self.assertEqual(q.event, self.event)
        self.assertEqual(q.author_session_id, self.anon.session.session_key)

    def test_blank_question_is_rejected(self):
        response = self.anon.post(
            f'/api/events/{self.event.event_code}/questions/',
            {'text': ''}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_questions_ordered_by_upvotes(self):
        q_high = Question.objects.create(
            event=self.event, text='Most upvoted', author_session_id='s1')
        q_low = Question.objects.create(
            event=self.event, text='Least upvoted', author_session_id='s1')
        QuestionUpvote.objects.create(question=q_high, session_id='v1')
        QuestionUpvote.objects.create(question=q_high, session_id='v2')
        QuestionUpvote.objects.create(question=q_low, session_id='v3')

        response = self.anon.get(f'/api/events/{self.event.event_code}/questions/')
        self.assertEqual(response.status_code, 200)
        results = response.json()['results']
        self.assertEqual(results[0]['text'], 'Most upvoted')
        self.assertEqual(results[0]['upvote_count'], 2)

    def test_question_upvote_returns_updated_count(self):
        question = Question.objects.create(
            event=self.event, text='Will this work?', author_session_id='s1')
        client = Client(raise_request_exception=False)
        client.get('/')
        response = client.post(f'/api/questions/{question.id}/upvote/')
        # Expected: 200 with upvoted True and count 1.
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body['upvoted'])
        self.assertEqual(body['upvote_count'], 1)

    def test_mark_answered_allows_host(self):
        question = Question.objects.create(
            event=self.event, text='Answered?', author_session_id='s1')
        host_api = APIClient()
        host_api.force_authenticate(user=self.host)
        response = host_api.post(f'/api/questions/{question.id}/mark_answered/')
        self.assertEqual(response.status_code, 200)
        question.refresh_from_db()
        self.assertTrue(question.is_answered)

    def test_mark_answered_denies_non_host(self):
        question = Question.objects.create(
            event=self.event, text='Mine?', author_session_id='s1')
        other = _create_user('other_qa')
        other_api = APIClient()
        other_api.force_authenticate(user=other)
        response = other_api.post(f'/api/questions/{question.id}/mark_answered/')
        self.assertEqual(response.status_code, 403)
        question.refresh_from_db()
        self.assertFalse(question.is_answered)

    def test_qa_toggle_switches_event_flags(self):
        host_api = APIClient()
        host_api.force_authenticate(user=self.host)
        response = host_api.post(f'/api/events/{self.event.event_code}/toggle_qa/')
        self.assertEqual(response.status_code, 200)
        self.event.refresh_from_db()
        self.assertFalse(self.event.qa_enabled)

    def test_questions_rejected_when_qa_disabled(self):
        self.event.qa_enabled = False
        self.event.save()
        response = self.anon.post(
            f'/api/events/{self.event.event_code}/questions/',
            {'text': 'Should be blocked'}, format='json')
        # Expected rejection after QA is turned off.
        self.assertIn(response.status_code, (400, 403))


class PollFlowTests(TestCase):
    """Multiple-choice, rating and word-cloud polling with one-vote-per-session."""

    def setUp(self):
        self.host = _create_user('host_poll')
        self.host_api = APIClient()
        self.host_api.force_authenticate(user=self.host)
        self.event = Event.objects.create(
            title='Poll Event', host=self.host, event_code='POLL', is_active=True)
        self.anon = APIClient()
        self.anon.get('/')

    def test_host_creates_multiple_choice_poll_with_options(self):
        response = self.host_api.post(
            f'/api/events/{self.event.event_code}/polls/',
            {'event': self.event.id, 'question_text': 'Pick a color',
             'poll_type': 'multiple-choice', 'options': ['Red', 'Green', 'Blue']},
            format='json')
        self.assertEqual(response.status_code, 201)
        poll = Poll.objects.get(question_text='Pick a color')
        self.assertEqual(poll.options.count(), 3)

    def test_non_host_cannot_create_poll(self):
        other = _create_user('other_poll')
        other_api = APIClient()
        other_api.force_authenticate(user=other)
        response = other_api.post(
            f'/api/events/{self.event.event_code}/polls/',
            {'event': self.event.id, 'question_text': 'Sneaky',
             'poll_type': 'multiple-choice', 'options': ['A']},
            format='json')
        self.assertEqual(response.status_code, 403)

    def test_only_one_active_poll_per_event(self):
        poll_a = Poll.objects.create(
            event=self.event, question_text='Poll A', poll_type='multiple-choice')
        poll_b = Poll.objects.create(
            event=self.event, question_text='Poll B', poll_type='multiple-choice')
        self.host_api.post(f'/api/polls/{poll_a.id}/toggle_active/')
        self.host_api.post(f'/api/polls/{poll_b.id}/toggle_active/')
        poll_a.refresh_from_db()
        poll_b.refresh_from_db()
        self.assertFalse(poll_a.is_active)
        self.assertTrue(poll_b.is_active)

    def test_toggle_active_poll_off(self):
        poll = Poll.objects.create(
            event=self.event, question_text='Turn off', poll_type='multiple-choice')
        self.host_api.post(f'/api/polls/{poll.id}/toggle_active/')
        self.host_api.post(f'/api/polls/{poll.id}/toggle_active/')
        poll.refresh_from_db()
        self.assertFalse(poll.is_active)

    def test_vote_counted_once_per_session(self):
        poll = Poll.objects.create(
            event=self.event, question_text='One vote?', poll_type='multiple-choice')
        opt = PollOption.objects.create(poll=poll, text='Yes')
        poll.is_active = True
        poll.save()
        first = self.anon.post('/api/votes/', {'poll_option': opt.id}, format='json')
        self.assertEqual(first.status_code, 201)
        second = self.anon.post('/api/votes/', {'poll_option': opt.id}, format='json')
        # A second vote from the same session must be rejected, not silently dropped.
        self.assertEqual(second.status_code, 400)
        self.assertEqual(Vote.objects.filter(poll_option=opt).count(), 1)

    def test_votes_from_distinct_sessions_counted(self):
        poll = Poll.objects.create(
            event=self.event, question_text='Many votes', poll_type='multiple-choice')
        opt = PollOption.objects.create(poll=poll, text='Yes')
        poll.is_active = True
        poll.save()
        self.anon.post('/api/votes/', {'poll_option': opt.id}, format='json')
        other = APIClient()
        other.get('/')
        self.assertEqual(
            other.post('/api/votes/', {'poll_option': opt.id}, format='json').status_code, 201)
        self.assertEqual(Vote.objects.filter(poll_option=opt).count(), 2)

    def test_vote_on_inactive_poll_rejected(self):
        poll = Poll.objects.create(
            event=self.event, question_text='Not live', poll_type='multiple-choice')
        opt = PollOption.objects.create(poll=poll, text='Yes')
        response = self.anon.post('/api/votes/', {'poll_option': opt.id}, format='json')
        # Voting on a poll that is not active should be refused.
        self.assertIn(response.status_code, (400, 403))
        self.assertEqual(Vote.objects.filter(poll_option=opt).count(), 0)

    def test_rating_updated_for_same_session(self):
        poll = Poll.objects.create(
            event=self.event, question_text='Rate the class', poll_type='rating')
        poll.is_active = True
        poll.save()
        first = self.anon.post(
            '/api/rating-responses/', {'poll': poll.id, 'rating': 3}, format='json')
        self.assertEqual(first.status_code, 201)
        second = self.anon.post(
            '/api/rating-responses/', {'poll': poll.id, 'rating': 5}, format='json')
        # The same participant re-rating should update their rating in place.
        self.assertIn(second.status_code, (200, 201))
        self.assertEqual(RatingResponse.objects.filter(poll=poll).count(), 1)
        self.assertEqual(RatingResponse.objects.get(poll=poll).rating, 5)

    def test_word_cloud_accepts_repeated_sessions(self):
        poll = Poll.objects.create(
            event=self.event, question_text='Say a word', poll_type='word-cloud')
        poll.is_active = True
        poll.save()
        self.anon.post('/api/word-responses/', {'poll': poll.id, 'text': 'energy'}, format='json')
        other = APIClient()
        other.get('/')
        other.post('/api/word-responses/', {'poll': poll.id, 'text': 'energy'}, format='json')
        self.assertEqual(WordCloudResponse.objects.filter(poll=poll).count(), 2)


class WebSocketFeatureTests(TransactionTestCase):
    """Real-time behaviour over the Channels WebSocket consumer.

    TransactionTestCase is used so rows created in setUp are visible to the
    worker threads the consumer runs on.
    """

    def setUp(self):
        self.host = _create_user('host_ws')
        self.event = Event.objects.create(
            title='WS Event', host=self.host, event_code='WS01', is_active=True)
        self.poll = Poll.objects.create(
            event=self.event, question_text='Which?', poll_type='multiple-choice')
        self.opt_a = PollOption.objects.create(poll=self.poll, text='Option A')
        self.opt_b = PollOption.objects.create(poll=self.poll, text='Option B')

        host_api = APIClient()
        host_api.force_login(self.host)
        self.host_session_key = host_api.session.session_key

    def _ws(self, path, session_key=None):
        headers = []
        if session_key:
            headers.append((b'cookie', f'sessionid={session_key}'.encode()))
        return WebsocketCommunicator(application, path, headers=headers)

    async def _connect(self, path, session_key=None):
        comm = self._ws(path, session_key)
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        return comm

    async def _drain_snapshot(self, comm):
        msg = await comm.receive_json_from()
        self.assertEqual(msg['type'], 'event_data')
        return msg

    async def test_ws_connect_receives_event_data(self):
        comm = await self._connect(f'/ws/event/{self.event.event_code}/')
        msg = await comm.receive_json_from()
        self.assertEqual(msg['type'], 'event_data')
        self.assertEqual(msg['event']['code'], self.event.event_code)
        await comm.disconnect()

    async def test_ws_unknown_event_is_rejected(self):
        comm = self._ws('/ws/event/UN01/')
        connected, _ = await comm.connect()
        self.assertFalse(connected)

    async def test_ws_question_submit_broadcasts(self):
        comm = await self._connect(f'/ws/event/{self.event.event_code}/')
        await self._drain_snapshot(comm)
        await comm.send_json_to({'type': 'question_submit', 'text': 'Ready for quiz?'})
        msg = await comm.receive_json_from()
        self.assertEqual(msg['type'], 'question_new')
        self.assertEqual(msg['question']['text'], 'Ready for quiz?')
        count = await database_sync_to_async(
            lambda: Question.objects.filter(event=self.event).count())()
        self.assertEqual(count, 1)
        await comm.disconnect()

    async def test_ws_question_upvote_broadcasts(self):
        question = await database_sync_to_async(Question.objects.create)(
            event=self.event, text='Upvote me', author_session_id='s1')
        comm = await self._connect(f'/ws/event/{self.event.event_code}/')
        await self._drain_snapshot(comm)
        await comm.send_json_to({'type': 'question_upvote', 'question_id': question.id})
        try:
            msg = await asyncio.wait_for(comm.receive_json_from(), timeout=2)
        except Exception:
            msg = None
        # Expected: broadcast question_upvote_update with count 1, socket stays open.
        self.assertIsNotNone(msg)
        self.assertEqual(msg.get('type'), 'question_upvote_update')
        self.assertEqual(msg.get('upvote_count'), 1)
        await comm.disconnect()

    async def test_ws_anonymous_cannot_activate_poll(self):
        comm = await self._connect(f'/ws/event/{self.event.event_code}/')
        await self._drain_snapshot(comm)
        await comm.send_json_to({'type': 'poll_activate', 'poll_id': self.poll.id})
        await comm.receive_nothing()
        active = await database_sync_to_async(
            lambda: Poll.objects.get(pk=self.poll.pk).is_active)()
        self.assertFalse(active)
        await comm.disconnect()

    async def test_ws_host_activates_poll(self):
        comm = await self._connect(f'/ws/event/{self.event.event_code}/', self.host_session_key)
        await self._drain_snapshot(comm)
        await comm.send_json_to({'type': 'poll_activate', 'poll_id': self.poll.id})
        msg = await comm.receive_json_from()
        self.assertEqual(msg['type'], 'poll_activated')
        self.assertEqual(msg['poll']['id'], self.poll.id)
        active = await database_sync_to_async(
            lambda: Poll.objects.get(pk=self.poll.pk).is_active)()
        self.assertTrue(active)
        await comm.disconnect()

    async def test_ws_poll_vote_broadcasts_results(self):
        active = await database_sync_to_async(
            lambda: Poll.objects.filter(pk=self.poll.pk).update(is_active=True))()
        comm = await self._connect(f'/ws/event/{self.event.event_code}/')
        await self._drain_snapshot(comm)
        await comm.send_json_to({
            'type': 'poll_vote',
            'poll_id': self.poll.id,
            'vote_data': {'option_id': self.opt_a.id},
        })
        msg = await comm.receive_json_from()
        self.assertEqual(msg['type'], 'poll_results_update')
        self.assertEqual(msg['results']['options'][0]['vote_count'], 1)
        count = await database_sync_to_async(
            lambda: Vote.objects.filter(poll_option=self.opt_a).count())()
        self.assertEqual(count, 1)
        await comm.disconnect()

    async def test_ws_word_cloud_vote_broadcasts_results(self):
        wc_poll = await database_sync_to_async(Poll.objects.create)(
            event=self.event, question_text='Say a word', poll_type='word-cloud')
        await database_sync_to_async(
            lambda: Poll.objects.filter(pk=wc_poll.pk).update(is_active=True))()
        comm = await self._connect(f'/ws/event/{self.event.event_code}/')
        await self._drain_snapshot(comm)
        await comm.send_json_to({
            'type': 'poll_vote',
            'poll_id': wc_poll.id,
            'vote_data': {'text': 'energy'},
        })
        msg = await comm.receive_json_from()
        self.assertEqual(msg['type'], 'poll_results_update')
        self.assertEqual(msg['results']['words'], [{'word': 'energy', 'count': 1}])
        count = await database_sync_to_async(
            lambda: WordCloudResponse.objects.filter(poll=wc_poll).count())()
        self.assertEqual(count, 1)
        await comm.disconnect()


class TemplateFeatureTests(TestCase):
    """The WebSocket paths emitted by the templates must use the event code."""

    def setUp(self):
        self.host = _create_user('host_tmpl')
        self.event = Event.objects.create(
            title='Big Test Event', host=self.host, event_code='TMPL', is_active=True)
        self.client.login(username='host_tmpl', password='testpass123')

    def test_participant_template_uses_event_code(self):
        response = self.client.get(reverse('event', args=[self.event.event_code]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn(f"const eventCode = '{self.event.event_code}'", html)

    def test_host_template_uses_event_code_not_title(self):
        response = self.client.get(reverse('host_event', args=[self.event.event_code]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        # The host page's WebSocket path must be built from the event code.
        self.assertIn(f"const eventCode = '{self.event.event_code}'", html)

    def test_participant_page_has_live_results_updater(self):
        response = self.client.get(reverse('event', args=[self.event.event_code]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        # Live poll results (incl. word cloud) must have a JS renderer on the
        # participant page so new entries update the display immediately.
        self.assertIn('function updatePollResults', html)
        self.assertIn('results.words', html)
        self.assertIn('word-cloud-display', html)
        self.assertNotIn(f"const eventCode = '{self.event.title}'", html)

    def test_host_view_requires_ownership(self):
        other = _create_user('other_tmpl')
        self.client.login(username='other_tmpl', password='testpass123')
        response = self.client.get(reverse('host_event', args=[self.event.event_code]))
        self.assertEqual(response.status_code, 404)


class WordCloudImageTests(TestCase):
    """Word-cloud polls render a real PNG from the word_cloud library."""

    PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'

    def setUp(self):
        self.host = _create_user('wcimg_host')
        self.event = Event.objects.create(title='WC', host=self.host, event_code='WCIM')
        self.poll = Poll.objects.create(
            event=self.event, question_text='Say a word', poll_type='word-cloud')

    def _url(self, poll=None, code=None):
        return reverse('poll-wordcloud', args=[
            code or self.event.event_code, (poll or self.poll).id])

    def test_renders_png_from_responses(self):
        WordCloudResponse.objects.create(
            poll=self.poll, text='energy', author_session_id='s1')
        WordCloudResponse.objects.create(
            poll=self.poll, text='energy', author_session_id='s2')
        WordCloudResponse.objects.create(
            poll=self.poll, text='team', author_session_id='s3')
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertTrue(response.content.startswith(self.PNG_SIGNATURE))

    def test_renders_placeholder_png_when_no_words(self):
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/png')
        self.assertTrue(response.content.startswith(self.PNG_SIGNATURE))

    def test_ignores_blank_texts(self):
        WordCloudResponse.objects.create(
            poll=self.poll, text='   ', author_session_id='s1')
        response = self.client.get(self._url())
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(self.PNG_SIGNATURE))

    def test_404_when_poll_belongs_to_other_event(self):
        other = Event.objects.create(title='Other WC', host=self.host, event_code='WOTH')
        other_poll = Poll.objects.create(
            event=other, question_text='x', poll_type='word-cloud')
        response = self.client.get(self._url(other_poll))
        self.assertEqual(response.status_code, 404)
        # And the reverse direction: an event code must not expose another poll.
        response = self.client.get(self._url(code='WOTH'))
        self.assertEqual(response.status_code, 404)

    def test_404_for_unknown_poll(self):
        response = self.client.get(reverse('poll-wordcloud', args=[self.event.event_code, 99999]))
        self.assertEqual(response.status_code, 404)

    def test_templates_reference_wordcloud_image_endpoint(self):
        # The participant page's live updater must point at the PNG endpoint.
        participant = self.client.get(reverse('event', args=[self.event.event_code]))
        self.assertEqual(participant.status_code, 200)
        html = participant.content.decode()
        self.assertIn('/polls/${poll.id}/wordcloud/', html)
        self.assertIn('word-cloud-display', html)

        # The host page embeds a rendered image for every word-cloud poll.
        self.client.login(username='wcimg_host', password='testpass123')
        host = self.client.get(reverse('host_event', args=[self.event.event_code]))
        self.assertEqual(host.status_code, 200)
        html = host.content.decode()
        self.assertIn(f'/api/events/{self.event.event_code}/polls/{self.poll.id}/wordcloud/',
                      html)

    def test_participant_server_renders_image_for_active_word_cloud(self):
        # The participant page must embed the rendered image directly when a
        # word-cloud poll is active at page-load time (no WS round trip needed).
        Poll.objects.filter(pk=self.poll.pk).update(is_active=True)
        response = self.client.get(reverse('event', args=[self.event.event_code]))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('<img id="word-cloud-display"', html)
        self.assertIn(f'/api/events/{self.event.event_code}/polls/{self.poll.id}/wordcloud/',
                      html)


class HostPresentationTests(TestCase):
    """The host page can expand Q&A or Polls to full width to present results."""

    def setUp(self):
        self.host = _create_user('pres_host')
        self.event = Event.objects.create(
            title='Pres Event', host=self.host, event_code='PRES', is_active=True)
        self.client.login(username='pres_host', password='testpass123')

    def _html(self):
        response = self.client.get(reverse('host_event', args=[self.event.event_code]))
        self.assertEqual(response.status_code, 200)
        return response.content.decode()

    def test_both_panels_have_expand_toggles(self):
        html = self._html()
        self.assertIn('<div class="col-lg-6 mb-4" id="qa-panel-column">', html)
        self.assertIn('<div class="col-lg-6 mb-4" id="polls-panel-column">', html)
        self.assertIn('id="qa-expand-btn"', html)
        self.assertIn('id="polls-expand-btn"', html)

    def test_toggle_expands_to_full_width_and_restores(self):
        html = self._html()
        self.assertIn('function setPresentationMode', html)
        self.assertIn('setPresentationMode(\'qa\')', html)
        self.assertIn('setPresentationMode(\'polls\')', html)
        # Expanding removes the half-width class and applies full width.
        self.assertIn("qaCol.classList.remove('col-lg-6')", html)
        self.assertIn("qaCol.classList.add('col-lg-12')", html)
        self.assertIn("pollsCol.classList.remove('col-lg-6')", html)
        self.assertIn("pollsCol.classList.add('col-lg-12')", html)
        # The companion panel is hidden while presenting.
        self.assertIn("pollsCol.style.display = 'none'", html)
        self.assertIn("qaCol.style.display = 'none'", html)
        # A second click must restore the side-by-side layout.
        self.assertIn("qaCol.classList.add('col-lg-6')", html)
        self.assertIn("pollsCol.classList.add('col-lg-6')", html)
        self.assertIn('fa-compress', html)