"""
Django settings for tripsnap project.
"""

import os
from pathlib import Path

import dotenv
from environ import Env

dotenv.load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / ".env"

env = Env()
if env_path.is_file():
    env.read_env(env_path, overwrite=True)

SECRET_KEY = os.environ.get("django_secret_key")
DEBUG = False  # 에러 발생 시 노란색 에러 화면(코드 유출 위험)이 나오지 않도록 반드시 False로 바꿔야 합니다.
ALLOWED_HOSTS = [
    "tripsnap.shop", 
    "www.tripsnap.shop", 
    "43.201.75.252", 
    "localhost", 
    "127.0.0.1",
    # "marvelous-faun-4b98d8.netlify.app" # 단일 도메인 사용 시 제외 가능
]

# ===============================================
# Applications
# ===============================================
INSTALLED_APPS = [
    "daphne",
    "corsheaders",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "rest_framework",
    "rest_framework.authtoken",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "dj_rest_auth",
    "dj_rest_auth.registration",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.kakao",
    "users",
    "chatbot",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "tripsnap.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Channels / ASGI
ASGI_APPLICATION = "tripsnap.asgi.application"

# ===============================================
# Database
# ===============================================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
        "TEST": {"NAME": BASE_DIR / "db.sqlite3"},
    }
}

# ===============================================
# Password validation
# ===============================================
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ===============================================
# I18N / TZ
# ===============================================
LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

# ===============================================
# Static / Media
# ===============================================
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ===============================================
# Custom User Model
# ===============================================
AUTH_USER_MODEL = "users.User"
SITE_ID = 1

# ===============================================
# DRF
# ===============================================
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
        "dj_rest_auth.jwt_auth.JWTCookieAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}

# ===============================================
# DJ-REST-AUTH
# ===============================================
REST_AUTH = {
    "USE_JWT": True,
    "JWT_AUTH_COOKIE": "jwt-auth",
    "JWT_AUTH_REFRESH_COOKIE": "jwt-refresh",
    "JWT_AUTH_HTTPONLY": False,  # 프론트엔드 JS 접근 허용
    "JWT_AUTH_SECURE": True,    # HTTPS 환경 필수
    "JWT_AUTH_SAMESITE": "Lax",  # 동일 도메인이므로 Lax로 간소화
    "USER_DETAILS_SERIALIZER": "users.serializers.UserSerializer",
    "REGISTER_SERIALIZER": "users.serializers.CustomRegisterSerializer",
    "LOGIN_SERIALIZER": "users.serializers.CustomLoginSerializer",
}

# ===============================================
# ALLAUTH
# ===============================================

ACCOUNT_AUTHENTICATION_METHOD = 'email'  # ✅ 문자열로 변경
ACCOUNT_USERNAME_REQUIRED = False  # ✅ 추가
ACCOUNT_EMAIL_REQUIRED = True  # ✅ 추가
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGOUT_ON_GET = True

LOGIN_REDIRECT_URL = "/auth/kakao/complete"
ACCOUNT_SIGNUP_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/"

ACCOUNT_ADAPTER = "users.adapters.CustomAccountAdapter"
SOCIALACCOUNT_ADAPTER = "users.adapters.CustomSocialAccountAdapter"

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]



# ===============================================
# Social Login
# ===============================================
kakao_client_id = os.environ.get("kakao_client_id")
kakao_secret = os.environ.get("kakao_secret")

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": "YOUR_GOOGLE_CLIENT_ID",
            "secret": "YOUR_GOOGLE_SECRET_KEY",
            "key": "",
        },
        "SCOPE": ["email"],
    },
    "kakao": {
        "APP": {
            "client_id": kakao_client_id,
            "secret": kakao_secret,
            "key": "",
        },
        "SCOPE": [
            "account_email",

        ],
        "AUTH_PARAMS": {"prompt": "select_account"},
        "VERIFIED_EMAIL": False,
    },
}

# ===============================================
# JWT (SimpleJWT)
# ===============================================
from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_COOKIE": "jwt-auth",
    "AUTH_COOKIE_REFRESH": "jwt-refresh",
    "AUTH_COOKIE_SECURE": True,
    "AUTH_COOKIE_SAMESITE": "Lax", # 동일 도메인이므로 Lax
    "AUTH_COOKIE_HTTP_ONLY": True,
}

# ===============================================
# OPENAI API KEY
# ===============================================
OPENAI_API_KEY = env.str("OPENAI_API_KEY", default=None)

# ===============================================
# Session / Cookie 통합 설정 (간소화 버전)
# ===============================================
SESSION_COOKIE_AGE = 86400
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

# 동일 도메인(tripsnap.shop) 통합 배포 환경 설정
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False 
SESSION_COOKIE_HTTPONLY = True

# ===============================================
# CORS / CSRF (Vue dev server & Production)
# ===============================================
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://tripsnap.shop",
    "https://www.tripsnap.shop"
]
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://tripsnap.shop",
    "https://www.tripsnap.shop"
]

# 카카오 로그인 리다이렉트 주소
SOCIAL_AUTH_KAKAO_REDIRECT_URI = 'https://tripsnap.shop/accounts/kakao/login/callback/'

# 보안 설정: 프록시(Nginx)를 통해 들어오는 HTTPS 요청을 인식하도록 함
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
# SECURE_SSL_REDIRECT = True  # Nginx에서 리다이렉트를 처리하므로 필요한 경우에만 켜기