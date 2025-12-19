# users/serializers.py
from __future__ import annotations

import random
import re

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from rest_framework import serializers
from dj_rest_auth.serializers import LoginSerializer
from dj_rest_auth.registration.serializers import RegisterSerializer

from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

class UserSerializer(serializers.ModelSerializer):
    """
    /api/auth/user/ 응답용 시리얼라이저
    """
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'nickname']
        read_only_fields = ['id', 'email', 'username', 'nickname']

_ADJECTIVES = [
    "따뜻한", "뜨거운", "갓구운", "신선한", "폭신한", "보송보송한", "쫄깃한", "바삭한",
    "부드러운", "촉촉한", "고소한", "달콤한", "담백한", "짭짤한", "향긋한", "노릇노릇한",
]
_NOUNS = [
    "밀가루", "효모", "버터", "우유", "설탕", "소금", "계란", "반죽", "오븐", "베이커리",
    "빵집", "제빵사", "식빵", "바게트", "크루아상", "베이글", "도넛", "케이크",
]


def _generate_unique_nickname() -> str:
    while True:
        nick = f"{random.choice(_ADJECTIVES)}{random.choice(_NOUNS)}{random.randint(100, 999)}"
        if not User.objects.filter(nickname=nick).exists():
            return nick


def _sanitize_username_base(s: str) -> str:
    # Django username에 안전하게: 영문/숫자/._ 만 남김
    s = (s or "").strip()
    s = re.sub(r"[^A-Za-z0-9._]", "", s)
    return s or "user"


def _generate_unique_username_from_email(email: str) -> str:
    base = (email or "").split("@")[0] or "user"
    base = _sanitize_username_base(base)

    candidate = base
    i = 0
    while User.objects.filter(username=candidate).exists():
        i += 1
        candidate = f"{base}{i}"
    return candidate


class CustomRegisterSerializer(RegisterSerializer):
    """
    /api/auth/registration/
    - username 입력을 받지 않아도 됨(서버 자동 생성)
    - email 중복/비밀번호 약함 메시지 커스터마이징
    - username/nickname 자동 생성
    """

    # ✅ username을 "없어도 되는 필드"로 재정의
    username = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    def validate_email(self, email: str) -> str:
        email = (email or "").strip().lower()
        if not email:
            raise serializers.ValidationError("이메일을 입력해주세요.")
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("이미 사용 중인 이메일입니다.")
        return email

    def validate_password1(self, password: str) -> str:
        try:
            validate_password(password)
        except DjangoValidationError:
            raise serializers.ValidationError(
                "비밀번호는 영문+숫자+특수문자 조합으로 8자 이상 작성해 주세요."
            )
        return password

    def get_cleaned_data(self):
        """
        dj-rest-auth RegisterSerializer.save()가 내부적으로 cleaned_data['username']을 사용합니다.
        따라서 username을 제거(None)하는 방식이 아니라, "반드시 채워서" 넘기는 방식이 안전합니다.
        """
        data = super().get_cleaned_data()

        email = (self.validated_data.get("email") or "").strip().lower()
        username = (self.validated_data.get("username") or "").strip()

        if not username:
            username = _generate_unique_username_from_email(email)

        data["username"] = username
        data["email"] = email
        return data

    @transaction.atomic
    def save(self, request):
        """
        - 이메일 중복/비번 검증에서 걸리면 여기까지 오지 않음(400)
        - 저장이 시작되면 atomic으로 묶어서 중간 실패 시 DB에 남지 않게 방어
        """
        user = super().save(request)

        # nickname 자동 생성
        if not getattr(user, "nickname", None):
            user.nickname = _generate_unique_nickname()

        # username이 비어있을 경우(이상 케이스) 한 번 더 방어
        if not getattr(user, "username", None):
            user.username = _generate_unique_username_from_email(getattr(user, "email", ""))

        user.save(update_fields=["username", "nickname"])
        return user



from django.contrib.auth import authenticate

class CustomLoginSerializer(LoginSerializer):
    """
    /api/auth/login/
    - username 대신 email+password로 로그인
    """

    username = None
    email = serializers.EmailField(required=True)

    def validate(self, attrs):
        email = (attrs.get("email") or "").strip().lower()
        password = attrs.get("password")

        if not email or not password:
            raise serializers.ValidationError("이메일과 비밀번호를 입력해주세요.")

        # ✅ User 모델의 USERNAME_FIELD가 'email'이므로 username으로 전달
        user = authenticate(
            request=self.context.get('request'),
            username=email,  # USERNAME_FIELD='email'이므로 이렇게 전달
            password=password
        )

        if not user:
            raise serializers.ValidationError("이메일 또는 비밀번호가 올바르지 않습니다.")

        if not user.is_active:
            raise serializers.ValidationError("비활성화된 계정입니다.")

        # authenticate()가 user.backend를 자동으로 설정해줌
        attrs['user'] = user
        self.user = user
        
        return attrs