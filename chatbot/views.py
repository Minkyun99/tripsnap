from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from django.views.decorators.csrf import ensure_csrf_cookie

from .rag_wrapper import RAGWrapper
from .models import Conversation, Message

import json


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
@permission_classes([IsAuthenticated])
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
    conv = Conversation.objects.create(user=request.user)

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

    return Response(
        {
            'llm_response': llm_response,
            'results': result.get('results', []),
        },
        status=status.HTTP_200_OK,
    )
