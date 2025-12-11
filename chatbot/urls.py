from django.urls import path
from . import views

urlpatterns = [
    path('', views.chatbot, name='chatbot'),  # chatbot/
    path('chat/', views.chat, name='chat'),  # chatbot/chat/
    path('init/', views.chat_init, name="chat_init") # vue에서 keywordSelection 이후 서버로 데이터 전송
]