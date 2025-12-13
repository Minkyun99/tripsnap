"""
Django settings for tripsnap project.
"""

import os
import dotenv
dotenv.load_dotenv()
from pathlib import Path
from environ import Env

BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'

env = Env()

if env_path.is_file():
    env.read_env(env_path, overwrite=True)

SECRET_KEY = os.environ.get("django_secret_key")
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "daphne",
    'corsheaders',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'rest_framework',
    'rest_framework.authtoken',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'dj_rest_auth',
    'dj_rest_auth.registration',
    'allauth.socialaccount.providers.google', 
    'allauth.socialaccount.providers.kakao',
    'users',
    'chatbot',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',  # 개발 편의를 위해 csrf 설정 꺼둠
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
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# WSGI_APPLICATION = 'tripsnap.wsgi.application'
# Channels를 위한 ASGI 설정
ASGI_APPLICATION = 'tripsnap.asgi.application'  # WSGI를 ASGI 설정으로 변경(비동기 처리 가능)
# CHANNEL_LAYERS = {
#     "default": {
#         "BACKEND": "channels_redis.core.RedisChannelLayer",
#         "CONFIG": {
#             "hosts": [("127.0.0.1", 6379)],
#         },
#     },
# }

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "TEST": {
            "NAME": BASE_DIR / "db.sqlite3",
        },
    }
}

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

LANGUAGE_CODE = 'ko-kr' 
TIME_ZONE = 'Asia/Seoul' 
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ===============================================
# Custom User Model
# ===============================================
AUTH_USER_MODEL = 'users.User' 
SITE_ID = 1

# ===============================================
# DRF 설정
# ===============================================
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'dj_rest_auth.jwt_auth.JWTCookieAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',  # 테스트용
    ]
}

# ===============================================
# DJ-REST-AUTH 설정
# ===============================================
REST_AUTH = {
    'USE_JWT': True, 
    'JWT_AUTH_COOKIE': 'jwt-auth',
    'JWT_AUTH_REFRESH_COOKIE': 'jwt-refresh',
    'JWT_AUTH_HTTPONLY': False,  # 🔥 쿠키를 JavaScript에서 접근 가능하게 (로그아웃 시 삭제용)
    'SOCIALACCOUNT_ADAPTER': 'users.adapters.CustomSocialAccountAdapter',
}

# ===============================================
# ALLAUTH 설정
# ===============================================
ACCOUNT_LOGIN_METHODS = {"email"}  # 이메일로 로그인

ACCOUNT_SIGNUP_FIELDS = [
    "email*",
    "password1*",
    "password2*",
]    
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_EMAIL_VERIFICATION = 'none' 


LOGIN_REDIRECT_URL = '/auth/kakao/complete'
ACCOUNT_SIGNUP_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_REDIRECT_URL = '/'

# ⭐ 어댑터 설정 - 오타 수정 및 올바른 위치
ACCOUNT_ADAPTER = 'users.adapters.CustomAccountAdapter'
SOCIALACCOUNT_ADAPTER = 'users.adapters.CustomSocialAccountAdapter'  # 콜론이 아닌 등호!

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend' 

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# ===============================================
# 소셜 로그인 설정
# ===============================================
kakao_client_id = os.environ.get("kakao_client_id")
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
            'client_id': kakao_client_id, 
            'secret': kakao_secret,
            'key': ''
        },
        'SCOPE': [
            'account_email',
            'profile_nickname',  # 닉네임 정보 추가
        ],
        # 🔥 동의 항목 설정
        'AUTH_PARAMS': {
            'prompt': 'select_account',  # 계정 선택 화면 표시
        },
        'VERIFIED_EMAIL': False,
    }
}

# ===============================================
# JWT 설정
# ===============================================
from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_COOKIE': 'jwt-auth',
    'AUTH_COOKIE_REFRESH': 'jwt-refresh',
    'AUTH_COOKIE_SECURE': False,  # 개발 환경에서는 False
    'AUTH_COOKIE_HTTP_ONLY': False,  # 🔥 JavaScript에서 접근 가능하게
    'AUTH_COOKIE_SAMESITE': 'Lax',
}

# ===============================================
# OPENAI API KEY
# ===============================================
OPENAI_API_KEY = env.str("OPENAI_API_KEY", default=None)

# ===============================================
# 세션 설정 (로그아웃 시 쿠키 완전 삭제)
# ===============================================
SESSION_COOKIE_AGE = 86400  # 1일
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False


# Vue dev 서버에서 오는 요청 허용
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# 쿠키/세션을 포함한 요청 허용 (credentials: 'include' 사용 중)
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
