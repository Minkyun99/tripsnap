from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import transaction

from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from django.views.decorators.csrf import ensure_csrf_cookie

from .rag_wrapper import RAGWrapper
from .models import Conversation, Message, Bakery, BakeryLike, BakeryComment
from .serializers import (
    BakeryListSerializer,
    BakeryDetailSerializer,
    BakeryCommentSerializer,
    BakeryCommentCreateSerializer,
)

import json


# ==========================================
# 기존 Chatbot Views
# ==========================================

# 1) 기존과 동일: /chatbot/ → 키워드 선택 템플릿
@login_required
def chatbot(request):
    """
    브라우저에서 바로 /chatbot/ 으로 접근할 때 사용하는 템플릿 뷰.
    (기존 keyword_selection.html 렌더링)
    """
    return render(request, "chat/keyword_selection.html")


# 2) Vue용 초기화 API: /chatbot/init/ (POST)
#    → 기존 chat(GET)에서 하던 Conversation 생성 + META 저장 + 초기 봇 메시지 2개 생성 로직을
#      JSON 기반으로 옮긴 버전입니다.
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

    응답(JSON):
      {
        "conversation_id": "1",
        "preference": "...",
        "region": "...",
        "dates": "...",
        "transport": "...",
        "initial_messages": [
          {"role": "bot", "content": "선택하신 키워드: ..."},
          {"role": "bot", "content": "원하시는 것을 더 자세히..."}
        ]
      }
    """
    # 인증 체크
    user = request.user
    if not user or not user.is_authenticated:
        return Response({'detail': '로그인 필요'}, status=status.HTTP_401_UNAUTHORIZED)
    
    data = request.data

    preference = (data.get('preference') or '').strip()
    region = (data.get('region') or '').strip()
    dates = (data.get('dates') or '').strip()
    transport = (data.get('transport') or '').strip()

    if not preference:
        return Response(
            {'detail': 'preference(선호 키워드)는 필수입니다.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Conversation 생성 (기존 GET chat 로직과 동일)
    conv = Conversation.objects.create(user=user)

    meta = {
        'preference': preference,
        'region': region,
        'dates': dates,
        'transport': transport,
    }
    # META 시스템 메시지 저장
    Message.objects.create(
        conversation=conv,
        sender=Message.SENDER_SYSTEM,
        content='__META__:' + json.dumps(meta, ensure_ascii=False),
    )

    # 안내용 초기 봇 메시지 2개 생성 (기존과 동일)
    summary = f"선택하신 키워드: {preference}"
    prompt = "원하시는 것을 더 자세히 설명해주시겠어요? 그냥 추천해달라고 하시면 바로 추천을 시작할게요."

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


# 3) 실제 대화 API: /chatbot/chat/ (POST)
#    → 아래 로직은 질문에 주신 기존 chat(view)를
#      Vue + JSON 환경에 맞게 그대로 옮긴 것입니다.
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

    응답(JSON):
      {
        "llm_response": "...",
        "results": [ ... RAG 추천 결과 ... ]
      }
    """
    # 수동 인증 검사: 기존 코드 그대로 유지
    user = request.user
    if not user or not user.is_authenticated:
        return Response({'detail': '로그인 필요'}, status=status.HTTP_401_UNAUTHORIZED)

    # request.data(JSON) 또는 request.POST 폼 데이터를 안전하게 처리
    data = request.data if hasattr(request, 'data') else request.POST

    # 클라이언트로부터 온 메시지와 대화 ID, 선택적 trigger 플래그를 읽습니다.
    message = data.get('message')
    conversation_id = data.get('conversation_id')
    # trigger가 True이면 RAG(LLM) 호출; 아니면 단순 저장만 수행합니다.
    trigger = data.get('trigger')

    if not message:
        return Response({'error': '메시지를 입력해주세요'}, status=status.HTTP_400_BAD_REQUEST)

    # 대화(Conversation)를 찾습니다.
    conv = None
    if conversation_id:
        try:
            # 사용자 소유의 대화인지 한 번 더 체크 (보안 강화)
            conv = Conversation.objects.get(id=conversation_id, user=user)
        except Conversation.DoesNotExist:
            conv = None

    if conv is None:
        conv = Conversation.objects.create(user=user)

    # 사용자 메시지를 저장합니다.
    Message.objects.create(
        conversation=conv,
        sender=Message.SENDER_USER,
        content=message,
    )

    # RAG 호출 여부 결정: 기존 코드 로직 그대로
    should_call_rag = False
    if trigger and str(trigger).lower() in ['1', 'true', 'yes']:
        should_call_rag = True
    if '추천' in message or '추천해' in message:
        should_call_rag = True

    if not should_call_rag:
        # RAG를 호출하지 않고 저장만 한 경우, 저장 완료 응답을 반환합니다.
        return Response({'saved': True})

    # 대화에서 메타 시스템 메시지를 찾아 region/keywords 등을 복원합니다.
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
                region_context = ''
                keywords_context = ''
    except Exception:
        region_context = ''
        keywords_context = ''

    # 프롬프트에 지역 및 선호 키워드를 포함
    prompt_for_rag = message
    parts = []
    if region_context:
        parts.append(f"지역: {region_context}")
    if keywords_context:
        parts.append(f"선호: {keywords_context}")
    if parts:
        prompt_for_rag = "\n".join(parts) + "\n" + message

    # ✅ 기존 코드와 동일하게 RAGWrapper.chat 호출
    try:
        result = RAGWrapper.chat(message=prompt_for_rag, use_llm=True)
    except Exception as e:
        return Response(
            {'detail': f'추천 엔진 호출 중 오류가 발생했습니다: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    llm_response = result.get('llm_response')
    if llm_response:
        Message.objects.create(
            conversation=conv,
            sender=Message.SENDER_BOT,
            content=llm_response,
        )

    # RAG 결과를 DB의 Bakery 객체와 매핑
    rag_results = result.get('results', [])
    enriched_results = []
    
    for rag_result in rag_results:
        # RAG 결과에서 빵집 이름 추출 (place_name 또는 name)
        bakery_name = rag_result.get('place_name') or rag_result.get('name', '')
        
        if not bakery_name:
            continue
        
        try:
            # DB에서 빵집 조회
            bakery = Bakery.objects.get(name=bakery_name)
            
            # DB 데이터로 enriched 결과 생성
            enriched_results.append({
                'id': bakery.id,  # DB의 실제 ID
                'name': bakery.name,
                'place_name': bakery.name,  # 프론트엔드 호환성
                'district': bakery.district,
                'address': bakery.road_address or bakery.jibun_address,
                'rating': bakery.naver_rate or bakery.kakao_rate,
                'phone': bakery.phone,
                'url': bakery.url,
            })
        except Bakery.DoesNotExist:
            # DB에 없으면 RAG 결과 그대로 사용 (id 없음)
            enriched_results.append(rag_result)
        except Bakery.MultipleObjectsReturned:
            # 중복된 이름이면 첫 번째 것 사용
            bakery = Bakery.objects.filter(name=bakery_name).first()
            enriched_results.append({
                'id': bakery.id,
                'name': bakery.name,
                'place_name': bakery.name,
                'district': bakery.district,
                'address': bakery.road_address or bakery.jibun_address,
                'rating': bakery.naver_rate or bakery.kakao_rate,
                'phone': bakery.phone,
                'url': bakery.url,
            })

    return Response(
        {
            'llm_response': llm_response,
            'results': enriched_results,
        },
        status=status.HTTP_200_OK,
    )


# ==========================================
# Bakery Views (FBV로 작성)
# ==========================================

@api_view(['GET'])
def bakery_list(request):
    """
    빵집 목록 조회 (검색, 필터링)
    GET /api/bakery/
    
    Query Parameters:
        - district: 구 필터링 (예: district=동구)
        - search: 이름 검색 (예: search=하늘만큼)
        - ordering: 정렬 (예: ordering=-like_count)
    """
    queryset = Bakery.objects.all()
    
    # 구 필터링
    district = request.query_params.get('district', None)
    if district:
        queryset = queryset.filter(district=district)
    
    # 이름 검색
    search = request.query_params.get('search', None)
    if search:
        queryset = queryset.filter(name__icontains=search)
    
    # 정렬
    ordering = request.query_params.get('ordering', '-like_count')
    queryset = queryset.order_by(ordering)
    
    serializer = BakeryListSerializer(queryset, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
def bakery_detail(request, bakery_id):
    """
    빵집 상세 정보 조회
    GET /api/bakery/<bakery_id>/
    """
    bakery = get_object_or_404(Bakery, id=bakery_id)
    serializer = BakeryDetailSerializer(bakery, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
def bakery_like_toggle(request, bakery_id):
    """
    빵집 좋아요 토글
    POST /api/bakery/<bakery_id>/like/
    
    Returns:
        {
            "is_liked": true/false,
            "like_count": 123
        }
    """
    # 인증 체크
    user = request.user
    if not user or not user.is_authenticated:
        return Response({'detail': '로그인 필요'}, status=status.HTTP_401_UNAUTHORIZED)
    
    bakery = get_object_or_404(Bakery, id=bakery_id)
    
    try:
        with transaction.atomic():
            # 좋아요 존재 여부 확인
            like, created = BakeryLike.objects.get_or_create(
                bakery=bakery,
                user=user
            )
            
            if not created:
                # 이미 좋아요가 있으면 삭제 (토글)
                like.delete()
                bakery.like_count = max(0, bakery.like_count - 1)
                bakery.save(update_fields=['like_count'])
                is_liked = False
            else:
                # 새로 좋아요 생성
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
    """
    빵집 댓글 목록 조회
    GET /api/bakery/<bakery_id>/comments/
    """
    comments = BakeryComment.objects.filter(
        bakery_id=bakery_id
    ).select_related('user').order_by('-created_at')
    
    serializer = BakeryCommentSerializer(comments, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
def bakery_comment_create(request, bakery_id):
    """
    빵집 댓글 작성
    POST /api/bakery/<bakery_id>/comments/create/
    
    Request Body:
        {
            "content": "맛있어요!"
        }
    """
    # 인증 체크
    user = request.user
    if not user or not user.is_authenticated:
        return Response({'detail': '로그인 필요'}, status=status.HTTP_401_UNAUTHORIZED)
    
    bakery = get_object_or_404(Bakery, id=bakery_id)
    
    serializer = BakeryCommentCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        with transaction.atomic():
            # 댓글 저장
            comment = serializer.save(
                user=user,
                bakery=bakery
            )
            
            # 빵집의 댓글 수 증가
            bakery.comment_count += 1
            bakery.save(update_fields=['comment_count'])
        
        # 생성된 댓글 정보 반환
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
    """
    빵집 댓글 삭제 (본인만 가능)
    DELETE /api/bakery/<bakery_id>/comments/<comment_id>/
    """
    # 인증 체크
    user = request.user
    if not user or not user.is_authenticated:
        return Response({'detail': '로그인 필요'}, status=status.HTTP_401_UNAUTHORIZED)
    
    comment = get_object_or_404(
        BakeryComment,
        id=comment_id,
        bakery_id=bakery_id
    )
    
    # 본인 확인
    if comment.user != user:
        return Response(
            {'detail': '본인의 댓글만 삭제할 수 있습니다.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        with transaction.atomic():
            bakery = comment.bakery
            comment.delete()
            
            # 빵집의 댓글 수 감소
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