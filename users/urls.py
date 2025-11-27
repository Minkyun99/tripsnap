from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('profile/', views.user_profile, name='user_profile'),
    path('signup/', views.signup, name='signup'),
    path('delete/', views.account_delete, name='account_delete'),
]