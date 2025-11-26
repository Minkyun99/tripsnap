"""
ASGI config for tripsnap project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tripsnap.settings')

django_asgi_app = get_asgi_application()

from chatbot.routing import websocket_urlpatterns

# ASGI 설정: HTTP와 WebSocket을 처리할 수 있도록 라우팅 
application = ProtocolTypeRouter({  # ProtocolTypeRouter: 연결의 타입을 검사. 웹소켓이면  AuthMiddlewareStack으로 넘겨준다.
    "http": django_asgi_app,
    "websocket": AllowedHostsOriginValidator(  # 기본 ASGI 구성을 chatbot.routing 모듈로 지정.
        AuthMiddlewareStack(URLRouter(websocket_urlpatterns))  # AuthMiddlewareStack: request 객체에 인증된 사용자를 채워줌, 그다음 연결이 URLRouter에 전달됨
    ),
})
