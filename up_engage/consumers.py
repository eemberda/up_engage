import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from .models import Event, Question, Poll


class EventConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time event updates"""
    
    async def connect(self):
        print(f"WebSocket connect attempt for event: {self.scope['url_route']['kwargs']['event_code']}")
        self.event_code = self.scope['url_route']['kwargs']['event_code']
        self.event_group_name = f'event_{self.event_code}'
        
        # Verify event exists
        try:
            event_exists = await self.event_exists(self.event_code)
            print(f"Event exists: {event_exists}")
            if not event_exists:
                print(f"Event {self.event_code} not found, closing connection")
                await self.close()
                return
        except Exception as e:
            print(f"Error checking event existence: {e}")
            await self.close()
            return
        
        # Join event group
        await self.channel_layer.group_add(
            self.event_group_name,
            self.channel_name
        )
        
        print(f"Accepting WebSocket connection for event {self.event_code}")
        await self.accept()
        
        # Send initial event data
        await self.send_event_data()
    
    async def disconnect(self, close_code):
        # Leave event group
        await self.channel_layer.group_discard(
            self.event_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'question_submit':
                await self.handle_question_submit(data)
            elif message_type == 'question_upvote':
                await self.handle_question_upvote(data)
            elif message_type == 'poll_vote':
                await self.handle_poll_vote(data)
            elif message_type == 'poll_activate':
                await self.handle_poll_activate(data)
            elif message_type == 'question_mark_answered':
                await self.handle_question_mark_answered(data)
            elif message_type == 'qa_toggle':
                await self.handle_qa_toggle(data)
            
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
    
    async def handle_question_submit(self, data):
        """Handle new question submission"""
        question_text = data.get('text', '').strip()
        if not question_text:
            return
        
        # Create question
        question = await self.create_question(question_text)
        if question:
            # Broadcast new question to all participants
            await self.channel_layer.group_send(
                self.event_group_name,
                {
                    'type': 'question_new',
                    'question': {
                        'id': question.id,
                        'text': question.text,
                        'upvote_count': 0,
                        'is_answered': False,
                        'created_at': question.created_at.isoformat()
                    }
                }
            )
    
    async def handle_question_upvote(self, data):
        """Handle question upvote"""
        question_id = data.get('question_id')
        if question_id:
            result = await self.toggle_question_upvote(question_id)
            if result:
                # Broadcast upvote update
                await self.channel_layer.group_send(
                    self.event_group_name,
                    {
                        'type': 'question_upvote_update',
                        'question_id': question_id,
                        'upvote_count': result['upvote_count']
                    }
                )
    
    async def handle_poll_vote(self, data):
        """Handle poll voting"""
        poll_id = data.get('poll_id')
        vote_data = data.get('vote_data')
        
        if poll_id and vote_data:
            success = await self.submit_poll_vote(poll_id, vote_data)
            if success:
                # Broadcast poll results update
                poll_results = await self.get_poll_results(poll_id)
                await self.channel_layer.group_send(
                    self.event_group_name,
                    {
                        'type': 'poll_results_update',
                        'poll_id': poll_id,
                        'results': poll_results
                    }
                )
    
    async def handle_poll_activate(self, data):
        """Handle poll activation (host only)"""
        poll_id = data.get('poll_id')
        user = self.scope.get('user')
        
        if poll_id and user and not isinstance(user, AnonymousUser):
            success = await self.activate_poll(poll_id, user)
            if success:
                poll_data = await self.get_poll_data(poll_id)
                # Broadcast poll activation
                await self.channel_layer.group_send(
                    self.event_group_name,
                    {
                        'type': 'poll_activated',
                        'poll': poll_data
                    }
                )
    
    async def handle_question_mark_answered(self, data):
        """Handle marking question as answered (host only)"""
        question_id = data.get('question_id')
        user = self.scope.get('user')
        
        if question_id and user and not isinstance(user, AnonymousUser):
            result = await self.mark_question_answered(question_id, user)
            if result is not None:
                # Broadcast question status update
                await self.channel_layer.group_send(
                    self.event_group_name,
                    {
                        'type': 'question_answered_update',
                        'question_id': question_id,
                        'is_answered': result
                    }
                )
    
    async def handle_qa_toggle(self, data):
        """Handle Q&A toggle (host only)"""
        user = self.scope.get('user')
        
        if user and not isinstance(user, AnonymousUser):
            qa_enabled = await self.toggle_qa(user)
            if qa_enabled is not None:
                # Broadcast Q&A status update
                await self.channel_layer.group_send(
                    self.event_group_name,
                    {
                        'type': 'qa_status_update',
                        'qa_enabled': qa_enabled
                    }
                )
    
    # WebSocket message handlers
    async def question_new(self, event):
        """Send new question to WebSocket"""
        await self.send(text_data=json.dumps(event))
    
    async def question_upvote_update(self, event):
        """Send question upvote update to WebSocket"""
        await self.send(text_data=json.dumps(event))
    
    async def question_answered_update(self, event):
        """Send question answered status update to WebSocket"""
        await self.send(text_data=json.dumps(event))
    
    async def poll_activated(self, event):
        """Send poll activation to WebSocket"""
        await self.send(text_data=json.dumps(event))
    
    async def poll_results_update(self, event):
        """Send poll results update to WebSocket"""
        await self.send(text_data=json.dumps(event))
    
    async def qa_status_update(self, event):
        """Send Q&A status update to WebSocket"""
        await self.send(text_data=json.dumps(event))
    
    # Database operations
    @database_sync_to_async
    def event_exists(self, event_code):
        return Event.objects.filter(event_code=event_code, is_active=True).exists()
    
    @database_sync_to_async
    def create_question(self, text):
        try:
            event = Event.objects.get(event_code=self.event_code, is_active=True)
            
            # Get or create session key
            session_key = self.scope.get('session', {}).get('session_key')
            if not session_key:
                session_key = 'anonymous'
            
            question = Question.objects.create(
                event=event,
                text=text,
                author_session_id=session_key
            )
            return question
        except Event.DoesNotExist:
            return None
    
    @database_sync_to_async
    def toggle_question_upvote(self, question_id):
        try:
            from .models import QuestionUpvote
            
            question = Question.objects.get(id=question_id)
            session_key = self.scope.get('session', {}).get('session_key', 'anonymous')
            
            upvote, created = QuestionUpvote.objects.get_or_create(
                question=question,
                session_id=session_key
            )
            
            if not created:
                upvote.delete()
            
            return {'upvote_count': question.upvote_count}
        except Question.DoesNotExist:
            return None
    
    @database_sync_to_async
    def submit_poll_vote(self, poll_id, vote_data):
        try:
            poll = Poll.objects.get(id=poll_id, is_active=True)
            
            # Debug: print session info
            print(f"Session scope: {self.scope.get('session')}")
            print(f"Cookies: {self.scope.get('cookies')}")
            
            # Get session key, or create one based on client info for anonymous users
            session_key = self.scope.get('session', {}).get('session_key')
            if not session_key:
                # Try to get session from cookies
                cookies = self.scope.get('cookies', {})
                session_key = cookies.get('sessionid') or cookies.get('django_session')
                
            if not session_key:
                # For anonymous WebSocket users, use client IP + user agent as identifier
                client_ip = self.scope.get('client', ['unknown'])[0]
                user_agent = 'unknown'
                for header_name, header_value in self.scope.get('headers', []):
                    if header_name == b'user-agent':
                        user_agent = header_value.decode('utf-8', errors='ignore')
                        break
                session_key = f"anon_{client_ip}_{hash(user_agent) % 10000}"
            
            print(f"Using session key: {session_key}")
            
            if poll.poll_type == 'multiple-choice':
                from .models import Vote, PollOption
                option_id = vote_data.get('option_id')
                option = PollOption.objects.get(id=option_id, poll=poll)
                
                vote, created = Vote.objects.get_or_create(
                    poll_option=option,
                    author_session_id=session_key
                )
                print(f"Vote created: {created}, Total votes for option: {option.vote_count}")
                
            elif poll.poll_type == 'rating':
                from .models import RatingResponse
                rating = vote_data.get('rating')
                
                RatingResponse.objects.update_or_create(
                    poll=poll,
                    author_session_id=session_key,
                    defaults={'rating': rating}
                )
                
            elif poll.poll_type == 'word-cloud':
                from .models import WordCloudResponse
                text = vote_data.get('text', '').strip()
                
                if text:
                    WordCloudResponse.objects.create(
                        poll=poll,
                        text=text,
                        author_session_id=session_key
                    )
            
            return True
        except (Poll.DoesNotExist, Exception) as e:
            print(f"Error in submit_poll_vote: {e}")
            return False
    
    @database_sync_to_async
    def get_poll_results(self, poll_id):
        try:
            poll = Poll.objects.get(id=poll_id)
            
            if poll.poll_type == 'multiple-choice':
                options = []
                for option in poll.options.all():
                    options.append({
                        'id': option.id,
                        'text': option.text,
                        'vote_count': option.vote_count
                    })
                return {'options': options}
                
            elif poll.poll_type == 'rating':
                responses = list(poll.rating_responses.values_list('rating', flat=True))
                return {'ratings': responses}
                
            elif poll.poll_type == 'word-cloud':
                # Get all word responses and count duplicates
                from collections import Counter
                words = list(poll.word_responses.values_list('text', flat=True))
                word_counts = Counter(words)
                # Convert to list of dictionaries with word and count
                word_data = [{'word': word, 'count': count} for word, count in word_counts.items()]
                return {'words': word_data}
                
        except Poll.DoesNotExist:
            return {}
    
    @database_sync_to_async
    def activate_poll(self, poll_id, user):
        try:
            poll = Poll.objects.get(id=poll_id)
            if poll.event.host != user:
                return False
            
            # Deactivate other polls in the same event
            Poll.objects.filter(event=poll.event, is_active=True).update(is_active=False)
            
            # Activate this poll
            poll.is_active = True
            poll.save()
            
            return True
        except Poll.DoesNotExist:
            return False
    
    @database_sync_to_async
    def get_poll_data(self, poll_id):
        try:
            poll = Poll.objects.get(id=poll_id)
            data = {
                'id': poll.id,
                'question_text': poll.question_text,
                'poll_type': poll.poll_type,
                'is_active': poll.is_active
            }
            
            if poll.poll_type == 'multiple-choice':
                data['options'] = [
                    {'id': opt.id, 'text': opt.text}
                    for opt in poll.options.all()
                ]
            
            return data
        except Poll.DoesNotExist:
            return {}
    
    @database_sync_to_async
    def mark_question_answered(self, question_id, user):
        try:
            question = Question.objects.get(id=question_id)
            if question.event.host != user:
                return None
            
            question.is_answered = not question.is_answered
            question.save()
            
            return question.is_answered
        except Question.DoesNotExist:
            return None
    
    @database_sync_to_async
    def toggle_qa(self, user):
        try:
            event = Event.objects.get(event_code=self.event_code, host=user)
            event.qa_enabled = not event.qa_enabled
            event.save()
            return event.qa_enabled
        except Event.DoesNotExist:
            return None
    
    @database_sync_to_async
    def send_event_data(self):
        """Send initial event data when user connects"""
        try:
            event = Event.objects.get(event_code=self.event_code, is_active=True)
            
            # Get questions with upvote counts
            questions = []
            # Use annotation to count upvotes for proper ordering
            from django.db.models import Count
            questions_qs = event.questions.all().annotate(
                upvote_count_field=Count('upvotes')
            ).order_by('-upvote_count_field', '-created_at')
            
            for q in questions_qs:
                questions.append({
                    'id': q.id,
                    'text': q.text,
                    'upvote_count': q.upvote_count_field,  # Use annotated field
                    'is_answered': q.is_answered,
                    'created_at': q.created_at.isoformat()
                })
            
            # Get active poll
            active_poll = None
            active_poll_obj = event.polls.filter(is_active=True).first()
            if active_poll_obj:
                active_poll = {
                    'id': active_poll_obj.id,
                    'question_text': active_poll_obj.question_text,
                    'poll_type': active_poll_obj.poll_type,
                    'is_active': active_poll_obj.is_active
                }
                
                if active_poll_obj.poll_type == 'multiple-choice':
                    active_poll['options'] = [
                        {'id': opt.id, 'text': opt.text, 'vote_count': opt.vote_count}
                        for opt in active_poll_obj.options.all()
                    ]
                elif active_poll_obj.poll_type == 'word-cloud':
                    # Get all word responses and count duplicates
                    from collections import Counter
                    words = list(active_poll_obj.word_responses.values_list('text', flat=True))
                    word_counts = Counter(words)
                    word_data = [{'word': word, 'count': count} for word, count in word_counts.items()]
                    active_poll['words'] = word_data
                elif active_poll_obj.poll_type == 'rating':
                    ratings = list(active_poll_obj.rating_responses.values_list('rating', flat=True))
                    active_poll['ratings'] = ratings
            
            return {
                'type': 'event_data',
                'event': {
                    'code': event.event_code,
                    'title': event.title,
                    'description': event.description,
                    'qa_enabled': event.qa_enabled
                },
                'questions': questions,
                'active_poll': active_poll
            }
            
        except Event.DoesNotExist:
            return None