# chatbot/consumers.py
# consumers란? Django의 View의 비동기 버전. 비동기 통신(WebSocket, long-polling 등)을 처리하기 위해 만들어진 구조.
# Django의 views.py는 HTTP 요청을 처리하는 거라면, Channel에서는 Websocket 연결이나 다른 프로토콜 이벤트를 처리하는 단위가 Consumer이다.
# 클라-서버 간 지속적인 연결 상태에서 발생하는 이벤트를 관리한다.

# 해당 클래스 대한 설명: https://channels.readthedocs.io/en/latest/tutorial/part_2.html#enable-a-channel-layer
import json

from asgiref.sync import async_to_sync
from channels.generic.websocket import WebsocketConsumer


class ChatConsumer(WebsocketConsumer):
    # 클라이언트가 WebSocket을 통해 서버에 연결
    def connect(self):
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = f"chat_{self.room_name}"

        # Join room group
        async_to_sync(self.channel_layer.group_add)(
            self.room_group_name, self.channel_name
        )

        self.accept()

    # 연결이 끊길 때
    def disconnect(self, close_code):
        # Leave room group
        async_to_sync(self.channel_layer.group_discard)(
            self.room_group_name, self.channel_name
        )

    # 클라이언트가 메시지를 보낼 때 실행되어 데이터를 처리
    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]

        # Send message to room group
        async_to_sync(self.channel_layer.group_send)(
            self.room_group_name, {"type": "chat.message", "message": message}
        )

    # Receive message from room group
    def chat_message(self, event):
        message = event["message"]

        # Send message to WebSocket
        self.send(text_data=json.dumps({"message": message}))