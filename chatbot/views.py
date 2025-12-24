from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import transaction

from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from django.views.decorators.csrf import ensure_csrf_cookie

from .enhanced_rag_adapter import EnhancedRAGAdapter
from .models import Conversation, Message, Bakery, BakeryLike, BakeryComment
from .serializers import (
    BakeryListSerializer,
    BakeryDetailSerializer,
    BakeryCommentSerializer,
    BakeryCommentCreateSerializer,
)

import json
import logging

# 로거 설정
logger = logging.getLogger(__name__)

# Enhanced RAG Adapter 초기화
enhanced_rag = EnhancedRAGAdapter(Bakery)


# ==========================================
# Chatbot Views
# ==========================================

@login_required
def chatbot(request):
    """
    브라우저에서 바로 /chatbot/ 으로 접근할 때 사용하는 템플릿 뷰.
    """
    return render(request, "chat/keyword_selection.html")


@api_view(['POST'])
def chat_init(request):
    """
    Vue의 KeywordSelectionView에서 호출하는 초기화 엔드포인트.
    
    POST /chatbot/init/
    body(JSON):
      {
        "preference": "줄 서도 먹는 빵집",
        "region": "대전",
        "dates": "주말",
        "transport": "대중교통"
      }
    """
    user = request.user
    if not user or not user.is_authenticated:
        return Response({'detail': '로그인 필요'}, status=status.HTTP_401_UNAUTHORIZED)
    
    data = request.data
    preference = (data.get('preference') or '').strip()
    region = (data.get('region') or '').strip()
    dates = (data.get('dates') or '').strip()
    transport = (data.get('transport') or '').strip()

    # 🔍 디버깅: 받은 키워드 로그
    logger.info(f"🎯 [INIT] 받은 키워드 - preference: '{preference}', region: '{region}', dates: '{dates}', transport: '{transport}'")

    # ✨ 모든 키워드는 선택 사항 - 필수 검증 제거
    # 사용자가 아무것도 선택하지 않아도 챗봇 시작 가능

    # Conversation 생성
    conv = Conversation.objects.create(user=user)

    meta = {
        'preference': preference,
        'region': region,
        'dates': dates,
        'transport': transport,
    }
    
    logger.info(f"💾 [INIT] 저장할 메타 데이터: {meta}")
    
    # META 시스템 메시지 저장
    Message.objects.create(
        conversation=conv,
        sender=Message.SENDER_SYSTEM,
        content='__META__:' + json.dumps(meta, ensure_ascii=False),
    )

    # 안내용 초기 봇 메시지 - 선택한 모든 키워드를 보여줌
    selected_items = []
    
    if preference and preference != '상관없음':
        selected_items.append(f"선호: {preference}")
    
    if region and region != '대전 전체':
        selected_items.append(f"지역: {region}")
    
    if dates and dates != '상관없음':
        selected_items.append(f"날짜: {dates}")
    
    if transport and transport != '상관없음':
        selected_items.append(f"이동수단: {transport}")
    
    # 선택한 키워드가 있으면 표시, 없으면 환영 메시지
    if selected_items:
        summary = f"선택하신 키워드:\n• " + "\n• ".join(selected_items)
        prompt = "원하시는 것을 더 자세히 설명해주시겠어요? 그냥 추천해달라고 하시면 바로 추천을 시작할게요."
    else:
        summary = "안녕하세요! 대전 빵집 추천 챗봇입니다. 😊"
        prompt = "어떤 빵집을 찾으시나요? 원하시는 조건을 자유롭게 말씀해주세요!"

    Message.objects.create(conversation=conv, sender=Message.SENDER_BOT, content=summary)
    Message.objects.create(conversation=conv, sender=Message.SENDER_BOT, content=prompt)

    return Response(
        {
            'conversation_id': str(conv.id),
            'preference': preference,
            'region': region,
            'dates': dates,
            'transport': transport,
            'initial_messages': [
                {'role': 'bot', 'content': summary},
                {'role': 'bot', 'content': prompt},
            ],
        },
        status=status.HTTP_201_CREATED,
    )


@ensure_csrf_cookie
@api_view(['POST'])
def chat(request):
    """
    Vue의 ChatbotView에서 호출하는 실제 대화 엔드포인트.
    
    POST /chatbot/chat/
    body(JSON):
      {
        "message": "에그타르트 맛집 추천해줘",
        "conversation_id": "1",
        "trigger": true
      }
    """
    # 인증 검사
    user = request.user
    if not user or not user.is_authenticated:
        return Response({'detail': '로그인 필요'}, status=status.HTTP_401_UNAUTHORIZED)

    data = request.data if hasattr(request, 'data') else request.POST

    message = data.get('message')
    conversation_id = data.get('conversation_id')
    trigger = data.get('trigger')

    if not message:
        return Response({'error': '메시지를 입력해주세요'}, status=status.HTTP_400_BAD_REQUEST)

    # 대화 찾기 또는 생성
    conv = None
    if conversation_id:
        try:
            conv = Conversation.objects.get(id=conversation_id, user=user)
        except Conversation.DoesNotExist:
            conv = None

    if conv is None:
        conv = Conversation.objects.create(user=user)

    # 사용자 메시지 저장
    Message.objects.create(
        conversation=conv,
        sender=Message.SENDER_USER,
        content=message,
    )

    # RAG 호출 여부 결정
    should_call_rag = False
    if trigger and str(trigger).lower() in ['1', 'true', 'yes']:
        should_call_rag = True
    if '추천' in message or '추천해' in message:
        should_call_rag = True

    if not should_call_rag:
        return Response({'saved': True})

    # 메타 정보 복원 (region, keywords)
    region_context = ''
    keywords_context = ''
    try:
        meta_msg = (
            Message.objects
            .filter(conversation=conv, sender=Message.SENDER_SYSTEM)
            .order_by('created_at')
            .first()
        )
        if meta_msg and meta_msg.content.startswith('__META__:'):
            meta_json = meta_msg.content.split('__META__:', 1)[1]
            try:
                meta = json.loads(meta_json)
                region_context = meta.get('region', '') or ''
                keywords_context = meta.get('preference', '') or ''
            except Exception:
                pass
    except Exception:
        pass

    # 프롬프트 구성 (자연스러운 문장 형식)
    prompt_for_rag = message
    
    context_parts = []
    if region_context:
        context_parts.append(f"{region_context}에서")
    if keywords_context and keywords_context.strip():
        context_parts.append(f"{keywords_context} 관련")
    
    if context_parts:
        context_str = " ".join(context_parts)
        prompt_for_rag = f"{context_str} {message}"

    # ✨ Enhanced RAG Adapter 호출 (모든 비즈니스 로직 위임)
    try:
        logger.info(f"🔍 [CHAT] RAG 호출 - 프롬프트: {prompt_for_rag}")
        result = enhanced_rag.answer_query_with_enrichment(
            query=prompt_for_rag,
            use_llm=True
        )
    except Exception as e:
        logger.error(f"❌ [CHAT] RAG 호출 실패: {str(e)}")
        return Response(
            {'detail': f'추천 엔진 호출 중 오류가 발생했습니다: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    # LLM 응답 저장
    llm_response = result.get('llm_response')
    if llm_response:
        Message.objects.create(
            conversation=conv,
            sender=Message.SENDER_BOT,
            content=llm_response,
        )

    # 응답 반환
    # enhanced_rag가 이미 results 포함 여부를 결정했음
    return Response(result, status=status.HTTP_200_OK)


# ==========================================
# Bakery Views (FBV)
# ==========================================

@api_view(['GET'])
def bakery_list(request):
    """빵집 목록 조회"""
    queryset = Bakery.objects.all()
    
    district = request.query_params.get('district', None)
    if district:
        queryset = queryset.filter(district=district)
    
    search = request.query_params.get('search', None)
    if search:
        queryset = queryset.filter(name__icontains=search)
    
    ordering = request.query_params.get('ordering', '-like_count')
    queryset = queryset.order_by(ordering)
    
    serializer = BakeryListSerializer(queryset, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
def bakery_detail(request, bakery_id):
    """빵집 상세 정보 조회"""
    bakery = get_object_or_404(Bakery, id=bakery_id)
    serializer = BakeryDetailSerializer(bakery, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
def bakery_like_toggle(request, bakery_id):
    """빵집 좋아요 토글"""
    user = request.user
    if not user or not user.is_authenticated:
        return Response({'detail': '로그인 필요'}, status=status.HTTP_401_UNAUTHORIZED)
    
    bakery = get_object_or_404(Bakery, id=bakery_id)
    
    try:
        with transaction.atomic():
            like, created = BakeryLike.objects.get_or_create(
                bakery=bakery,
                user=user
            )
            
            if not created:
                like.delete()
                bakery.like_count = max(0, bakery.like_count - 1)
                bakery.save(update_fields=['like_count'])
                is_liked = False
            else:
                bakery.like_count += 1
                bakery.save(update_fields=['like_count'])
                is_liked = True
            
            return Response({
                'is_liked': is_liked,
                'like_count': bakery.like_count,
            }, status=status.HTTP_200_OK)
    
    except Exception as e:
        return Response(
            {'detail': f'좋아요 처리 중 오류가 발생했습니다: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
def bakery_comments_list(request, bakery_id):
    """빵집 댓글 목록 조회"""
    comments = BakeryComment.objects.filter(
        bakery_id=bakery_id
    ).select_related('user').order_by('-created_at')
    
    serializer = BakeryCommentSerializer(comments, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
def bakery_comment_create(request, bakery_id):
    """빵집 댓글 작성"""
    user = request.user
    if not user or not user.is_authenticated:
        return Response({'detail': '로그인 필요'}, status=status.HTTP_401_UNAUTHORIZED)
    
    bakery = get_object_or_404(Bakery, id=bakery_id)
    
    serializer = BakeryCommentCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        with transaction.atomic():
            comment = serializer.save(
                user=user,
                bakery=bakery
            )
            
            bakery.comment_count += 1
            bakery.save(update_fields=['comment_count'])
        
        output_serializer = BakeryCommentSerializer(comment)
        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED
        )
    
    except Exception as e:
        return Response(
            {'detail': f'댓글 작성 중 오류가 발생했습니다: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['DELETE'])
def bakery_comment_delete(request, bakery_id, comment_id):
    """빵집 댓글 삭제"""
    user = request.user
    if not user or not user.is_authenticated:
        return Response({'detail': '로그인 필요'}, status=status.HTTP_401_UNAUTHORIZED)
    
    comment = get_object_or_404(
        BakeryComment,
        id=comment_id,
        bakery_id=bakery_id
    )
    
    if comment.user != user:
        return Response(
            {'detail': '본인의 댓글만 삭제할 수 있습니다.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        with transaction.atomic():
            bakery = comment.bakery
            comment.delete()
            
            bakery.comment_count = max(0, bakery.comment_count - 1)
            bakery.save(update_fields=['comment_count'])
        
        return Response(
            {'detail': '댓글이 삭제되었습니다.'},
            status=status.HTTP_204_NO_CONTENT
        )
    
    except Exception as e:
        return Response(
            {'detail': f'댓글 삭제 중 오류가 발생했습니다: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )