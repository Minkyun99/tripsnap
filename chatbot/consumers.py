# chatbot/consumers.py
# consumers란? Django의 View의 비동기 버전. 비동기 통신(WebSocket, long-polling 등)을 처리하기 위해 만들어진 구조.
# Django의 views.py는 HTTP 요청을 처리하는 거라면, Channel에서는 Websocket 연결이나 다른 프로토콜 이벤트를 처리하는 단위가 Consumer이다.
# 클라-서버 간 지속적인 연결 상태에서 발생하는 이벤트를 관리한다.

# 해당 클래스 대한 설명: https://channels.readthedocs.io/en/latest/tutorial/part_2.html#enable-a-channel-layer
import json

from channels.generic.websocket import AsyncWebsocketConsumer  # Django Channels가 제공하는 비동기 웹소켓 Consumer 기본 클래스.
# connect/receive/disconnect 같은 비동기 메서드를 오버라이드해서 웹소켓 동작을 정의한다.
from channels.db import database_sync_to_async  # 동기 작업을 비동기 작업으로 한다.

class ChatConsumer(AsyncWebsocketConsumer):
    # 클라이언트가 WebSocket을 통해 서버에 연결
    async def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"chat_{self.room_name}"  # 같은 방에 있는 클라이언트들이 모두 이 그룹에 묶인다.

        # Join room group
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        # group_add: 현재 연결 채널(self.channel_name)을 해당 그룹에 가입시킨다.
        # channel_layer는 Redis 등 백엔드를 통해 서버 간 메시지 라우팅을 담당한다.

        await self.accept()  # 웹소켓 핸드셰이크를 완료하고 연결을 수락한다.

        # 연결 확인 메시지
        await self.send(text_data=json.dumps({
            'type': 'connection',
            'message': 'Connected to TripSnap chatbot'
        }))

    # 연결이 끊길 때
    async def disconnect(self, close_code):  # close_code는 연결 종료 사유 코드(WebSocket 표준)를 나타낸다.
        # Leave room group
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)
        # group_discard: 현재 채널을 그룹에서 제거하여 더 이상 브로드캐스트 대상이 되지 않게 한다.

    # 클라이언트가 메시지를 보낼 때 실행되어 데이터를 처리
    async def receive(self, text_data):
        try:
            text_data_json = json.loads(text_data)  # json.loads: 수신한 JSON 문자열을 파이썬 딕셔너리로 변환한다.
            message = text_data_json["message"]  # message 추출: 클라이언트가 보낸 메시지 본문을 꺼낸다.

            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name, {"type": "chat.message", "message": message}
                # group_send: 같은 그룹(방)의 모든 채널에 이벤트를 브로드캐스트한다.
                # 이벤트 딕셔너리의 "type" 필드는 이 Consumer에서 호출할 핸들러 메서드 이름을 지정한다.
                # "chat.message" → chat_message 메서드가 호출된다(점(.)은 밑줄로 변환 규칙 적용).
            )

        except Exception as e:
            await self.send(text_data=json.dumps({
            'type': 'error',
            'message': f'Error: {str(e)}'
        }))

    # Receive message from room group
    # async def chat_message(self, event):
    #     message = event["message"]  # 브로드캐스트된 메시지 내용 추출

    #     # Send message(JSON 문자열) to WebSocket
    #     await self.send(text_data=json.dumps({"message": message}))
    
    @database_sync_to_async
    def get_rag_response(self, message, use_llm):
        """RAG 시스템 호출 (동기 -> 비동기 변환)"""
        from .rag_wrapper import RAGWrapper
        return RAGWrapper.chat(message, use_llm)