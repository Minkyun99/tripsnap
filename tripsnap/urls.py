"""
URL configuration for tripsnap project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView
from django.shortcuts import redirect
import os

from users import views as users_views

FRONT_URL = os.getenv('FRONT_URL', 'http://localhost:5173')

urlpatterns = [
    path('admin/', admin.site.urls),

    # === [1] dj-rest-auth 및 소셜 로그인 시작 URL ===
    path('api/auth/', include('dj_rest_auth.urls')),
    
    # dj-rest-auth의 소셜 로그인 등록 (Registration) 기능을 포함합니다.
    path('api/auth/registration/', include('dj_rest_auth.registration.urls')),
    
    # dj-rest-auth가 소셜 로그인을 처리하기 위해 필요한 URL (예: /api/auth/kakao/login/)을 포함합니다.
    path('api/auth/', include('allauth.socialaccount.urls')),
    
    # === [2] allauth의 핵심 URL (카카오 콜백 URI 처리를 위해 필수) ===
    # ✅ 중요: 이 경로가 SPA Catch-all이나 메인페이지 설정보다 명확히 위에 있어야 합니다.
    path('accounts/', include('allauth.urls')), 
    
    # [3] users 앱 URL
    path('users/', include('users.urls', namespace='users')),

    # [4] chatbot 앱 URL
    path('chatbot/', include('chatbot.urls')),

    # ✅ 2) 카카오 로그인 완료 착지 URL (settings.LOGIN_REDIRECT_URL과 일치)
    path('auth/kakao/complete', lambda request: redirect(f"{FRONT_URL}/"), name='kakao_complete'),

    # --- 여기서부터 프론트엔드(Vue) 관련 경로입니다 ---

    # # 메인페이지 (빈 문자열 매칭)
    # ✅ path('', ...)은 정확히 도메인 뒤에 아무것도 없을 때만 index.html을 부릅니다.
    path('', TemplateView.as_view(template_name='index.html'), name='home'),

    # ✨ [SPA Catch-all] Vue Router를 위한 패턴
    # API 경로가 아닌 모든 경로를 Vue의 index.html로 리다이렉트
    # 주의: 이 패턴은 반드시 urlpatterns의 가장 마지막에 위치해야 함
    # ✅ 정규식 보정: 제외할 단어들 뒤에 /를 선택사항으로 넣어 매칭을 더 정확하게 합니다.
    # urls.py 의 re_path 부분 수정
    re_path(r'^(?!(api|admin|accounts|media|static|auth|chatbot|users)).*$', 
            TemplateView.as_view(template_name='index.html'), 
            name='spa_catchall'),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)