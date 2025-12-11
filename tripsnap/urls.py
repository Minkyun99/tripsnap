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
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from users import views as users_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # [1] dj-rest-auth 및 소셜 로그인 핵심 API 경로 유지
    path('api/auth/', include('dj_rest_auth.urls')),
    path('api/auth/registration/', include('dj_rest_auth.registration.urls')),
    path('api/auth/', include('allauth.socialaccount.urls')),
    
    # [2] users 앱 URL을 API 경로로 변경
    # 모든 사용자, 게시글, 팔로우 관련 기능을 /api/v1/users/ 아래로 통합합니다.
    path('api/v1/users/', include('users.urls')), 

    # [3] chatbot 앱 URL도 API 경로로 변경 (챗봇 기능이 API라면)
    path('api/v1/chatbot/', include('chatbot.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
