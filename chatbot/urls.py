from django.urls import path
from . import views

urlpatterns = [
    # ===== Chatbot URLs =====
    path('', views.chatbot, name='chatbot'),  # chatbot/
    path('chat/', views.chat, name='chat'),  # chatbot/chat/
    path('init/', views.chat_init, name="chat_init"),  # vue에서 keywordSelection 이후 서버로 데이터 전송

    # ===== Bakery URLs =====
    # 빵집 목록
    path('bakery/', views.bakery_list, name='bakery_list'),
    
    # 빵집 상세
    path('bakery/<int:bakery_id>/', views.bakery_detail, name='bakery_detail'),
    
    # 빵집 좋아요 토글
    path('bakery/<int:bakery_id>/like/', views.bakery_like_toggle, name='bakery_like_toggle'),
    
    # 빵집 댓글 목록
    path('bakery/<int:bakery_id>/comments/', views.bakery_comments_list, name='bakery_comments_list'),
    
    # 빵집 댓글 작성
    path('bakery/<int:bakery_id>/comments/create/', views.bakery_comment_create, name='bakery_comment_create'),
    
    # 빵집 댓글 삭제
    path('bakery/<int:bakery_id>/comments/<int:comment_id>/', views.bakery_comment_delete, name='bakery_comment_delete'),
]