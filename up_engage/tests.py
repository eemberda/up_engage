from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from .models import Event, Question, Poll, PollOption, Vote, QuestionUpvote


class EventModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_event_creation(self):
        """Test that events are created with unique codes"""
        event = Event.objects.create(
            title='Test Event',
            description='Test Description',
            host=self.user
        )
        self.assertTrue(len(event.event_code) >= 4)
        self.assertEqual(event.title, 'Test Event')
        self.assertEqual(event.host, self.user)
        self.assertTrue(event.is_active)

    def test_event_code_uniqueness(self):
        """Test that event codes are unique"""
        event1 = Event.objects.create(
            title='Event 1',
            host=self.user
        )
        event2 = Event.objects.create(
            title='Event 2',
            host=self.user
        )
        self.assertNotEqual(event1.event_code, event2.event_code)


class QuestionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.event = Event.objects.create(
            title='Test Event',
            host=self.user
        )

    def test_question_creation(self):
        """Test question creation"""
        question = Question.objects.create(
            event=self.event,
            text='Test question?',
            author_session_id='test_session'
        )
        self.assertEqual(question.text, 'Test question?')
        self.assertEqual(question.event, self.event)
        self.assertFalse(question.is_answered)

    def test_question_upvote(self):
        """Test question upvoting"""
        question = Question.objects.create(
            event=self.event,
            text='Test question?',
            author_session_id='test_session'
        )
        
        # Add upvote
        upvote = QuestionUpvote.objects.create(
            question=question,
            session_id='voter_session'
        )
        
        self.assertEqual(question.get_upvote_count(), 1)


class PollModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.event = Event.objects.create(
            title='Test Event',
            host=self.user
        )

    def test_poll_creation(self):
        """Test poll creation"""
        poll = Poll.objects.create(
            event=self.event,
            question_text='What is your favorite color?',
            poll_type='multiple-choice'
        )
        self.assertEqual(poll.question_text, 'What is your favorite color?')
        self.assertEqual(poll.poll_type, 'multiple-choice')
        self.assertFalse(poll.is_active)

    def test_poll_with_options(self):
        """Test poll with options and voting"""
        poll = Poll.objects.create(
            event=self.event,
            question_text='What is your favorite color?',
            poll_type='multiple-choice'
        )
        
        option1 = PollOption.objects.create(
            poll=poll,
            text='Red'
        )
        option2 = PollOption.objects.create(
            poll=poll,
            text='Blue'
        )
        
        # Add votes
        Vote.objects.create(
            poll_option=option1,
            author_session_id='session1'
        )
        Vote.objects.create(
            poll_option=option1,
            author_session_id='session2'
        )
        Vote.objects.create(
            poll_option=option2,
            author_session_id='session3'
        )
        
        self.assertEqual(option1.vote_count, 2)
        self.assertEqual(option2.vote_count, 1)


class ViewsTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_home_view(self):
        """Test home page loads"""
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SlidoClone')

    def test_login_view(self):
        """Test login functionality"""
        response = self.client.post(reverse('login'), {
            'username': 'testuser',
            'password': 'testpass123'
        })
        self.assertEqual(response.status_code, 302)  # Redirect after login

    def test_dashboard_requires_login(self):
        """Test that dashboard requires authentication"""
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 302)  # Redirect to login

    def test_dashboard_with_login(self):
        """Test dashboard with authenticated user"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_event_join_with_valid_code(self):
        """Test joining event with valid code"""
        event = Event.objects.create(
            title='Test Event',
            host=self.user,
            is_active=True
        )
        
        response = self.client.post(reverse('home'), {
            'event_code': event.event_code
        })
        self.assertEqual(response.status_code, 302)  # Redirect to event

    def test_event_join_with_invalid_code(self):
        """Test joining event with invalid code"""
        response = self.client.post(reverse('home'), {
            'event_code': 'INVALID'
        })
        self.assertEqual(response.status_code, 200)  # Stay on home page
        self.assertContains(response, 'Event not found')


class APITest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        self.event = Event.objects.create(
            title='Test Event',
            host=self.user,
            is_active=True
        )

    def test_event_api_list(self):
        """Test event API list endpoint"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get('/api/events/')
        self.assertEqual(response.status_code, 200)

    def test_event_api_create(self):
        """Test event creation via API"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post('/api/events/', {
            'title': 'New Event',
            'description': 'New Description'
        }, content_type='application/json')
        self.assertEqual(response.status_code, 201)

    def test_question_creation_api(self):
        """Test question creation via API"""
        import json
        
        # Create a session by making a simple request first
        self.client.get('/')  # This creates a session
        
        response = self.client.post(f'/api/events/{self.event.event_code}/questions/', 
            json.dumps({'text': 'Test question via API?'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 201)
        
        # Verify question was created
        question = Question.objects.filter(text='Test question via API?').first()
        self.assertIsNotNone(question)


class IntegrationTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )

    def test_full_event_workflow(self):
        """Test complete event workflow"""
        import json
        
        # Login
        self.client.login(username='testuser', password='testpass123')
        
        # Create event
        response = self.client.post('/api/events/', 
            json.dumps({
                'title': 'Integration Test Event',
                'description': 'Testing full workflow'
            }), content_type='application/json')
        self.assertEqual(response.status_code, 201)
        
        event_data = response.json()
        event_code = event_data['event_code']
        
        # Join event as participant
        client2 = Client()
        # Create session by making a simple request
        client2.get('/')
        
        response = client2.post(reverse('home'), {
            'event_code': event_code
        })
        self.assertEqual(response.status_code, 302)
        
        # Submit question as participant
        response = client2.post(f'/api/events/{event_code}/questions/', 
            json.dumps({'text': 'Integration test question?'}),
            content_type='application/json')
        self.assertEqual(response.status_code, 201)
        
        # Verify question appears for host
        response = self.client.get(f'/api/events/{event_code}/questions/')
        self.assertEqual(response.status_code, 200)
        questions = response.json()['results']
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]['text'], 'Integration test question?')
