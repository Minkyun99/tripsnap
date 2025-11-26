from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

# --- 1. User Model (users 테이블 + AbstractUser의 기본 기능) ---
class User(AbstractUser):
    """
    Django의 기본 AbstractUser를 상속받아 사용합니다.
    - id (PK), password, date_joined (created_at) 필드가 기본 포함됩니다.
    - email 필드는 unique=True로 설정하여 소셜 로그인에서 핵심 식별자로 사용합니다.
    """
    
    # [users] username (varchar, null)
    # 소셜 로그인의 경우 username이 없을 수 있으므로 null=True, blank=True 허용
    # Profile 테이블의 외래 키(FK) 참조를 위해 unique=True를 유지합니다.
    username = models.CharField(
        _("사용자명"), 
        max_length=150, 
        unique=True, 
        blank=True, 
        null=True
    )

    # [social] email (varchar, PK)
    # AbstractUser에 있는 email 필드를 오버라이드하여 unique=True로 설정
    email = models.EmailField(_("이메일 주소"), unique=True, null=False, blank=False)

    # nickname은 임의로 자동 할당되도록 페이지 구현 예정
    # 모델에서는 null = True로 주고, 사용자가 가입할 당시에는 nickanme 란이 생길 수 있도록 함
    nickname = models.CharField(max_length=30, unique=True, null=True, blank=True)
    REQUIRED_FIELDS = ['email']

    class Meta:
        verbose_name = _("사용자")
        verbose_name_plural = _("사용자 목록")

    def __str__(self):
        return {self.username or self.email or "Unknown User", self.username}


# --- 2. Profile Model (profile 테이블) ---
class Profile(models.Model):
    """
    사용자의 프로필 이미지 등을 저장하는 모델입니다.
    요청에 따라 User 모델의 'username' 필드를 외래 키로 참조합니다.
    """
    
    # [profile] username (FK) -> users.username
    # to_field='username' 옵션을 사용하여 FK가 User의 PK(id) 대신 username을 참조하도록 설정
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        to_field='username',  # User 모델의 username 필드를 FK로 사용
        primary_key=True,     # 이 필드를 Profile 테이블의 PK로도 사용 (1:1 관계)
        verbose_name=_("사용자명")
    )

    # [profile] profile_img
    profile_img = models.ImageField(
        _("프로필 이미지"),
        upload_to='profile_images/',
        blank=True, 
        null=True
    )
    
    class Meta:
        verbose_name = _("프로필")
        verbose_name_plural = _("프로필")

    def __str__(self):
        return f"{self.user.username}의 프로필"