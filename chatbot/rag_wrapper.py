# chatbot/rag_wrapper.py
# RAGWrapper의 기능
# 1. 싱글톤 관리 - 처음 한 번만 인스턴스 생성, 초기화 및 제어
# 2. bakery_rag.py를 수정하지 않고 코드를 보호
# 3. 나중에 여기다가 캐싱, 로깅 등 추가 기능 추가하기 쉬움
# 4. 인터페이스 제공

from .bakery_rag import BakeryRAGSystem

class RAGWrapper:
    _instance = None  # 싱글톤 패턴 사용
    
    @classmethod
    def initialize(cls):
        if cls._instance is None:
            print("🚀 RAG 시스템 초기화 중...")
            cls._instance = BakeryRAGSystem()
            
            if cls._instance.collection.count() == 0:
                print("📊 빵집 데이터 인덱싱 중...")
                cls._instance.load_and_index_bakeries(force_reindex=False)
            
            print(f"✅ RAG 준비 완료: {cls._instance.collection.count()}개 빵집")
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls.initialize()
        return cls._instance
    
    @classmethod
    def search(cls, query: str, top_k: int = 5):
        rag = cls.get_instance()
        return rag.search(query, top_k=top_k)
    
    @classmethod
    def chat(cls, message: str, use_llm: bool = True):
        rag = cls.get_instance()
        results = rag.search(message, top_k=5)
        
        llm_response = None
        if use_llm:
            llm_response = rag.generate_llm_response(
                message, results, use_openai=True
            )
        
        return {
            'results': results,
            'llm_response': llm_response
        }