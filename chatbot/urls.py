from django.urls import path
from . import views

urlpatterns = [
    path('', views.chatbot, name='chatbot'),  # chatbot/
    path('chat/', views.chat, name='chat'),  # chatbot/chat/
]