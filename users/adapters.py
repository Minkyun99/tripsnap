import uuid
import random
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from django.conf import settings
from django.shortcuts import resolve_url
from django.http import HttpRequest
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from django.contrib import messages


# =========================================================
# 0. 공용 랜덤 닉네임 생성 함수
# =========================================================
ADJECTIVES = [
    '따뜻한', '뜨거운', '갓 구운', '신선한', '폭신한', '보송보송한',
    '쫄깃한', '바삭한', '파삭한', '부드러운', '촉촉한', '퍽퍽한',
    '거친', '묵직한', '고소한', '달콤한', '담백한', '짭짤한',
    '신맛이 나는', '시큼한', '풍부한', '향긋한', '노릇노릇한',
    '탐스러운', '먹음직스러운', '마른', '딱딱한', '매끈한', '겉바속촉', '눅눅한'
]

NOUNS = [
    '밀가루', '효모', '이스트', '버터', '우유', '설탕', '소금', '계란',
    '반죽', '오븐', '베이커리', '빵집', '제빵사', '식빵', '바게트',
    '크루아상', '베이글', '모닝빵', '도넛', '케이크', '사워도우',
    '깜빠뉴', '크러스트', '겉껍질', '속살', '빵조각', '기포', '트레이'
]


def generate_unique_nickname():
    """
    adjectives + nouns + 조합으로 users.nickname 에 UNIQUE 값 생성
    """
    User = get_user_model()

    while True:
        nickname = f"{random.choice(ADJECTIVES)} {random.choice(NOUNS)}"
        if not User.objects.filter(nickname=nickname).exists():
            return nickname


# =========================================================
# 1. 일반 계정 (Allauth) 어댑터
# =========================================================
class CustomAccountAdapter(DefaultAccountAdapter):
    """
    일반적인 계정(홈페이지 회원가입 /accounts/signup/) 에서
    username, nickname 을 자동 세팅하기 위한 어댑터
    """

    def get_login_redirect_url(self, request: HttpRequest):
        """
        로그인 성공 후 리디렉션될 URL
        """
        # 🔹 카카오가 아닌, /accounts/login/, /accounts/signup/ 에서 온 경우에만 메시지 표시
        path = request.path or ""
        if path.startswith("/accounts/login/") or path.startswith("/accounts/signup/"):
            messages.success(request, "로그인/회원가입이 완료되었습니다! 🥐")

        # 메인으로 리다이렉트
        return resolve_url(settings.LOGIN_REDIRECT_URL)

    def is_open_for_signup(self, request):
        # 회원가입 허용 여부 (필요하면 조건 걸어서 제어 가능)
        return True

    def save_user(self, request, user, form, commit=True):
        """
        allauth SignupView 가 사용.
        기본 저장 로직 실행 후 username / nickname 을 보정.
        """
        # 1) allauth 기본 저장 로직으로 email, username 등 먼저 채우기
        user = super().save_user(request, user, form, commit=False)

        UserModel = get_user_model()

        # -------- username 처리 --------
        # 폼에서 username 을 받았으면 그 값 사용
        username = form.cleaned_data.get("username") or getattr(user, "username", "")

        # username 이 비어 있으면 이메일 앞부분으로 생성
        if not username:
            email = form.cleaned_data.get("email") or getattr(user, "email", "")
            if email:
                base_username = email.split("@")[0]
            else:
                base_username = f"user{random.randint(1000, 9999)}"

            # 영문/숫자/하이픈 정도로 정리 (혹시 한글/특수문자 섞였을 때)
            base_username = slugify(base_username) or f"user{random.randint(1000, 9999)}"

            unique_username = base_username
            idx = 1
            while UserModel.objects.filter(username=unique_username).exists():
                unique_username = f"{base_username}{idx}"
                idx += 1

            username = unique_username

        user.username = username

        # -------- nickname 처리 --------
        # User 모델에 nickname 필드가 있고 비어있으면 랜덤 닉네임 부여
        if hasattr(user, "nickname"):
            if not user.nickname:
                user.nickname = generate_unique_nickname()

        if commit:
            user.save()

        return user


# =========================================================
# 2. 소셜 계정 (Socialaccount) 어댑터
# =========================================================
class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    소셜 로그인 시 User 모델의 username과 nickname 필드에 랜덤 닉네임을 설정합니다.
    """

    def populate_user(self, request, sociallogin, data):
        """
        소셜 로그인 데이터로 User 객체를 채우는 단계.
        """
        user = super().populate_user(request, sociallogin, data)

        # 1) username: 이메일 앞부분 사용 (가능하면)
        if data.get("email"):
            email_username = data["email"].split("@")[0]
            # slugify 로 약간 정리
            email_username = slugify(email_username) or email_username
            user.username = email_username

        # 2) nickname: 공용 함수로 UNIQUE 닉네임 부여
        if hasattr(user, "nickname"):
            if not user.nickname:
                user.nickname = generate_unique_nickname()

        return user
