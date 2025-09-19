from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import api_views

router = DefaultRouter()
router.register(r'events', api_views.EventViewSet)
router.register(r'questions', api_views.QuestionViewSet)
router.register(r'polls', api_views.PollViewSet)
router.register(r'poll-options', api_views.PollOptionViewSet)
router.register(r'votes', api_views.VoteViewSet)
router.register(r'word-responses', api_views.WordCloudResponseViewSet)
router.register(r'rating-responses', api_views.RatingResponseViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('events/<str:event_code>/questions/', api_views.EventQuestionsView.as_view(), name='event-questions'),
    path('events/<str:event_code>/polls/', api_views.EventPollsView.as_view(), name='event-polls'),
    path('questions/<int:question_id>/upvote/', api_views.QuestionUpvoteView.as_view(), name='question-upvote'),
]