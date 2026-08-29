from rest_framework import serializers
from django.contrib.auth.models import User
from .models import (
    Event, Question, QuestionUpvote, Poll, PollOption, 
    Vote, WordCloudResponse, RatingResponse
)


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']


class EventSerializer(serializers.ModelSerializer):
    host = UserSerializer(read_only=True)
    question_count = serializers.SerializerMethodField()
    poll_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Event
        fields = ['id', 'title', 'description', 'event_code', 'host', 
                 'is_active', 'created_at', 'updated_at', 'question_count', 'poll_count']
        read_only_fields = ['event_code', 'created_at', 'updated_at']
    
    def get_question_count(self, obj):
        return obj.questions.count()
    
    def get_poll_count(self, obj):
        return obj.polls.count()
    
    def create(self, validated_data):
        validated_data['host'] = self.context['request'].user
        return super().create(validated_data)


class QuestionUpvoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = QuestionUpvote
        fields = ['id', 'session_id', 'created_at']


class QuestionSerializer(serializers.ModelSerializer):
    upvote_count = serializers.SerializerMethodField()
    user_upvoted = serializers.SerializerMethodField()
    event_code = serializers.CharField(source='event.event_code', read_only=True)
    
    class Meta:
        model = Question
        fields = ['id', 'event', 'event_code', 'text', 'author_session_id', 
                 'is_answered', 'created_at', 'updated_at', 'upvote_count', 'user_upvoted']
        read_only_fields = ['created_at', 'updated_at']
    
    def get_upvote_count(self, obj):
        if hasattr(obj, 'upvote_count'):
            return obj.upvote_count
        return obj.get_upvote_count()
    
    def get_user_upvoted(self, obj):
        request = self.context.get('request')
        if request and hasattr(request, 'session'):
            session_id = request.session.session_key
            if session_id:
                return obj.upvotes.filter(session_id=session_id).exists()
        return False


class QuestionCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating questions without requiring event and author_session_id"""
    
    class Meta:
        model = Question
        fields = ['text']  # Only require text field


class PollOptionSerializer(serializers.ModelSerializer):
    vote_count = serializers.SerializerMethodField()
    
    class Meta:
        model = PollOption
        fields = ['id', 'poll', 'text', 'vote_count', 'created_at']
        read_only_fields = ['created_at']
    
    def get_vote_count(self, obj):
        return obj.vote_count


class PollSerializer(serializers.ModelSerializer):
    options = PollOptionSerializer(many=True, read_only=True)
    event_code = serializers.CharField(source='event.event_code', read_only=True)
    total_votes = serializers.SerializerMethodField()
    
    class Meta:
        model = Poll
        fields = ['id', 'event', 'event_code', 'question_text', 'poll_type', 
                 'is_active', 'created_at', 'updated_at', 'options', 'total_votes']
        read_only_fields = ['created_at', 'updated_at']
    
    def get_total_votes(self, obj):
        if obj.poll_type == 'multiple-choice':
            return sum(option.vote_count for option in obj.options.all())
        elif obj.poll_type == 'rating':
            return obj.rating_responses.count()
        elif obj.poll_type == 'word-cloud':
            return obj.word_responses.count()
        return 0


class VoteSerializer(serializers.ModelSerializer):
    poll_option_text = serializers.CharField(source='poll_option.text', read_only=True)
    
    class Meta:
        model = Vote
        fields = ['id', 'poll_option', 'poll_option_text', 'author_session_id', 'created_at']
        read_only_fields = ['created_at', 'author_session_id']


class WordCloudResponseSerializer(serializers.ModelSerializer):
    poll_question = serializers.CharField(source='poll.question_text', read_only=True)
    
    class Meta:
        model = WordCloudResponse
        fields = ['id', 'poll', 'poll_question', 'text', 'author_session_id', 'created_at']
        read_only_fields = ['created_at', 'author_session_id']


class RatingResponseSerializer(serializers.ModelSerializer):
    poll_question = serializers.CharField(source='poll.question_text', read_only=True)
    
    class Meta:
        model = RatingResponse
        fields = ['id', 'poll', 'poll_question', 'rating', 'author_session_id', 'created_at']
        read_only_fields = ['created_at', 'author_session_id']


class CreatePollSerializer(serializers.ModelSerializer):
    """Serializer for creating polls with options"""
    options = serializers.ListField(
        child=serializers.CharField(max_length=200),
        required=False,
        allow_empty=True,
        write_only=True
    )
    
    class Meta:
        model = Poll
        fields = ['event', 'question_text', 'poll_type', 'options']
    
    def create(self, validated_data):
        options_data = validated_data.pop('options', [])
        poll = Poll.objects.create(**validated_data)
        
        # Create options for multiple-choice polls
        if poll.poll_type == 'multiple-choice' and options_data:
            for option_text in options_data:
                PollOption.objects.create(poll=poll, text=option_text)
        
        return poll