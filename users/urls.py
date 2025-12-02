from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # ===== 프로필 =====
    path('profile/', views.user_profile, name='user_profile'),
    path('profile/search/', views.profile_search, name='profile_search'),  # ✅ search는 <nickname>보다 위!
    path('profile/<str:nickname>/', views.user_profile, name='profile_detail'),

    # ===== 팔로우 =====
    path('follow/<str:nickname>/', views.follow_toggle, name='follow_toggle'),              # 일반용(필요시)
    path('follow/<str:nickname>/ajax/', views.follow_toggle_ajax, name='follow_toggle_ajax'),  # ✅ JS에서 쓰는 URL

    path(
        "profile/<str:nickname>/followers/ajax/",
        views.followers_list_ajax,
        name="followers_list_ajax",
    ),
    path(
        "profile/<str:nickname>/followings/ajax/",
        views.followings_list_ajax,
        name="followings_list_ajax",
    ),

    # ===== 회원가입 / 탈퇴 / 프로필 이미지 =====
    path('signup/', views.signup, name='signup'),
    path('delete/', views.account_delete, name='account_delete'),
    path('upload-profile-image/', views.upload_profile_image, name='upload_profile_image'),

    # ===== 게시글 =====
    path('post/create/', views.post_create, name='post_create'),
    path('post/<int:post_id>/delete/', views.post_delete, name='post_delete'),

    # 좋아요 
    path('post/<int:post_id>/like-toggle/', views.post_like_toggle, name='post_like_toggle'),
    # 좋아요 (AJAX 전용)
    path('post/<int:post_id>/like-toggle/ajax/', views.post_like_toggle_ajax, name='post_like_toggle_ajax'),

    # 댓글
    path('post/<int:post_id>/comment/', views.comment_create, name='comment_create'),
    # 댓글 (AJAX 전용)
    path('post/<int:post_id>/comments/ajax/', views.post_comments_ajax, name='post_comments_ajax'),

    # 댓글 삭제
    path('comment/<int:comment_id>/delete/', views.comment_delete, name='comment_delete'),
]
