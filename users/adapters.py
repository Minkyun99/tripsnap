import uuid
import random
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.account.adapter import DefaultAccountAdapter
from django.db import IntegrityError
from django.conf import settings
from django.shortcuts import resolve_url
from django.http import HttpRequest


# =========================================================
# 1. 일반 계정 (Allauth) 어댑터
# =========================================================
class CustomAccountAdapter(DefaultAccountAdapter):
    """
    일반적인 계정 등록/인증 흐름을 위한 어댑터입니다.
    """
    def get_login_redirect_url(self, request: HttpRequest):
        """
        로그인 성공 후 리디렉션될 URL을 사용자 정의합니다.
        settings.LOGIN_REDIRECT_URL을 따릅니다.
        """
        return resolve_url(settings.LOGIN_REDIRECT_URL)

    def is_open_for_signup(self, request):
        # 회원가입 기능을 제어하려면 이 메서드를 오버라이딩합니다.
        return True


# =========================================================
# 2. 소셜 계정 (Socialaccount) 어댑터
# =========================================================
class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    소셜 로그인 시 User 모델의 username과 nickname 필드에 랜덤 닉네임을 설정합니다.
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.adjectives = ['따뜻한', '뜨거운', '갓 구운', '신선한', '폭신한', '보송보송한', 
                          '쫄깃한', '바삭한', '파삭한', '부드러운', '촉촉한', '퍽퍽한', 
                          '거친', '묵직한', '고소한', '달콤한', '담백한', '짭짤한', 
                          '신맛이 나는', '시큼한', '풍부한', '향긋한', '노릇노릇한', 
                          '탐스러운', '먹음직스러운', '마른', '딱딱한', '매끈한', '겉바속촉', '눅눅한']
        self.nouns = ['밀가루', '효모', '이스트', '버터', '우유', '설탕', '소금', '계란', 
                     '반죽', '오븐', '베이커리', '빵집', '제빵사', '식빵', '바게트', 
                     '크루아상', '베이글', '모닝빵', '도넛', '케이크', '사워도우', 
                     '깜빠뉴', '크러스트', '겉껍질', '속살', '빵조각', '기포', '트레이']

    def generate_korean_nickname(self):
        """랜덤한 한국어 닉네임을 생성합니다."""
        adjective = random.choice(self.adjectives)
        noun = random.choice(self.nouns)
        return f"{adjective} {noun}"

    def populate_user(self, request, sociallogin, data):
        """
        소셜 로그인 데이터로 User 객체를 채웁니다.
        이 메서드는 save_user 전에 호출되며, User 객체의 기본 필드를 설정합니다.
        """
        user = super().populate_user(request, sociallogin, data)
        
        # username을 이메일의 @ 앞부분으로 설정
        if data.get('email'):
            email_username = data['email'].split('@')[0]
            user.username = email_username
        
        # nickname 생성 및 설정
        max_attempts = 10
        nickname_set = False

        for _ in range(max_attempts):
            generated_nickname = self.generate_korean_nickname()
            # 중복 체크
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if not User.objects.filter(nickname=generated_nickname).exists():
                user.nickname = generated_nickname
                nickname_set = True
                break

        # 모든 시도가 실패했을 경우, UUID를 추가
        if not nickname_set:
            final_nickname = f"{self.generate_korean_nickname()}_{uuid.uuid4().hex[:4]}"
            user.nickname = final_nickname

        return user