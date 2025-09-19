from django.urls import path
from . import views

urlpatterns = [
    path('', views.HomeView.as_view(), name='home'),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard'),
    path('event/<str:event_code>/', views.EventView.as_view(), name='event'),
    path('event/<str:event_code>/host/', views.HostEventView.as_view(), name='host_event'),
]