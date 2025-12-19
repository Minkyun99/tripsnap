from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _


# ---------------------------------------------------
# 1. User Model (users 테이블 + AbstractUser)
# ---------------------------------------------------
class User(AbstractUser):
    """
    Django의 기본 AbstractUser를 상속받아 사용합니다.
    - id (PK), password, date_joined (created_at) 필드가 기본 포함됩니다.
    - email 필드는 unique=True로 설정하여 소셜 로그인에서 핵심 식별자로 사용합니다.
    """
    

    # 소셜 로그인의 경우 username이 없을 수 있으므로 null=True, blank=True 허용
    username = models.CharField(
        _("사용자명"),
        max_length=150,
        unique=True,
        blank=True,
        null=True,
    )

    # 이메일을 고유 값으로 사용
    email = models.EmailField(
        _("이메일 주소"),
        unique=True,
        null=False,
        blank=False,
    )

    # 회원가입 시 랜덤으로 자동 생성되는 닉네임
    nickname = models.CharField(
        _("닉네임"),
        max_length=30,
        unique=True,
        null=True,
        blank=True,
    )

    USERNAME_FIELD = 'email'  # ✅ 이메일로 로그인
    REQUIRED_FIELDS = []  # ✅ email이 USERNAME_FIELD이므로 비워둠

    class Meta:
        verbose_name = _("사용자")
        verbose_name_plural = _("사용자 목록")

    def __str__(self):
        # 기존 코드에 set 을 반환하는 버그가 있어서 문자열 하나만 반환하도록 수정
        return self.nickname or self.username or self.email or "Unknown User"


# ---------------------------------------------------
# 2. Profile Model (profile 테이블)
#    - 이제는 username 을 FK 로 쓰지 않고, User 의 PK(id)를 1:1 로 참조
# ---------------------------------------------------
class Profile(models.Model):
    """
    사용자의 프로필 이미지를 저장하는 모델입니다.
    닉네임은 User.nickname 을 그대로 사용하고, 여기서는 이미지 등 부가 정보만 관리합니다.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        verbose_name=_("사용자"),
    )

    profile_img = models.ImageField(
        _("프로필 이미지"),
        upload_to="profile_images/",
        blank=True,
        null=True,
    )

    class Meta:
        verbose_name = _("프로필")
        verbose_name_plural = _("프로필")

    def __str__(self):
        return f"{self.user.nickname or self.user.username}의 프로필"


# ---------------------------------------------------
# 3. Social (팔로우 관계) – ERD 의 social 테이블
# ---------------------------------------------------
class Social(models.Model):
    """
    인스타그램 스타일 팔로우 관계.
    follow_id / following_id 를 boolean 으로 두지 않고,
    실제로 '누가(follower) 누구를(following) 팔로우하는지' 를 FK 로 표현합니다.
    """

    follower = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="following_set",  # 내가 팔로우하는 사람들
        verbose_name=_("팔로우 하는 사용자"),
    )
    following = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="follower_set",   # 나를 팔로우하는 사람들
        verbose_name=_("팔로우 당하는 사용자"),
    )

    created_at = models.DateTimeField(_("생성일"), auto_now_add=True)

    class Meta:
        db_table = "social"  # ERD 테이블명 맞추고 싶으면 지정
        verbose_name = _("팔로우")
        verbose_name_plural = _("팔로우")
        unique_together = ("follower", "following")  # 같은 쌍은 한 번만

    def __str__(self):
        return f"{self.follower.nickname} -> {self.following.nickname}"


# ---------------------------------------------------
# 4. Post (게시글) – ERD 의 post 테이블
# ---------------------------------------------------
class Post(models.Model):
    """
    인스타그램 스타일의 게시글.
    writer 는 User FK 이고, 닉네임은 writer.nickname 으로 참조합니다.
    """

    writer = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="posts",
        verbose_name=_("작성자"),
    )

    title = models.CharField(_("제목"), max_length=200)
    content = models.TextField(_("내용"))

    share_trip = models.ImageField(
        _("여행 사진"),
        upload_to="posts/",
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(_("작성일"), auto_now_add=True)
    updated_at = models.DateTimeField(_("수정일"), auto_now=True)

    class Meta:
        verbose_name = _("게시글")
        verbose_name_plural = _("게시글")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.writer.nickname})"


# ---------------------------------------------------
# 5. Like (좋아요) – ERD 의 like 테이블
# ---------------------------------------------------
class Like(models.Model):
    """
    게시글 좋아요.
    한 유저는 한 게시글에 한 번만 좋아요를 누를 수 있습니다.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="likes",
        verbose_name=_("사용자"),
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="likes",
        verbose_name=_("게시글"),
    )
    created_at = models.DateTimeField(_("생성일"), auto_now_add=True)

    class Meta:
        verbose_name = _("좋아요")
        verbose_name_plural = _("좋아요")
        unique_together = ("user", "post")

    def __str__(self):
        return f"{self.user.nickname} ♥ {self.post_id}"


# ---------------------------------------------------
# 6. Comment (댓글) – ERD 의 comment 테이블
# ---------------------------------------------------
class Comment(models.Model):
    """
    게시글 댓글.
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name=_("작성자"),
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name=_("게시글"),
    )
    content = models.TextField(_("내용"))

    created_at = models.DateTimeField(_("작성일"), auto_now_add=True)
    updated_at = models.DateTimeField(_("수정일"), auto_now=True)

    class Meta:
        verbose_name = _("댓글")
        verbose_name_plural = _("댓글")

    def __str__(self):
        return f"{self.user.nickname}: {self.content[:20]}"


