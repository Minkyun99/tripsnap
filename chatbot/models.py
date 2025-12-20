from django.db import models
from django.conf import settings


class Conversation(models.Model):
    """대화(Conversation) 모델 - 최소 정보만 보관합니다.

    필드:
    - user: 대화 주인 (ForeignKey)
    - created_at: 생성 시각
    """

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'

    def __str__(self):
        return f"Conversation({self.id}) - {self.user}"


class Message(models.Model):
    """대화 메시지 모델

    필드:
    - conversation: 연결된 Conversation
    - sender: 'user', 'bot', 또는 'system' 등 발신자
    - content: 메시지 내용(텍스트)
    - created_at: 생성 시각
    """

    SENDER_USER = 'user'
    SENDER_BOT = 'bot'
    SENDER_SYSTEM = 'system'
    SENDER_CHOICES = [
        (SENDER_USER, '사용자'),
        (SENDER_BOT, '봇'),
        (SENDER_SYSTEM, '시스템'),
    ]

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='messages')
    sender = models.CharField(max_length=20, choices=SENDER_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'

    def __str__(self):
        preview = (self.content[:47] + '...') if len(self.content) > 50 else self.content
        return f"{self.get_sender_display()}: {preview}"


class Bakery(models.Model):
    """빵집 정보 저장 모델 (확장)

    dessert.json의 모든 필드를 포함합니다.
    """

    # 기본 정보
    name = models.CharField(max_length=255, verbose_name="빵집 이름")
    category = models.CharField(max_length=100, blank=True, verbose_name="카테고리")
    district = models.CharField(max_length=50, blank=True, verbose_name="구")
    
    # 주소 정보
    road_address = models.CharField(max_length=255, blank=True, verbose_name="도로명 주소")
    jibun_address = models.CharField(max_length=255, blank=True, verbose_name="지번 주소")
    
    # 연락처
    phone = models.CharField(max_length=50, blank=True, verbose_name="전화번호")
    
    # 영업시간
    business_hours_raw = models.TextField(blank=True, verbose_name="영업시간 원본")
    monday = models.CharField(max_length=100, blank=True, verbose_name="월요일")
    tuesday = models.CharField(max_length=100, blank=True, verbose_name="화요일")
    wednesday = models.CharField(max_length=100, blank=True, verbose_name="수요일")
    thursday = models.CharField(max_length=100, blank=True, verbose_name="목요일")
    friday = models.CharField(max_length=100, blank=True, verbose_name="금요일")
    saturday = models.CharField(max_length=100, blank=True, verbose_name="토요일")
    sunday = models.CharField(max_length=100, blank=True, verbose_name="일요일")
    
    # 기타 정보
    slug_en = models.CharField(max_length=255, blank=True, verbose_name="영문 슬러그")
    url = models.URLField(blank=True, verbose_name="지도 URL")
    
    # 좌표
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name="위도")
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True, verbose_name="경도")
    
    # 평점 (JSON 필드 대신 개별 필드로 저장)
    kakao_rate = models.CharField(max_length=10, blank=True, default='', verbose_name="카카오 평점")
    naver_rate = models.CharField(max_length=10, blank=True, default='', verbose_name="네이버 평점")
    
    # 키워드 (쉼표로 구분된 문자열)
    keywords = models.TextField(blank=True, verbose_name="키워드")
    
    # 통계 (비정규화 - 성능 향상용)
    like_count = models.PositiveIntegerField(default=0, verbose_name="좋아요 수")
    comment_count = models.PositiveIntegerField(default=0, verbose_name="댓글 수")
    
    # 메타 정보
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")

    class Meta:
        verbose_name = 'Bakery'
        verbose_name_plural = 'Bakeries'
        indexes = [
            models.Index(fields=['district']),  # 구별 조회 최적화
            models.Index(fields=['name']),       # 이름 검색 최적화
        ]

    def __str__(self):
        return f"{self.name} ({self.district})"


class BakeryLike(models.Model):
    """빵집 좋아요 모델
    
    한 사용자는 한 빵집에 한 번만 좋아요 가능
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bakery_likes',
        verbose_name="사용자"
    )
    bakery = models.ForeignKey(
        Bakery,
        on_delete=models.CASCADE,
        related_name='likes',
        verbose_name="빵집"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")

    class Meta:
        verbose_name = 'Bakery Like'
        verbose_name_plural = 'Bakery Likes'
        unique_together = ('user', 'bakery')  # 중복 좋아요 방지
        indexes = [
            models.Index(fields=['bakery', '-created_at']),  # 빵집별 좋아요 조회 최적화
        ]

    def __str__(self):
        return f"{self.user.nickname or self.user.username} ♥ {self.bakery.name}"


class BakeryComment(models.Model):
    """빵집 댓글 모델"""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='bakery_comments',
        verbose_name="작성자"
    )
    bakery = models.ForeignKey(
        Bakery,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name="빵집"
    )
    content = models.TextField(verbose_name="내용")
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="생성일")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="수정일")

    class Meta:
        verbose_name = 'Bakery Comment'
        verbose_name_plural = 'Bakery Comments'
        ordering = ['-created_at']  # 최신순 정렬
        indexes = [
            models.Index(fields=['bakery', '-created_at']),  # 빵집별 댓글 조회 최적화
        ]

    def __str__(self):
        preview = self.content[:30] + '...' if len(self.content) > 30 else self.content
        return f"{self.user.nickname or self.user.username}: {preview}"


class Recommendation(models.Model):
    """대화별 추천 결과를 저장하는 모델

    필드:
    - conversation: 관련 Conversation
    - bakery: 추천된 Bakery
    - similarity_score: 유사도 점수 (소수)
    - created_at: 생성 시각
    """

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='recommendations')
    bakery = models.ForeignKey(Bakery, on_delete=models.CASCADE)
    similarity_score = models.DecimalField(max_digits=6, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Recommendation'
        verbose_name_plural = 'Recommendations'

    def __str__(self):
        return f"Recommendation({self.id}) for Conversation({self.conversation_id}) -> {self.bakery.name} ({self.similarity_score})"