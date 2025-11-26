# chatbot/consumers.py
# consumers란? Django의 View의 비동기 버전. 비동기 통신(WebSocket, long-polling 등)을 처리하기 위해 만들어진 구조.
# Django의 views.py는 HTTP 요청을 처리하는 거라면, Channel에서는 Websocket 연결이나 다른 프로토콜 이벤트를 처리하는 단위가 Consumer이다.
# 클라-서버 간 지속적인 연결 상태에서 발생하는 이벤트를 관리한다.

import json

from channels.generic.websocket import WebsocketConsumer


class ChatConsumer(WebsocketConsumer):
    # 클라이언트가 WebSocket을 통해 서버에 연결
    def connect(self):
        self.accept()

    # 연결이 끊길 때
    def disconnect(self, close_code):
        pass

    # 클라이언트가 메시지를 보낼 때 실행되어 데이터를 처리
    def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json["message"]

        # self.send(): 서버가 클라이언트로 메시지 보낼 때 사용. WebsocketConsumer에 구현되어 있다.
        self.send(text_data=json.dumps({"message": message}))