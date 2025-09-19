from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.contrib import messages
from django.db.models import Count
from .models import Event, Question, Poll


class HomeView(TemplateView):
    """Home page with event code entry form"""
    template_name = 'up_engage/home.html'
    
    def post(self, request, *args, **kwargs):
        event_code = request.POST.get('event_code', '').strip().upper()
        if event_code:
            try:
                event = Event.objects.get(event_code=event_code, is_active=True)
                return redirect('event', event_code=event_code)
            except Event.DoesNotExist:
                messages.error(request, 'Event not found or is not active.')
        else:
            messages.error(request, 'Please enter an event code.')
        
        return self.get(request, *args, **kwargs)


class DashboardView(LoginRequiredMixin, TemplateView):
    """Dashboard for event hosts to manage their events"""
    template_name = 'up_engage/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['events'] = Event.objects.filter(host=self.request.user).annotate(
            question_count=Count('questions'),
            poll_count=Count('polls')
        ).order_by('-created_at')
        return context


class EventView(TemplateView):
    """Participant view of an event"""
    template_name = 'up_engage/event.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event_code = kwargs['event_code']
        
        event = get_object_or_404(Event, event_code=event_code, is_active=True)
        context['event'] = event
        
        # Get questions ordered by upvotes
        context['questions'] = Question.objects.filter(event=event).annotate(
            upvote_count=Count('upvotes')
        ).order_by('-upvote_count', '-created_at')
        
        # Get active poll
        context['active_poll'] = Poll.objects.filter(event=event, is_active=True).first()
        
        # Get all polls for this event
        context['polls'] = Poll.objects.filter(event=event).order_by('-created_at')
        
        # Ensure session exists for participant identification
        if not self.request.session.session_key:
            self.request.session.create()
        
        return context


class HostEventView(LoginRequiredMixin, TemplateView):
    """Host view of an event for management"""
    template_name = 'up_engage/host_event.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        event_code = kwargs['event_code']
        
        event = get_object_or_404(Event, event_code=event_code, host=self.request.user)
        context['event'] = event
        
        # Get questions ordered by upvotes
        context['questions'] = Question.objects.filter(event=event).annotate(
            upvote_count=Count('upvotes')
        ).order_by('-upvote_count', '-created_at')
        
        # Get all polls for this event
        context['polls'] = Poll.objects.filter(event=event).order_by('-created_at')
        
        # Get active poll
        context['active_poll'] = Poll.objects.filter(event=event, is_active=True).first()
        
        return context
