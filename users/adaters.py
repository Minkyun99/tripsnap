from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.db import IntegrityError
import uuid

class CustomSocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    소셜 로그인 시 User 모델의 username 필드를 소셜 계정의 email로 설정합니다.

    요구사항: User.username 필드와 SocialAccount의 이메일 필드를 일치시켜
             다른 앱/모델(예: Profile)에서 User를 이메일 기반으로 쉽게 참조할 수 있게 합니다.
    """
    
    def save_user(self, request, sociallogin, form=None):
        # 1. 부모 클래스의 save_user를 호출하여 User 객체를 생성하거나 가져옵니다.
        user = super().save_user(request, sociallogin, form)
        
        # 2. 소셜 계정에서 추출한 이메일 주소 (allauth는 이메일을 반드시 가져오도록 설정되어 있음)
        email = sociallogin.user.email
        
        # 3. username이 비어있는 경우에만 이메일로 설정합니다.
        #    (allauth는 기본적으로 username을 공백으로 두거나 임시로 설정할 수 있음)
        if not user.username or user.username == '':
            try:
                # User.username 필드에 이메일을 할당 (핵심 로직)
                user.username = email
                user.save()
            except IntegrityError:
                # IntegrityError 발생 시 (이메일이 이미 다른 사용자의 username으로 사용 중일 경우)
                # 충돌을 피하기 위해 이메일과 UUID를 조합한 고유한 임시 username을 설정합니다.
                # (이 경우는 매우 드물지만, 안정성을 위해 추가합니다.)
                temp_username = f"{email[:30]}_{uuid.uuid4().hex[:8]}"
                user.username = temp_username
                user.save()

        # 수정된 User 객체를 반환
        return user