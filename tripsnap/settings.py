"""
Django settings for tripsnap project.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/topics/settings/
"""

import os
import dotenv
dotenv.load_dotenv()
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get("django_secret_key")

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []


# Application definition

INSTALLED_APPS = [
    # 0. Django 기본 내장 앱들 (필수)
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # 1. Allauth 필수 의존성 앱
    'django.contrib.sites',

    # 2. Third-party Apps (서드파티 앱)
    'rest_framework',
    'rest_framework.authtoken',
    
    # Django Allauth 및 관련 앱
    'allauth',
    'allauth.account',
    'allauth.socialaccount',

    # DRF + Allauth 연결 앱
    'dj_rest_auth',
    'dj_rest_auth.registration', # 회원가입 기능을 사용하려면 필요

    # 3. Social Providers (소셜 제공자별 앱)
    'allauth.socialaccount.providers.google', 
    'allauth.socialaccount.providers.kakao',
    
    # 4. Local Apps (사용자 정의 앱)
    'users',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    'allauth.account.middleware.AccountMiddleware',
]

ROOT_URLCONF = 'tripsnap.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request', # allauth에 필수
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'tripsnap.wsgi.application'


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
LANGUAGE_CODE = 'ko-kr' 

TIME_ZONE = 'Asia/Seoul' 

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
# 개발 환경에서 정적 파일과 미디어 파일을 제공하기 위한 설정
STATIC_ROOT = BASE_DIR / 'staticfiles'


# Media files (사용자 업로드 파일 - Profile 모델의 ImageField 관련)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ===============================================
# Custom & Third-party App Settings
# ===============================================

# 1. Custom User Model 등록 (필수)
# users 앱의 User 모델을 기본 인증 모델로 사용하도록 설정
AUTH_USER_MODEL = 'users.User' 

# 2. Allauth 필수 의존성: SITE_ID 설정
SITE_ID = 1

# 3. DRF/AUTH 설정
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        # JWT를 사용하려면 아래 설정을 추가합니다.
        'dj_rest_auth.jwt_auth.JWTCookieAuthentication',
    )
}

# 4. DJ-REST-AUTH 설정
REST_AUTH = {
    'USE_JWT': True, 
    'JWT_AUTH_COOKIE': 'jwt-auth', # JWT 쿠키 이름 설정
    'JWT_AUTH_REFRESH_COOKIE': 'jwt-refresh', # JWT 리프레시 쿠키 이름 설정
    # 소셜 로그인 시 필요한 어댑터 지정 (user 앱에 adapters.py가 있다고 가정)
    'SOCIALACCOUNT_ADAPTER': 'users.adapters.CustomSocialAccountAdapter', 
    # 사용자 정의 Serializer를 사용하여 User 모델 필드 커스터마이징 가능
    # 'USER_DETAILS_SERIALIZER': 'user.serializers.CustomUserDetailsSerializer', 
}

# 5. ALLAUTH 기본 설정
ACCOUNT_AUTHENTICATION_METHOD = 'email' 
ACCOUNT_EMAIL_REQUIRED = True         
ACCOUNT_UNIQUE_EMAIL = True           
ACCOUNT_USERNAME_REQUIRED = False     
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_EMAIL_VERIFICATION = 'none' 
ACCOUNT_LOGOUT_ON_GET = True

# 리디렉션 URL 설정
LOGIN_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'

# 6. Email 설정 (개발 환경: 콘솔 출력)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' 

# 7. 소셜 로그인 설정
kakao_clinet_id = os.environ.get("kakao_clinet_id")
kakao_secret = os.environ.get("kakao_secret")

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': 'YOUR_GOOGLE_CLIENT_ID',       
            'secret': 'YOUR_GOOGLE_SECRET_KEY',         
            'key': ''
        },
        'SCOPE': [
            'email',
        ],
    },
    'kakao': {
        'APP': {
            'client_id': kakao_clinet_id, 
            'secret': kakao_secret,
            'key': ''
        },
        'SCOPE': [
            'account_email',
        ]
    }
}

# 8. JWT 설정 (dj-rest-auth에서 USE_JWT=True일 때 필수)
# pip install djangorestframework-simplejwt 필요
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=5), # 액세스 토큰 만료 시간
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),  # 리프레시 토큰 만료 시간
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

ACCOUNT_ADAPTER = 'users.adapter.CustomAccountAdapter'