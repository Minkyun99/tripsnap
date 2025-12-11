from django.shortcuts import render, redirect
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.views.decorators.csrf import ensure_csrf_cookie
from .rag_wrapper import RAGWrapper
from .models import Conversation, Message
import json
from django.contrib.auth.decorators import login_required
from django.conf import settings


# `chatbot/` 루트 뷰: 로그인된 사용자가 키워드 선택 페이지로 이동합니다.
@login_required
def chatbot(request):
    return render(request, "chat/keyword_selection.html")


# GET: 키워드 선택 페이지 또는 Conversation을 생성한 뒤 채팅 룸을 렌더링합니다.
# POST: JSON 바디로 메시지를 받아 RAG 결과를 반환하고 메시지를 저장하는 API 엔드포인트입니다.
@ensure_csrf_cookie
@api_view(['GET', 'POST'])
def chat(request):
    # 수동 인증 검사: Django의 로그인 상태를 확인합니다.
    # - GET 요청은 로그인 페이지로 리다이렉트합니다 (브라우저 사용 시).
    # - POST(API) 요청은 JSON 응답으로 401을 반환합니다.
    if not request.user or not request.user.is_authenticated:
        if request.method == 'GET':
            # 로그인 페이지로 이동시키되, 완료 후 현재 경로로 돌아오게 합니다.
            return redirect(f"{settings.LOGIN_URL}?next={request.path}")
        return Response({'detail': '로그인 필요'}, status=status.HTTP_401_UNAUTHORIZED)
    if request.method == 'GET':
        # 템플릿에서 전달된 단일 선호(preference) 파라미터를 읽습니다. (이전 키인 characteristic도 지원)
        preference = request.GET.get('preference') or request.GET.get('characteristic') or ''

        # 선호 키워드가 없으면 키워드 선택 페이지로 이동
        if not preference:
            return render(request, 'chat/keyword_selection.html')

        # 선택적으로 전달된 다른 파라미터를 읽습니다.
        region = request.GET.get('region', '')
        dates = request.GET.get('dates', '')
        transport = request.GET.get('transport', '')

        # Conversation 객체를 생성합니다 (최소 정보만 보관).
        conv = Conversation.objects.create(user=request.user)

        # 사용자가 선택한 메타 정보를 시스템 메시지로 저장합니다.
        # JSON 문자열로 저장하여 이후에 파싱할 수 있게 합니다.
        meta = {
            'preference': preference,
            'region': region,
            'dates': dates,
            'transport': transport,
        }
        Message.objects.create(conversation=conv, sender=Message.SENDER_SYSTEM, content='__META__:' + json.dumps(meta, ensure_ascii=False))

        # 사용자가 선택한 내용을 요약하는 봇의 안내 메시지 두 개를 생성합니다.
        # 이 초기 메시지들은 OpenAI(LLM)를 호출하지 않고 서버에서 직접 생성됩니다.
        summary = f"선택하신 키워드: {preference}"
        prompt = "원하시는 것을 더 자세히 설명해주시겠어요? 그냥 추천해달라고 하시면 바로 추천을 시작할게요."

        Message.objects.create(conversation=conv, sender=Message.SENDER_BOT, content=summary)
        Message.objects.create(conversation=conv, sender=Message.SENDER_BOT, content=prompt)

        context = {
            'preference': preference,
            'region': region,
            'dates': dates,
            'transport': transport,
            'conversation_id': str(conv.id),
            'initial_bot_1': summary,
            'initial_bot_2': prompt,
        }
        return render(request, 'chat/room.html', context)

    # POST: API 스타일 요청 처리 (JSON 바디 예: {"message": "...", "conversation_id": "..."})
    if request.method == 'POST':
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
                conv = Conversation.objects.get(id=conversation_id)
            except Conversation.DoesNotExist:
                conv = None

        if conv is None:
            conv = Conversation.objects.create(user=request.user)

        # 사용자 메시지를 저장합니다.
        Message.objects.create(conversation=conv, sender=Message.SENDER_USER, content=message)

        # RAG 호출 여부 결정: 클라이언트의 trigger 플래그 또는 메시지에 '추천' 관련 단어가 포함된 경우
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
            meta_msg = Message.objects.filter(conversation=conv, sender=Message.SENDER_SYSTEM).order_by('created_at').first()
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

        result = RAGWrapper.chat(message=prompt_for_rag, use_llm=True)
        llm_response = result.get('llm_response')
        if llm_response:
            Message.objects.create(conversation=conv, sender=Message.SENDER_BOT, content=llm_response)

        return Response({'llm_response': llm_response, 'results': result.get('results', [])})

    # 허용되지 않는 HTTP 메서드에 대해서는 405 응답을 반환합니다.
    return Response({'error': 'Method not allowed'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)