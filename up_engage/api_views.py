from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView
from django.shortcuts import get_object_or_404
from django.db.models import Count, F
from django.db import IntegrityError
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
        
        try:
            serializer.save(author_session_id=self.request.session.session_key)
        except IntegrityError:
            # User already voted for this option
            return Response(
                {'error': 'You have already voted for this option'}, 
                status=status.HTTP_400_BAD_REQUEST
            )


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
        
        try:
            serializer.save(author_session_id=self.request.session.session_key)
        except IntegrityError:
            # User already rated this poll
            return Response(
                {'error': 'You have already rated this poll'}, 
                status=status.HTTP_400_BAD_REQUEST
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
        
        # Ensure session exists
        if not self.request.session.session_key:
            self.request.session.create()
        
        serializer.save(
            event=event,
            author_session_id=self.request.session.session_key
        )


class EventPollsView(ListCreateAPIView):
    """List and create polls for a specific event"""
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    
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
            return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
        
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
            return Response({'upvoted': True, 'upvote_count': question.upvote_count})
        else:
            # Remove upvote
            upvote.delete()
            return Response({'upvoted': False, 'upvote_count': question.upvote_count})