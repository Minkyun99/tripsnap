from django.urls import path
from . import views

urlpatterns = [
    path('profile/', views.user_profile, name='user_profile'),
    path('signup/', views.signup, name='signup'),
]