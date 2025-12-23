from rest_framework import serializers
from .models import Bakery, BakeryLike, BakeryComment
from django.contrib.auth import get_user_model

User = get_user_model()

class ChatInitSerializer(serializers.Serializer):
    preference = serializers.CharField(max_length=100)
    region = serializers.CharField(max_length=100, required=False, allow_blank=True)
    dates = serializers.CharField(max_length=100, required=False, allow_blank=True)
    transport = serializers.CharField(max_length=100, required=False, allow_blank=True)

class BakeryListSerializer(serializers.ModelSerializer):
    """빵집 목록용 간단한 Serializer"""
    
    class Meta:
        model = Bakery
        fields = [
            'id',
            'name',
            'category',
            'district',
            'road_address',
            'rate',
            'keywords',
            'like_count',
            'comment_count',
        ]


class BakeryDetailSerializer(serializers.ModelSerializer):
    """빵집 상세 정보용 Serializer"""
    
    is_liked = serializers.SerializerMethodField()
    
    class Meta:
        model = Bakery
        fields = [
            'id',
            'name',
            'category',
            'district',
            'road_address',
            'jibun_address',
            'phone',
            'business_hours_raw',
            'monday',
            'tuesday',
            'wednesday',
            'thursday',
            'friday',
            'saturday',
            'sunday',
            'url',
            'latitude',
            'longitude',
            'rate',
            'keywords',
            'like_count',
            'comment_count',
            'is_liked',
            'created_at',
            'updated_at',
        ]
    
    def get_is_liked(self, obj):
        """현재 사용자가 좋아요를 눌렀는지 확인"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return BakeryLike.objects.filter(
                bakery=obj,
                user=request.user
            ).exists()
        return False


class BakeryCommentSerializer(serializers.ModelSerializer):
    """빵집 댓글 Serializer"""
    
    writer_nickname = serializers.CharField(source='user.nickname', read_only=True)
    writer_username = serializers.CharField(source='user.username', read_only=True)
    
    class Meta:
        model = BakeryComment
        fields = [
            'id',
            'writer_nickname',
            'writer_username',
            'content',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'writer_nickname', 'writer_username', 'created_at', 'updated_at']


class BakeryCommentCreateSerializer(serializers.ModelSerializer):
    """빵집 댓글 작성용 Serializer"""
    
    class Meta:
        model = BakeryComment
        fields = ['content']
    
    def validate_content(self, value):
        """댓글 내용 검증"""
        if not value.strip():
            raise serializers.ValidationError("댓글 내용을 입력해주세요.")
        if len(value) > 500:
            raise serializers.ValidationError("댓글은 500자 이내로 작성해주세요.")
        return value