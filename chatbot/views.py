from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render
from .rag_wrapper import RAGWrapper
# csrf 꺼두는 기능 https://dev-guardy.tistory.com/80
from django.views.decorators.csrf import csrf_exempt

# Create your views here.
def chatbot(request):
    return render(request, "chat/room.html")

@api_view(['POST'])
# @csrf_exempt
def chat(request):
    if request.method == 'POST':
        print("=== 요청 받음 ===")
        message = request.data.get('message')
        if not message:
            return Response(
                {'error': '메시지를 입력해주세요'},
                status=status.HTTP_400_BAD_REQUEST)
        
        print("RAG 호출 시작...")
        result = RAGWrapper.chat(message=message, use_llm=True)
        context = {
            'llm_response': result['llm_response'],
            'results': result['results']
        }
        return Response(context)