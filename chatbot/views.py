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
import re
import logging

# 로거 설정
logger = logging.getLogger(__name__)


# ==========================================
# 유틸리티 함수
# ==========================================

def normalize_bakery_name(name):
    """
    빵집 이름을 정규화하여 매칭률을 높입니다.
    - 공백 제거
    - 괄호 및 괄호 내용 제거
    - 특수문자 제거
    """
    if not name:
        return ""
    
    # 괄호와 괄호 안의 내용 제거 (예: "하늘만큼 땅만큼(대전본점)" → "하늘만큼 땅만큼")
    name = re.sub(r'\([^)]*\)', '', name)
    name = re.sub(r'\[[^\]]*\]', '', name)
    
    # 공백 제거
    name = name.replace(' ', '')
    
    # 특수문자 제거 (한글, 영문, 숫자만 남김)
    name = re.sub(r'[^가-힣a-zA-Z0-9]', '', name)
    
    return name.strip()


def find_bakery_fuzzy(bakery_name):
    """
    퍼지 매칭을 통해 DB에서 빵집을 찾습니다.
    1. 정확한 이름으로 검색
    2. 정규화된 이름으로 검색
    3. 부분 매칭 검색
    """
    if not bakery_name:
        return None
    
    # 1. 정확한 이름으로 검색
    try:
        return Bakery.objects.get(name=bakery_name)
    except Bakery.DoesNotExist:
        pass
    except Bakery.MultipleObjectsReturned:
        return Bakery.objects.filter(name=bakery_name).first()
    
    # 2. 정규화된 이름으로 검색
    normalized_search = normalize_bakery_name(bakery_name)
    if normalized_search:
        for bakery in Bakery.objects.all():
            if normalize_bakery_name(bakery.name) == normalized_search:
                return bakery
    
    # 3. 부분 매칭 (이름에 포함되는지 확인)
    if len(bakery_name) >= 3:  # 너무 짧은 이름은 부정확할 수 있음
        try:
            # 공백 제거한 이름으로 icontains 검색
            clean_name = bakery_name.replace(' ', '')
            candidates = Bakery.objects.filter(name__icontains=clean_name)
            if candidates.exists():
                return candidates.first()
        except Exception:
            pass
    
    return None


def is_recommendation_response(llm_response):
    """
    LLM 응답이 실제로 빵집을 추천하는 내용인지 확인합니다.
    
    추천 응답으로 간주되는 경우:
    - "추천", "코스", "매장" 등의 키워드 포함
    - "1.", "2.", "3." 같은 리스트 형식
    - 구체적인 빵집 이름이나 주소 언급
    
    추천 응답이 아닌 경우:
    - "찾지 못했다", "없습니다" 등 실패 메시지
    - "종류", "차이", "역사", "만드는 법" 등 지식 설명
    
    Args:
        llm_response (str): LLM의 응답 텍스트
        
    Returns:
        bool: 빵집 추천 응답이면 True, 아니면 False
    """
    if not llm_response:
        return False
    
    # 1. 실패 메시지 키워드 체크 (최우선)
    failure_keywords = [
        "찾지 못했습니다",
        "찾을 수 없습니다",
        "조건에 맞는 빵집이 없",
        "해당하는 빵집이 없",
        "추천할 빵집이 없",
        "적합한 빵집이 없",
        "검색 결과가 없",
    ]
    
    for keyword in failure_keywords:
        if keyword in llm_response:
            logger.info(f"🚫 [NOT_RECOMMENDATION] 실패 키워드 '{keyword}' 감지")
            return False
    
    # 2. 지식/설명 모드 키워드 체크
    knowledge_keywords = [
        "종류가 있",
        "종류는",
        "차이점",
        "차이가",
        "역사",
        "기원",
        "유래",
        "만드는 법",
        "만드는 방법",
        "레시피",
        "특징은",
        "정의는",
    ]
    
    knowledge_count = 0
    for keyword in knowledge_keywords:
        if keyword in llm_response:
            knowledge_count += 1
    
    # 지식 키워드가 2개 이상이면 지식 모드로 판단
    if knowledge_count >= 2:
        logger.info(f"🚫 [NOT_RECOMMENDATION] 지식 모드로 판단 (키워드 {knowledge_count}개)")
        return False
    
    # 3. 추천 키워드 체크
    recommendation_keywords = [
        "추천드립니다",
        "추천드려요",
        "추천해드립니다",
        "추천합니다",
        "코스",
        "방문하시면",
        "가보시면",
        "매장",
        "빵집",
        "베이커리",
        "이동 시간",
        "영업시간",
        "주소",
        "전화",
    ]
    
    recommendation_count = 0
    for keyword in recommendation_keywords:
        if keyword in llm_response:
            recommendation_count += 1
    
    # 4. 리스트 형식 체크 (1., 2., 3. 또는 ①, ②, ③)
    has_numbered_list = bool(re.search(r'[1-9]\.|①|②|③|④|⑤', llm_response))
    
    # 5. 판단 로직
    # - 추천 키워드가 2개 이상 있으면 추천 모드
    # - 또는 번호 리스트 + 추천 키워드 1개 이상
    is_recommendation = False
    
    if recommendation_count >= 2:
        is_recommendation = True
        logger.info(f"✅ [IS_RECOMMENDATION] 추천 키워드 {recommendation_count}개 감지")
    elif has_numbered_list and recommendation_count >= 1:
        is_recommendation = True
        logger.info(f"✅ [IS_RECOMMENDATION] 번호 리스트 + 추천 키워드 감지")
    else:
        logger.info(f"🚫 [NOT_RECOMMENDATION] 추천 응답 조건 미충족 (키워드: {recommendation_count}, 리스트: {has_numbered_list})")
    
    return is_recommendation


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

    # Conversation 생성
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

    # 안내용 초기 봇 메시지 2개 생성
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
        "results": [ ... RAG 추천 결과 ... ]  # 추천일 때만 포함
      }
    """
    # 수동 인증 검사
    user = request.user
    if not user or not user.is_authenticated:
        return Response({'detail': '로그인 필요'}, status=status.HTTP_401_UNAUTHORIZED)

    # request.data(JSON) 또는 request.POST 폼 데이터를 안전하게 처리
    data = request.data if hasattr(request, 'data') else request.POST

    # 클라이언트로부터 온 메시지와 대화 ID, 선택적 trigger 플래그를 읽습니다.
    message = data.get('message')
    conversation_id = data.get('conversation_id')
    trigger = data.get('trigger')

    if not message:
        return Response({'error': '메시지를 입력해주세요'}, status=status.HTTP_400_BAD_REQUEST)

    # 대화(Conversation)를 찾습니다.
    conv = None
    if conversation_id:
        try:
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

    # RAG 호출 여부 결정
    should_call_rag = False
    if trigger and str(trigger).lower() in ['1', 'true', 'yes']:
        should_call_rag = True
    if '추천' in message or '추천해' in message:
        should_call_rag = True

    if not should_call_rag:
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

    # RAGWrapper.chat 호출
    try:
        logger.info(f"🔍 [DEBUG] RAG 호출 시작 - 프롬프트: {prompt_for_rag}")
        result = RAGWrapper.chat(message=prompt_for_rag, use_llm=True)
        logger.info(f"🔍 [DEBUG] RAG 응답 받음 - result keys: {result.keys()}")
        logger.info(f"🔍 [DEBUG] RAG results 개수: {len(result.get('results', []))}")
    except Exception as e:
        logger.error(f"❌ [DEBUG] RAG 호출 실패: {str(e)}")
        return Response(
            {'detail': f'추천 엔진 호출 중 오류가 발생했습니다: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    llm_response = result.get('llm_response')
    if llm_response:
        logger.info(f"💬 [DEBUG] LLM 응답 (앞 200자): {llm_response[:200]}...")
        Message.objects.create(
            conversation=conv,
            sender=Message.SENDER_BOT,
            content=llm_response,
        )

    # ✨✨ 핵심 개선: LLM 응답이 실제 추천 내용인지 확인 ✨✨
    if not is_recommendation_response(llm_response):
        logger.info("🚫 [NOT_RECOMMENDATION] 추천 응답이 아님 - results를 포함하지 않습니다")
        response_data = {
            'llm_response': llm_response,
            # results 키를 아예 포함하지 않음!
        }
        return Response(response_data, status=status.HTTP_200_OK)

    # 여기까지 왔다면 정상적인 추천 응답
    logger.info("✅ [IS_RECOMMENDATION] 추천 응답으로 판단 - results 처리 시작")

    # 퍼지 매칭을 사용한 DB 매핑
    rag_results = result.get('results', [])
    logger.info(f"🍞 [DEBUG] RAG에서 반환한 빵집 수: {len(rag_results)}")
    
    enriched_results = []
    
    for idx, rag_result in enumerate(rag_results):
        # RAG 결과에서 빵집 이름 추출
        bakery_name = rag_result.get('place_name') or rag_result.get('name', '')
        logger.info(f"🔍 [DEBUG] [{idx+1}] RAG 빵집 이름: {bakery_name}")
        
        if not bakery_name:
            logger.warning(f"⚠️ [DEBUG] [{idx+1}] 빵집 이름 없음 - 건너뜀")
            continue
        
        # 퍼지 매칭으로 DB에서 빵집 찾기
        bakery = find_bakery_fuzzy(bakery_name)
        
        if bakery:
            logger.info(f"✅ [DEBUG] [{idx+1}] DB 매칭 성공 - ID: {bakery.id}, 이름: {bakery.name}")
            # DB 매칭 성공
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
        else:
            logger.warning(f"⚠️ [DEBUG] [{idx+1}] DB에 없는 빵집 - RAG 결과 그대로 사용: {bakery_name}")
            # DB에 없으면 RAG 결과 그대로 사용
            enriched_results.append({
                'id': None,  # 명시적으로 None 설정
                'name': bakery_name,
                'place_name': bakery_name,
                'district': rag_result.get('district', ''),
                'address': rag_result.get('address', ''),
                'rating': rag_result.get('rating', ''),
                'phone': rag_result.get('phone', ''),
                'url': rag_result.get('url', ''),
            })

    logger.info(f"📊 [DEBUG] 최종 enriched_results 개수: {len(enriched_results)}")

    # enriched_results가 있을 때만 results를 응답에 포함
    response_data = {
        'llm_response': llm_response,
    }
    
    if enriched_results:
        response_data['results'] = enriched_results
        logger.info(f"✅ [DEBUG] results를 응답에 포함 - {len(enriched_results)}개 빵집")
    else:
        logger.warning(f"⚠️ [DEBUG] enriched_results가 비어있음 - results 미포함")
    
    logger.info(f"🎯 [DEBUG] 최종 응답 keys: {response_data.keys()}")
    
    return Response(response_data, status=status.HTTP_200_OK)


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
    """
    빵집 댓글 삭제 (본인만 가능)
    DELETE /api/bakery/<bakery_id>/comments/<comment_id>/
    """
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