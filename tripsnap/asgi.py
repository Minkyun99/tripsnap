"""
ASGI config for tripsnap project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from channels.routing import ProtocolTypeRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tripsnap.settings')

# ASGI 설정: HTTP와 WebSocket을 처리할 수 있도록 라우팅 
application = ProtocolTypeRouter({  # ProtocolTypeRouter: 연결의 타입을 검사. 웹소켓이면  AuthMiddlewareStack으로 넘겨준다.
    "http": get_asgi_application(),
    # "websocket": 나중에 추가 가능
})
