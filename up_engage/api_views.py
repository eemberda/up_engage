from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView
from rest_framework.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from django.db.models import Count, F
import os
from .models import (
    Event, Question, QuestionUpvote, Poll, PollOption, 
    Vote, WordCloudResponse, RatingResponse
)
from .serializers import (
    EventSerializer, QuestionSerializer, QuestionCreateSerializer, QuestionUpvoteSerializer,
    PollSerializer, CreatePollSerializer, PollOptionSerializer, 
    VoteSerializer, WordCloudResponseSerializer, RatingResponseSerializer
)


class IsHostOrReadOnly(permissions.BasePermission):
    """Custom permission to only allow hosts to edit their events"""
    
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Write permissions are only allowed to the host of the event
        if hasattr(obj, 'host'):
            return obj.host == request.user
        elif hasattr(obj, 'event'):
            return obj.event.host == request.user
        return False


class EventViewSet(viewsets.ModelViewSet):
    """ViewSet for managing events"""
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsHostOrReadOnly]
    lookup_field = 'event_code'
    
    def get_queryset(self):
        if self.action == 'list' and self.request.user.is_authenticated:
            # For authenticated users, show only their events
            return Event.objects.filter(host=self.request.user)
        return super().get_queryset()
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def toggle_active(self, request, event_code=None):
        """Toggle event active status"""
        event = self.get_object()
        if event.host != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        event.is_active = not event.is_active
        event.save()
        return Response({'is_active': event.is_active})
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def toggle_qa(self, request, event_code=None):
        """Toggle Q&A enabled status"""
        event = self.get_object()
        if event.host != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        event.qa_enabled = not event.qa_enabled
        event.save()
        return Response({'qa_enabled': event.qa_enabled})


class QuestionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing questions"""
    queryset = Question.objects.all()
    serializer_class = QuestionSerializer
    permission_classes = [permissions.AllowAny]
    
    def get_queryset(self):
        event_code = self.request.query_params.get('event_code')
        if event_code:
            return Question.objects.filter(event__event_code=event_code).annotate(
                upvote_count=Count('upvotes')
            ).order_by('-upvote_count', '-created_at')
        return super().get_queryset()
    
    def perform_create(self, serializer):
        # Ensure session exists
        if not self.request.session.session_key:
            self.request.session.create()
        
        serializer.save(author_session_id=self.request.session.session_key)
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def mark_answered(self, request, pk=None):
        """Mark question as answered (host only)"""
        question = self.get_object()
        if question.event.host != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        question.is_answered = not question.is_answered
        question.save()
        return Response({'is_answered': question.is_answered})


class PollViewSet(viewsets.ModelViewSet):
    """ViewSet for managing polls"""
    queryset = Poll.objects.all()
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsHostOrReadOnly]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return CreatePollSerializer
        return PollSerializer
    
    def get_queryset(self):
        event_code = self.request.query_params.get('event_code')
        if event_code:
            return Poll.objects.filter(event__event_code=event_code)
        return super().get_queryset()
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def toggle_active(self, request, pk=None):
        """Toggle poll active status"""
        poll = self.get_object()
        if poll.event.host != request.user:
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
        # Deactivate other polls in the same event if activating this one
        if not poll.is_active:
            Poll.objects.filter(event=poll.event, is_active=True).update(is_active=False)
        
        poll.is_active = not poll.is_active
        poll.save()
        return Response({'is_active': poll.is_active})


class PollOptionViewSet(viewsets.ModelViewSet):
    """ViewSet for managing poll options"""
    queryset = PollOption.objects.all()
    serializer_class = PollOptionSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsHostOrReadOnly]


class VoteViewSet(viewsets.ModelViewSet):
    """ViewSet for managing votes"""
    queryset = Vote.objects.all()
    serializer_class = VoteSerializer
    permission_classes = [permissions.AllowAny]
    http_method_names = ['get', 'post', 'delete']  # No PUT/PATCH for votes
    
    def perform_create(self, serializer):
        # Ensure session exists
        if not self.request.session.session_key:
            self.request.session.create()
        
        option = serializer.validated_data['poll_option']
        if not option.poll.is_active:
            raise PermissionDenied('This poll is not active.')
        
        session_key = self.request.session.session_key
        if Vote.objects.filter(poll_option=option, author_session_id=session_key).exists():
            raise ValidationError('You have already voted for this option.')
        
        serializer.save(author_session_id=session_key)


class WordCloudResponseViewSet(viewsets.ModelViewSet):
    """ViewSet for managing word cloud responses"""
    queryset = WordCloudResponse.objects.all()
    serializer_class = WordCloudResponseSerializer
    permission_classes = [permissions.AllowAny]
    http_method_names = ['get', 'post', 'delete']
    
    def perform_create(self, serializer):
        # Ensure session exists
        if not self.request.session.session_key:
            self.request.session.create()
        
        poll = serializer.validated_data['poll']
        if not poll.is_active:
            raise PermissionDenied('This poll is not active.')
        
        serializer.save(author_session_id=self.request.session.session_key)


class RatingResponseViewSet(viewsets.ModelViewSet):
    """ViewSet for managing rating responses"""
    queryset = RatingResponse.objects.all()
    serializer_class = RatingResponseSerializer
    permission_classes = [permissions.AllowAny]
    http_method_names = ['get', 'post', 'delete']
    
    def perform_create(self, serializer):
        # Ensure session exists
        if not self.request.session.session_key:
            self.request.session.create()
        
        poll = serializer.validated_data['poll']
        if not poll.is_active:
            raise PermissionDenied('This poll is not active.')
        
        # Re-rating by the same session updates their rating in place.
        RatingResponse.objects.update_or_create(
            poll=poll,
            author_session_id=self.request.session.session_key,
            defaults={'rating': serializer.validated_data['rating']}
        )


class EventQuestionsView(ListCreateAPIView):
    """List and create questions for a specific event"""
    permission_classes = [permissions.AllowAny]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return QuestionCreateSerializer
        return QuestionSerializer
    
    def get_queryset(self):
        event_code = self.kwargs['event_code']
        return Question.objects.filter(event__event_code=event_code).annotate(
            upvote_count=Count('upvotes')
        ).order_by('-upvote_count', '-created_at')
    
    def perform_create(self, serializer):
        event_code = self.kwargs['event_code']
        event = get_object_or_404(Event, event_code=event_code)
        
        # Reject questions when Q&A is disabled
        if not event.qa_enabled:
            raise PermissionDenied('Q&A is disabled for this event.')
        
        # Ensure session exists
        if not self.request.session.session_key:
            self.request.session.create()
        
        serializer.save(
            event=event,
            author_session_id=self.request.session.session_key
        )


class EventPollsView(ListCreateAPIView):
    """List and create polls for a specific event"""
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CreatePollSerializer
        return PollSerializer
    
    def get_queryset(self):
        event_code = self.kwargs['event_code']
        return Poll.objects.filter(event__event_code=event_code)
    
    def perform_create(self, serializer):
        event_code = self.kwargs['event_code']
        event = get_object_or_404(Event, event_code=event_code)
        
        # Check if user is the host
        if event.host != self.request.user:
            raise PermissionDenied('You must be the event host to create polls.')
        
        serializer.save(event=event)


class QuestionUpvoteView(APIView):
    """Handle question upvoting"""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request, question_id):
        question = get_object_or_404(Question, id=question_id)
        
        # Ensure session exists
        if not request.session.session_key:
            request.session.create()
        
        session_id = request.session.session_key
        
        # Check if user already upvoted
        upvote, created = QuestionUpvote.objects.get_or_create(
            question=question,
            session_id=session_id
        )
        
        if created:
            return Response({'upvoted': True, 'upvote_count': question.get_upvote_count()})
        else:
            # Remove upvote
            upvote.delete()
            return Response({'upvoted': False, 'upvote_count': question.get_upvote_count()})


class WordCloudImageView(APIView):
    """Render word-cloud poll responses as a PNG using the word_cloud library.

    GET /api/events/<event_code>/polls/<poll_id>/wordcloud/
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request, event_code, poll_id):
        poll = get_object_or_404(
            Poll, id=poll_id, event__event_code=event_code.strip().upper())

        from collections import Counter
        frequencies = Counter(poll.word_responses.values_list('text', flat=True))
        frequencies = {word: count for word, count in frequencies.items() if word}

        from django.http import HttpResponse
        response = HttpResponse(
            _render_word_cloud(frequencies), content_type='image/png')
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response


def _render_word_cloud(frequencies):
    """Return PNG bytes for the given word->count mapping."""
    from io import BytesIO
    from PIL import Image
    from wordcloud import WordCloud

    font_path = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    if not os.path.exists(font_path):
        # Fall back to the library's bundled font (ASCII only).
        font_path = None

    if not frequencies:
        return _placeholder_word_cloud_png(font_path, 'No words yet')

    wordcloud = WordCloud(
        font_path=font_path,
        width=1000, height=500,
        background_color='white',
        colormap='viridis',
        collocations=False,
        random_state=42,
        min_font_size=10,
        prefer_horizontal=0.8,
    )
    wordcloud.generate_from_frequencies(frequencies)

    buffer = BytesIO()
    wordcloud.to_image().save(buffer, format='PNG')
    return buffer.getvalue()


def _placeholder_word_cloud_png(font_path, text):
    """Return a small centered-message PNG when a poll has no responses yet."""
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new('RGB', (1000, 300), (248, 249, 250))
    draw = ImageDraw.Draw(image)
    if font_path and os.path.exists(font_path):
        font = ImageFont.truetype(font_path, 44)
    else:
        font = ImageFont.load_default()
    draw.text((200, 120), text, fill=(108, 117, 125), font=font)

    buffer = BytesIO()
    image.save(buffer, format='PNG')
    return buffer.getvalue()