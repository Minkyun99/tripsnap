from django.apps import AppConfig
import sys

class ChatbotConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chatbot'

    # def ready(self):
    #     # ASGI 서버 실행 시에만 초기화
    #     if 'daphne' in sys.argv[0] or 'runserver' in sys.argv:
    #         from .rag_wrapper import RAGWrapper
    #         RAGWrapper.initialize()

    def ready(self):
        # importing model classes
        if 'runserver' in sys.argv:
            from .rag_wrapper import RAGWrapper
            RAGWrapper.initialize()