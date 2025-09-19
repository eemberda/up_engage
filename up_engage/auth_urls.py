from django.urls import path
from django.contrib.auth import views as auth_views
from . import auth_views as custom_auth_views

urlpatterns = [
    path('register/', custom_auth_views.RegisterView.as_view(), name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='auth/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('profile/', custom_auth_views.ProfileView.as_view(), name='profile'),
]