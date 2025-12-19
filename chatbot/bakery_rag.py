import json
import os
from typing import List, Dict, Optional
import numpy as np
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.config import Settings
from openai import OpenAI
from tqdm import tqdm

# ----------------- 0. 설정 -----------------
DATA_FILE = "./chatbot/dessert.json"
VECTOR_DB_PATH = "./bakery_vectordb"
COLLECTION_NAME = "bakery_collection"

# 임베딩 모델 설정 (한국어 최적화)
EMBEDDING_MODEL = "jhgan/ko-sroberta-multitask"  # 한국어 임베딩 모델

# OpenAI API 설정 (필요시)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key-here")

# 검색 설정
TOP_K_RESULTS = 5  # 상위 K개 결과 반환
SIMILARITY_THRESHOLD = 0.5  # 유사도 임계값
# ------------------------------------------

class BakeryRAGSystem:
    """
    빵집 추천을 위한 RAG 시스템
    - 벡터 DB 구축 및 관리
    - 키워드 기반 유사도 검색
    - LLM 기반 자연어 추천
    """
    
    def __init__(self, embedding_model_name: str = EMBEDDING_MODEL):
        """
        RAG 시스템 초기화
        
        Args:
            embedding_model_name: 임베딩 모델 이름
        """
        print("🚀 빵집 RAG 시스템 초기화 중...")
        
        # 1. 임베딩 모델 로드
        print(f"📦 임베딩 모델 로드: {embedding_model_name}")
        self.embedding_model = SentenceTransformer(embedding_model_name)
        
        # 2. ChromaDB 클라이언트 초기화
        print(f"💾 벡터 DB 초기화: {VECTOR_DB_PATH}")
        self.client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
        
        # 3. 컬렉션 생성 또는 로드
        try:
            self.collection = self.client.get_collection(name=COLLECTION_NAME)
            print(f"✅ 기존 컬렉션 로드: {COLLECTION_NAME}")
        except:
            self.collection = self.client.create_collection(
                name=COLLECTION_NAME,
                metadata={"description": "빵집 정보 벡터 DB"}
            )
            print(f"✅ 새 컬렉션 생성: {COLLECTION_NAME}")
        
        print("✅ RAG 시스템 초기화 완료!\n")
    
    def create_bakery_text(self, bakery: Dict) -> str:
        """
        빵집 정보를 텍스트로 변환 (임베딩용)
        
        Args:
            bakery: 빵집 정보 딕셔너리
        
        Returns:
            임베딩용 텍스트
        """
        # 새 JSON 구조에 맞춘 필드명
        place_name = bakery.get('name', '알 수 없음')
        keywords = bakery.get('keywords', [])
        category = bakery.get('category', '베이커리')
        
        # 주소 정보 (도로명 우선, 없으면 지번)
        address = bakery.get('road_address', bakery.get('jibun_address', '주소 정보 없음'))
        
        # 구 정보
        district = bakery.get('district', '')
        
        # 연락처
        phone = bakery.get('phone', '')
        
        # 평점 정보 (rating이 dict인 경우)
        rating_info = bakery.get('rating', {})
        if isinstance(rating_info, dict):
            naver_rate = rating_info.get('naver_rate', '0')
            kakao_rate = rating_info.get('kakao_rate', '0')
            rating_text = f"네이버 {naver_rate}점, 카카오 {kakao_rate}점"
        else:
            rating_text = f"{rating_info}점"
        
        # 리뷰 키워드 정보
        review_keywords = bakery.get('review_keywords', [])
        review_kw_text = ", ".join([kw['keyword'].strip('"') for kw in review_keywords[:5]])
        
        # 대기 시간 정보 (waiting_prediction)
        waiting_info = bakery.get('waiting_prediction', {})
        wait_text = ""
        if waiting_info:
            overall_stats = waiting_info.get('overall_stats', {})
            avg_wait = overall_stats.get('average_minutes', 0)
            if avg_wait > 0:
                wait_text = f"평균 대기 시간: {avg_wait}분"
        
        # 임베딩용 텍스트 생성 (키워드와 특징 중심)
        text_parts = [
            f"빵집 이름: {place_name}",
            f"카테고리: {category}",
        ]
        
        if district:
            text_parts.append(f"위치: 대전 {district}")
        
        if keywords:
            text_parts.append(f"특징 키워드: {', '.join(keywords)}")
        
        if review_kw_text:
            text_parts.append(f"고객 평가: {review_kw_text}")
        
        if wait_text:
            text_parts.append(wait_text)
        
        text_parts.extend([
            f"주소: {address}",
            f"평점: {rating_text}"
        ])
        
        return "\n".join(text_parts)
    
    def create_bakery_metadata(self, bakery: Dict) -> Dict:
        """
        빵집 정보를 메타데이터로 변환 (검색 결과용)
        
        Args:
            bakery: 빵집 정보 딕셔너리
        
        Returns:
            메타데이터 딕셔너리
        """
        # 새 JSON 구조에 맞춘 필드명
        place_name = bakery.get('name', '알 수 없음')
        address = bakery.get('road_address', bakery.get('jibun_address', '주소 정보 없음'))
        phone = bakery.get('phone', '전화번호 없음')
        category = bakery.get('category', '베이커리')
        district = bakery.get('district', '')
        url = bakery.get('url', '')
        
        # 평점 정보
        rating_info = bakery.get('rating', {})
        if isinstance(rating_info, dict):
            naver_rate = rating_info.get('naver_rate', '0')
            kakao_rate = rating_info.get('kakao_rate', '0')
            rating_str = f"네이버 {naver_rate}, 카카오 {kakao_rate}"
        else:
            rating_str = str(rating_info)
        
        # 키워드
        keywords = bakery.get('keywords', [])
        keywords_str = ', '.join(keywords) if keywords else '정보 없음'
        
        # 리뷰 키워드 (상위 3개)
        review_keywords = bakery.get('review_keywords', [])
        review_kw_str = ', '.join([kw['keyword'].strip('"') for kw in review_keywords[:3]])
        
        # 영업시간 정보 (business_hours_raw에서 추출)
        business_hours = bakery.get('business_hours_raw', '영업시간 정보 없음')
        
        # 대기 시간 정보
        waiting_info = bakery.get('waiting_prediction', {})
        avg_wait = "정보 없음"
        if waiting_info:
            overall_stats = waiting_info.get('overall_stats', {})
            avg_minutes = overall_stats.get('average_minutes', 0)
            if avg_minutes > 0:
                avg_wait = f"{avg_minutes}분"
            else:
                avg_wait = "대기 없음"
        
        return {
            'place_name': place_name,
            'address': address,
            'phone': phone,
            'rating': rating_str,
            'keywords': keywords_str,
            'review_keywords': review_kw_str,
            'category': category,
            'district': district,
            'url': url,
            'business_hours': business_hours,
            'avg_waiting_time': avg_wait
        }
    
    def load_and_index_bakeries(self, data_file: str = DATA_FILE, force_reindex: bool = False):
        """
        빵집 데이터를 로드하여 벡터 DB에 인덱싱
        
        Args:
            data_file: 빵집 데이터 JSON 파일 경로
            force_reindex: 기존 데이터 삭제 후 재인덱싱 여부
        """
        print(f"\n{'='*60}")
        print("📊 빵집 데이터 인덱싱 시작")
        print(f"{'='*60}\n")
        
        # 기존 데이터 확인
        existing_count = self.collection.count()
        
        if existing_count > 0 and not force_reindex:
            print(f"ℹ️ 이미 {existing_count}개의 빵집이 인덱싱되어 있습니다.")
            print("   재인덱싱하려면 force_reindex=True로 설정하세요.\n")
            return
        
        if force_reindex and existing_count > 0:
            print(f"🗑️ 기존 데이터 삭제 중... ({existing_count}개)")
            self.client.delete_collection(name=COLLECTION_NAME)
            self.collection = self.client.create_collection(
                name=COLLECTION_NAME,
                metadata={"description": "빵집 정보 벡터 DB"}
            )
        
        # 1. 데이터 로드
        if not os.path.exists(data_file):
            print(f"❌ 데이터 파일을 찾을 수 없습니다: {data_file}")
            return
        
        with open(data_file, 'r', encoding='utf-8') as f:
            bakeries = json.load(f)
        
        print(f"✅ 데이터 로드 완료: {len(bakeries)}개 빵집\n")
        
        # 2. 임베딩 및 인덱싱
        print("🔄 임베딩 및 벡터 DB 저장 중...\n")
        
        documents = []
        metadatas = []
        ids = []
        
        for idx, bakery in enumerate(tqdm(bakeries, desc="임베딩 생성")):
            # 임베딩용 텍스트 생성
            text = self.create_bakery_text(bakery)
            documents.append(text)
            
            # 메타데이터 생성
            metadata = self.create_bakery_metadata(bakery)
            metadatas.append(metadata)
            
            # ID 생성
            ids.append(f"bakery_{idx}")
        
        # 배치로 임베딩 생성 (속도 향상)
        print("\n🎯 벡터 임베딩 생성 중...")
        embeddings = self.embedding_model.encode(
            documents, 
            show_progress_bar=True,
            batch_size=32
        )
        
        # ChromaDB에 저장
        print("\n💾 벡터 DB에 저장 중...")
        self.collection.add(
            embeddings=embeddings.tolist(),
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        print(f"\n{'='*60}")
        print(f"✅ 인덱싱 완료: {len(bakeries)}개 빵집")
        print(f"{'='*60}\n")
    
    def extract_keywords_from_query(self, query: str) -> List[str]:
        """
        사용자 질문에서 키워드 추출 (간단한 방식)
        
        Args:
            query: 사용자 질문
        
        Returns:
            추출된 키워드 리스트
        """
        # 빵집 관련 키워드 사전
        keyword_dict = {
            # 맛 관련
            '달콤': '달콤한', '달달': '달콤한', '단': '달콤한', '달아': '달콤한',
            '짭짤': '짭짤한', '짠': '짭짤한',
            '고소': '고소한', '구수': '고소한',
            '바삭': '바삭한', '바삭바삭': '바삭한', '바삭바삭한': '바삭한',
            '부드러': '부드러운', '촉촉': '촉촉한',
            '쫄깃': '쫄깃한', '쫀득': '쫀득한',
            '새콤': '새콤한', '상큼': '상큼한',
            
            # 빵 종류
            '크로와상': '크로와상', '크루아상': '크로와상', '크와상': '크로와상',
            '바게트': '바게트', '빵': '식빵', '식빵': '식빵',
            '베이글': '베이글', '도넛': '도넛',
            '타르트': '타르트', '에그타르트': '에그타르트', '에그타트': '에그타르트',
            '마카롱': '마카롱', '스콘': '스콘',
            '카스테라': '카스테라', '페스츄리': '페스츄리',
            '소금빵': '소금빵', '치아바타': '치아바타',
            
            # 특징
            '신선': '신선한', '갓구운': '갓 구운', '갓 구운': '갓 구운',
            '수제': '수제', '시그니처': '시그니처',
            '건강': '건강빵', '유기농': '유기농',
            
            # 지역 (대전)
            '유성': '유성구', '서구': '서구', '동구': '동구', '중구': '중구', '대덕': '대덕구',
        }
        
        extracted = set()
        query_lower = query.lower()
        
        for key, standard_keyword in keyword_dict.items():
            if key in query_lower:
                extracted.add(standard_keyword)
        
        return list(extracted)
    
    def search(self, query: str, top_k: int = TOP_K_RESULTS) -> List[Dict]:
        """
        자연어 질문으로 빵집 검색
        
        Args:
            query: 사용자 질문 (예: "바삭한 크로와상이 맛있는 빵집 추천해줘")
            top_k: 반환할 상위 결과 수
        
        Returns:
            검색 결과 리스트
        """
        print(f"\n🔍 검색 쿼리: {query}")
        
        # 1. 키워드 추출
        keywords = self.extract_keywords_from_query(query)
        if keywords:
            print(f"📌 추출된 키워드: {', '.join(keywords)}")
            # 키워드를 쿼리에 추가하여 검색 정확도 향상
            enhanced_query = f"{query} {' '.join(keywords)}"
        else:
            enhanced_query = query
        
        # 2. 쿼리 임베딩
        query_embedding = self.embedding_model.encode([enhanced_query])[0]
        
        # 3. 유사도 검색
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            include=['documents', 'metadatas', 'distances']
        )
        
        # 4. 결과 포맷팅 (새 필드 추가)
        formatted_results = []
        if results['ids'] and len(results['ids'][0]) > 0:
            for i in range(len(results['ids'][0])):
                similarity = 1 - results['distances'][0][i]  # 거리를 유사도로 변환
                
                metadata = results['metadatas'][0][i]
                result = {
                    'place_name': metadata['place_name'],
                    'address': metadata['address'],
                    'phone': metadata['phone'],
                    'rating': metadata['rating'],
                    'keywords': metadata['keywords'],
                    'review_keywords': metadata.get('review_keywords', ''),
                    'district': metadata.get('district', ''),
                    'url': metadata.get('url', ''),
                    'business_hours': metadata.get('business_hours', '영업시간 정보 없음'),
                    'avg_waiting_time': metadata.get('avg_waiting_time', '정보 없음'),
                    'similarity_score': round(similarity, 3),
                    'document': results['documents'][0][i]
                }
                formatted_results.append(result)
        
        return formatted_results
    
    def search_and_display(self, query: str, top_k: int = TOP_K_RESULTS):
        """
        검색 결과를 보기 좋게 출력
        
        Args:
            query: 사용자 질문
            top_k: 반환할 상위 결과 수
        """
        results = self.search(query, top_k)
        
        if not results:
            print("\n⚠️ 검색 결과가 없습니다.")
            return
        
        print(f"\n{'='*60}")
        print(f"✨ 추천 빵집 Top {len(results)}")
        print(f"{'='*60}\n")
        
        for i, result in enumerate(results, 1):
            print(f"🥖 {i}. {result['place_name']}")
            print(f"   ⭐ 평점: {result['rating']}")
            
            if result['keywords'] and result['keywords'] != '정보 없음':
                print(f"   🏷️ 특징: {result['keywords']}")
            
            if result.get('review_keywords'):
                print(f"   💬 고객평: {result['review_keywords']}")
            
            if result.get('district'):
                print(f"   📍 위치: 대전 {result['district']}")
            
            print(f"   🏠 주소: {result['address']}")
            
            if result['phone'] and result['phone'] != '전화번호 없음':
                print(f"   📞 전화: {result['phone']}")
            
            # 대기 시간 정보 표시
            if result.get('avg_waiting_time') and result['avg_waiting_time'] != '정보 없음':
                print(f"   ⏰ 평균 대기: {result['avg_waiting_time']}")
            
            print(f"   🎯 유사도: {result['similarity_score']}")
            
            if result.get('url'):
                print(f"   🗺️ 지도: {result['url']}")
            
            print()
    
    def generate_llm_response(self, query: str, search_results: List[Dict], 
                             use_openai: bool = False) -> str:
        """
        LLM을 사용하여 자연스러운 추천 답변 생성
        
        Args:
            query: 사용자 질문
            search_results: 검색 결과
            use_openai: OpenAI API 사용 여부
        
        Returns:
            LLM 생성 답변
        """
        if not search_results:
            return "죄송합니다. 해당 조건에 맞는 빵집을 찾지 못했습니다. 다른 키워드로 검색해보시겠어요?"
        
        # 검색 결과를 텍스트로 변환
        context = "\n\n".join([
            f"빵집 {i+1}: {result['place_name']}\n"
            f"특징: {result['keywords']}\n"
            f"평점: {result['rating']}\n"
            f"위치: {result.get('district', '')} {result['address']}\n"
            f"전화: {result['phone']}\n"
            f"평균 대기: {result.get('avg_waiting_time', '정보 없음')}"
            for i, result in enumerate(search_results[:3])  # 상위 3개만 사용
        ])
        
        if use_openai and OPENAI_API_KEY != "your-api-key-here":
            # GMS API 사용
            
            # GMS 프록시 엔드포인트 설정
            GMS_BASE_URL = "https://gms.ssafy.io/gmsapi/api.openai.com/v1"
            
            # OpenAI 클라이언트 초기화 시 base_url과 api_key 설정
            client = OpenAI(
                api_key=OPENAI_API_KEY,  # 환경변수에 저장된 GMS_KEY 사용
                base_url=GMS_BASE_URL,   # GMS 프록시 주소 설정
            )
            
            # 모델은 gpt-4.1-nano로 유지 (GMS에서 해당 모델을 지원한다고 가정)
            MODEL_NAME = "gpt-4.1-nano"
            
            prompt = f"""당신은 친절한 빵집 추천 전문가입니다. 
사용자의 질문에 대해 검색된 빵집 정보를 바탕으로 자연스럽고 친근한 답변을 작성해주세요.

사용자 질문: {query}

검색된 빵집 정보:
{context}

위 정보를 바탕으로 사용자에게 빵집을 추천하는 답변을 작성해주세요. 
각 빵집의 특징과 장점을 구체적으로 설명해주세요."""
            prompt = prompt.encode('utf-8', 'ignore').decode('utf-8')

            try:
                print("Debug checkpoint 1")
                response = client.chat.completions.create(
                    model="gpt-4.1-nano",
                    messages=[
                        {"role": "system", "content": "당신은 친절한 빵집 추천 전문가입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=500
                )
                print("Debug checkpoint 2")
                return response.choices[0].message.content
            except Exception as e:
                print(f"⚠️ OpenAI API 오류: {e}")
                # 폴백: 템플릿 기반 응답
        
        # 템플릿 기반 응답 (OpenAI 미사용 시)
        response = f"'{query}'에 대한 추천 빵집을 찾았습니다!\n\n"
        
        for i, result in enumerate(search_results[:3], 1):
            response += f"{i}. **{result['place_name']}** ({result['rating']})\n"
            if result['keywords'] and result['keywords'] != '정보 없음':
                response += f"   - 특징: {result['keywords']}\n"
            if result.get('district'):
                response += f"   - 위치: 대전 {result['district']}\n"
            response += f"   - 주소: {result['address']}\n"
            if result.get('avg_waiting_time') and result['avg_waiting_time'] != '정보 없음':
                response += f"   - 평균 대기: {result['avg_waiting_time']}\n"
            if i < len(search_results[:3]):
                response += "\n"
        
        response += "\n위 빵집들을 추천드립니다! 더 자세한 정보가 필요하시면 말씀해주세요. 😊"
        
        return response
    
    def chat(self, query: str, use_llm: bool = True, use_openai: bool = False):
        """
        대화형 빵집 추천 (RAG 전체 파이프라인)
        
        Args:
            query: 사용자 질문
            use_llm: LLM 답변 생성 여부
            use_openai: OpenAI API 사용 여부
        """
        # 1. 검색
        results = self.search(query, top_k=TOP_K_RESULTS)
        
        # 2. 검색 결과 출력
        self.search_and_display(query, top_k=TOP_K_RESULTS)
        
        # 3. LLM 답변 생성 (선택)
        if use_llm:
            print(f"{'='*60}")
            print("🤖 AI 추천 답변")
            print(f"{'='*60}\n")
            response = self.generate_llm_response(query, results, use_openai)
            print(response)
            print()

# ----------------- 메인 실행 함수 -----------------

def main():
    """
    빵집 RAG 시스템 메인 실행
    """
    print(f"\n{'='*60}")
    print("🍞 빵집 추천 RAG 시스템")
    print(f"{'='*60}\n")
    
    # 1. RAG 시스템 초기화
    rag = BakeryRAGSystem()
    
    # 2. 데이터 인덱싱 (최초 1회 실행)
    rag.load_and_index_bakeries(force_reindex=False)
    
    # 3. 예시 검색
    print("\n" + "="*60)
    print("💡 사용 예시")
    print("="*60 + "\n")
    
    example_queries = [
        "바삭한 크로와상이 맛있는 빵집 추천해줘",
        "달콤하고 부드러운 빵을 파는 곳 찾아줘",
        "시그니처 메뉴가 있는 빵집 어디 있어?",
    ]
    
    for query in example_queries:
        rag.chat(query, use_llm=True, use_openai=False)
        print("\n" + "-"*60 + "\n")
    
    # 4. 대화형 모드 (선택)
    print("\n💬 대화형 모드를 시작하려면 'interactive' 모드로 실행하세요.")
    print("   예: python bakery_rag.py interactive")

def interactive_mode():
    """
    대화형 검색 모드
    """
    print(f"\n{'='*60}")
    print("💬 대화형 빵집 추천 시스템")
    print(f"{'='*60}\n")
    print("💡 사용법: 원하는 빵이나 특징을 자유롭게 입력하세요.")
    print("   (종료하려면 'quit' 또는 'exit' 입력)\n")
    
    rag = BakeryRAGSystem()
    
    # 데이터 로드 확인
    if rag.collection.count() == 0:
        print("⚠️ 벡터 DB가 비어있습니다. 데이터를 먼저 인덱싱합니다...\n")
        rag.load_and_index_bakeries()
    
    while True:
        query = input("\n🤔 질문: ").strip()
        
        if query.lower() in ['quit', 'exit', '종료', 'q']:
            print("\n👋 빵집 추천 시스템을 종료합니다. 맛있는 빵 드세요!")
            break
        
        if not query:
            continue
        
        rag.chat(query, use_llm=True, use_openai=False)

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'interactive':
        interactive_mode()
    else:
        main()