from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinLengthValidator, MaxLengthValidator
import string
import random


def generate_event_code():
    """Generate a random 4-character event code"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))


class Event(models.Model):
    """Model representing an event with Q&A and polling capabilities"""
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    event_code = models.CharField(
        max_length=10, 
        unique=True, 
        default=generate_event_code,
        validators=[MinLengthValidator(2), MaxLengthValidator(10)]
    )
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_events')
    is_active = models.BooleanField(default=True)
    qa_enabled = models.BooleanField(default=True, help_text="Whether Q&A is enabled for this event")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} ({self.event_code})"


class Question(models.Model):
    """Model representing questions submitted to an event"""
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    author_session_id = models.CharField(max_length=100)
    is_answered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Q: {self.text[:50]}..."
    
    def get_upvote_count(self):
        """Return the number of upvotes for this question"""
        return self.upvotes.count()


class QuestionUpvote(models.Model):
    """Model to track upvotes on questions by session"""
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='upvotes')
    session_id = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('question', 'session_id')
    
    def __str__(self):
        return f"Upvote for {self.question.id} by {self.session_id}"


class Poll(models.Model):
    """Model representing polls within an event"""
    POLL_TYPES = [
        ('multiple-choice', 'Multiple Choice'),
        ('rating', 'Rating'),
        ('word-cloud', 'Word Cloud'),
    ]
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name='polls')
    question_text = models.TextField()
    poll_type = models.CharField(max_length=20, choices=POLL_TYPES)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Poll: {self.question_text[:50]}..."


class PollOption(models.Model):
    """Model representing options for multiple-choice polls"""
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='options')
    text = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Option: {self.text}"
    
    @property
    def vote_count(self):
        """Return the number of votes for this option"""
        return self.votes.count()


class Vote(models.Model):
    """Model representing votes on poll options"""
    poll_option = models.ForeignKey(PollOption, on_delete=models.CASCADE, related_name='votes')
    author_session_id = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('poll_option', 'author_session_id')
    
    def __str__(self):
        return f"Vote for {self.poll_option.text} by {self.author_session_id}"


class WordCloudResponse(models.Model):
    """Model for word cloud responses (free text responses)"""
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='word_responses')
    text = models.CharField(max_length=100)
    author_session_id = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Word: {self.text}"


class RatingResponse(models.Model):
    """Model for rating poll responses"""
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='rating_responses')
    rating = models.IntegerField()  # e.g., 1-5 or 1-10
    author_session_id = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('poll', 'author_session_id')
    
    def __str__(self):
        return f"Rating: {self.rating} for poll {self.poll.id}"
