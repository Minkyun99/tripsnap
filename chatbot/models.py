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
    """빵집 정보 저장 모델

    필드:
    - road_address: 도로명 주소
    - operating_hours: 영업시간(텍스트)
    - name: 가게 이름
    - phone: 연락처
    - keywords: 키워드/특징(쉼표로 구분)
    - url: 외부 URL (예: 지도 링크)
    """

    road_address = models.CharField(max_length=255, blank=True)
    operating_hours = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=50, blank=True)
    keywords = models.CharField(max_length=255, blank=True)
    url = models.URLField(blank=True)

    class Meta:
        verbose_name = 'Bakery'
        verbose_name_plural = 'Bakeries'

    def __str__(self):
        return f"{self.name} - {self.road_address}"


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