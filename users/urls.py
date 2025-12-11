# users/urls.py
from django.urls import path
from . import views

app_name = 'users' # 이 네임스페이스는 Django 내부에서만 사용됨. API에서는 경로가 중요함.

urlpatterns = [
    # 🚨 [1] 회원 정보/설정 API
    path('settings/', views.settings_api, name='settings_api'), # views.settings_view -> settings_api
    path('delete/', views.account_delete_api, name='account_delete_api'),
    path('upload-profile-image/', views.upload_profile_image_api, name='upload_profile_image_api'),
    
    # Note: dj_rest_auth를 사용하고 있으므로, signup/login은 api/auth/registration/에서 처리될 가능성이 높습니다.
    # 만약 커스텀 signup을 사용한다면:
    # path('signup/', views.signup_api, name='signup_api'), 

    # 🚨 [2] 프로필 API
    path('profile/search/', views.profile_search_api, name='profile_search_api'), 
    path('profile/<str:nickname>/', views.user_profile_api, name='profile_detail_api'),
    
    # 🚨 [3] 팔로우 API (기존 AJAX 전용 뷰를 API 표준 뷰로 통합)
    path('profile/<str:nickname>/followers/', views.followers_list_api, name='followers_list_api'),
    path('profile/<str:nickname>/followings/', views.followings_list_api, name='followings_list_api'),
    path('follow/<str:nickname>/', views.follow_toggle_api, name='follow_toggle_api'), # AJAX 통합

    # 🚨 [4] 게시글 및 상호작용 API (views 이름 변경 필요)
    path('post/create/', views.post_create_api, name='post_create_api'),
    path('post/<int:post_id>/delete/', views.post_delete_api, name='post_delete_api'),
    path('post/<int:post_id>/update/', views.post_update_api, name='post_update_api'), 
    
    path('post/<int:post_id>/like-toggle/', views.post_like_toggle_api, name='post_like_toggle_api'), 

    path("post/<int:post_id>/comment/", views.comment_create_api, name="comment_create_api"),
    path("post/<int:post_id>/comments/", views.post_comments_api, name="post_comments_api"),

    path("comment/<int:comment_id>/update/", views.comment_update_api, name="comment_update_api"),
    path("comment/<int:comment_id>/delete/", views.comment_delete_api, name="comment_delete_api"),
]