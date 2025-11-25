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

from users import views as users_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # 메인페이지
    path('', users_views.home, name='home'),
    
    # [1] dj-rest-auth 및 소셜 로그인 시작 URL
    path('api/auth/', include('dj_rest_auth.urls')),
    
    # === [수정/추가된 부분] ===
    # dj-rest-auth의 소셜 로그인 등록 (Registration) 기능을 포함합니다.
    path('api/auth/registration/', include('dj_rest_auth.registration.urls')),
    
    # dj-rest-auth가 소셜 로그인을 처리하기 위해 필요한 URL (예: /api/auth/kakao/login/)을 포함합니다.
    # dj-rest-auth 패키지의 urls.py에 정의된 소셜 로그인 관련 뷰를 사용하기 위해 필요합니다.
    path('api/auth/', include('allauth.socialaccount.urls')),
    # ==========================
    
    # [2] allauth의 핵심 URL (카카오 콜백 URI 처리를 위해 필수)
    # 카카오 개발자 콘솔에 등록된 /accounts/kakao/login/callback/ 경로를 처리합니다.
    path('accounts/', include('allauth.urls')), 
    
    # [3] users 앱 URL
    path('users/', include('users.urls')),

    # ------------------------------------------------------------------------------------------

    # [4] chatbot 앱 URL
    path('chatbot/', include('chatbot.urls')),


]
