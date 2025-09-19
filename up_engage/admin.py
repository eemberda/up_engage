from django.contrib import admin
from .models import Event, Question, QuestionUpvote, Poll, PollOption, Vote, WordCloudResponse, RatingResponse


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ('title', 'event_code', 'host', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at', 'host')
    search_fields = ('title', 'event_code', 'description')
    readonly_fields = ('event_code', 'created_at', 'updated_at')


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text_preview', 'event', 'author_session_id', 'upvote_count_display', 'is_answered', 'created_at')
    list_filter = ('is_answered', 'created_at', 'event')
    search_fields = ('text', 'author_session_id')
    readonly_fields = ('created_at', 'updated_at')
    
    def text_preview(self, obj):
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text
    text_preview.short_description = "Question Text"
    
    def upvote_count_display(self, obj):
        return obj.get_upvote_count()
    upvote_count_display.short_description = "Upvotes"


@admin.register(QuestionUpvote)
class QuestionUpvoteAdmin(admin.ModelAdmin):
    list_display = ('question', 'session_id', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('session_id', 'question__text')


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ('question_text_preview', 'event', 'poll_type', 'is_active', 'created_at')
    list_filter = ('poll_type', 'is_active', 'created_at', 'event')
    search_fields = ('question_text',)
    readonly_fields = ('created_at', 'updated_at')
    
    def question_text_preview(self, obj):
        return obj.question_text[:50] + "..." if len(obj.question_text) > 50 else obj.question_text
    question_text_preview.short_description = "Poll Question"


@admin.register(PollOption)
class PollOptionAdmin(admin.ModelAdmin):
    list_display = ('text', 'poll', 'vote_count', 'created_at')
    list_filter = ('created_at', 'poll__poll_type')
    search_fields = ('text', 'poll__question_text')


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('poll_option', 'author_session_id', 'created_at')
    list_filter = ('created_at', 'poll_option__poll__poll_type')
    search_fields = ('author_session_id', 'poll_option__text')


@admin.register(WordCloudResponse)
class WordCloudResponseAdmin(admin.ModelAdmin):
    list_display = ('text', 'poll', 'author_session_id', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('text', 'author_session_id')


@admin.register(RatingResponse)
class RatingResponseAdmin(admin.ModelAdmin):
    list_display = ('poll', 'rating', 'author_session_id', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('author_session_id',)
