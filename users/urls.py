from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [

    # CSRF 쿠키 세팅 (Vue SPA에서 최초 1회 호출)
    path('api/csrf/', views.csrf_cookie, name='csrf_cookie'),

    # ✅ 설정 페이지
    path('settings/', views.settings_view, name='settings'),
    
    # ===== 프로필 =====
    path('profile/', views.user_profile, name='user_profile'),
    path("api/profile/search/", views.profile_search, name="profile-search"),  # ✅ search는 <nickname>보다 위!
    path('profile/<str:nickname>/', views.user_profile, name='profile_detail'),

    # ===== 팔로우 =====
    path('follow/<str:nickname>/', views.follow_toggle, name='follow_toggle'),              # 일반용(필요시)
    path('follow/<str:nickname>/ajax/', views.follow_toggle_ajax, name='follow_toggle_ajax'),  # ✅ JS에서 쓰는 URL
    # 설정
    path("api/settings/follow-visibility/", views.follow_visibility_setting_api, name="follow-visibility-setting"),

    # 팔로우 리스트(모달)
    path("profile/<str:nickname>/followers/ajax/", views.followers_list_ajax, name="followers-list-ajax"),
    path("profile/<str:nickname>/followings/ajax/", views.followings_list_ajax, name="followings-list-ajax"),


    # Vue용 프로필 데이터 API (추가)
    path('api/profile/me/', views.profile_me_api, name='profile_me_api'),
    path('api/profile/<str:nickname>/', views.profile_detail_api, name='profile_detail_api'),

    # ===== 회원가입 / 탈퇴 / 프로필 이미지 =====
    path('signup/', views.signup, name='signup'),
    path('delete/', views.account_delete, name='account_delete'),
    path('upload-profile-image/', views.upload_profile_image, name='upload_profile_image'),

    # ===== 게시글 =====
    path('post/create/', views.post_create, name='post_create'),
    path('post/<int:post_id>/delete/', views.post_delete, name='post_delete'),

    # 🔹 게시글 수정 (AJAX)
    path('post/<int:post_id>/update/ajax/', views.post_update_ajax, name='post_update_ajax'),

    # 좋아요 
    path('post/<int:post_id>/like-toggle/', views.post_like_toggle, name='post_like_toggle'),
    # 좋아요 (AJAX 전용)
    path('post/<int:post_id>/like-toggle/ajax/', views.post_like_toggle_ajax, name='post_like_toggle_ajax'),

    # 댓글
    path("post/<int:post_id>/comment/", views.comment_create, name="comment_create"),
    path("post/<int:post_id>/comments/ajax/", views.post_comments_ajax, name="post_comments_ajax"),

    # 🔹 댓글 수정/삭제 (AJAX)
    path("comment/<int:comment_id>/edit/ajax/", views.comment_update_ajax, name="comment_update_ajax"),
    path("comment/<int:comment_id>/delete/ajax/", views.comment_delete_ajax, name="comment_delete_ajax"),

    # Vue에서 쓰는 회원탈퇴 API (JSON)
    path('api/account/delete/', views.account_delete_api, name='account_delete_api'),
    
    # 기존 템플릿/폼 기반 탈퇴 (유지)
    path('delete/', views.account_delete, name='account_delete'),

    
   # ✅ 추천 빵집 API (HomeView.vue에서 사용)
    path('api/recommended-bakeries/', views.recommended_bakeries_api, name='recommended_bakeries_api'),


]
