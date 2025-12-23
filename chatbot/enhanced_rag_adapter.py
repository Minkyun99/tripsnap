"""
Enhanced RAG Adapter

RAG 시스템의 응답을 Django 모델과 연결하고, 
LLM 응답을 파싱하여 실제 DB 데이터로 enrichment하는 어댑터.

책임:
1. LLM 응답에서 빵집 이름 파싱
2. 파싱된 이름으로 DB에서 빵집 찾기 (퍼지 매칭)
3. 추천 응답 여부 판별
4. RAG 응답을 Django 모델 데이터로 변환
"""

import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class EnhancedRAGAdapter:
    """
    RAG 시스템과 Django 모델 사이의 어댑터.
    LLM 응답을 파싱하고 DB 데이터로 enrichment합니다.
    """
    
    def __init__(self, bakery_model):
        """
        Args:
            bakery_model: Django Bakery 모델 클래스
        """
        self.Bakery = bakery_model
    
    # ==========================================
    # 1. 추천 응답 판별
    # ==========================================
    
    def is_recommendation_response(self, llm_response: str) -> bool:
        """
        LLM 응답이 실제로 빵집을 추천하는 내용인지 확인합니다.
        
        추천 응답으로 간주되는 경우:
        - "추천", "코스", "매장" 등의 키워드 포함
        - "1.", "2.", "3." 같은 리스트 형식
        - 구체적인 빵집 이름이나 주소 언급
        
        추천 응답이 아닌 경우:
        - "찾지 못했다", "없습니다" 등 실패 메시지
        - "종류", "차이", "역사", "만드는 법" 등 지식 설명
        
        Args:
            llm_response: LLM의 응답 텍스트
            
        Returns:
            bool: 빵집 추천 응답이면 True, 아니면 False
        """
        if not llm_response:
            return False
        
        # 1. 실패 메시지 키워드 체크 (최우선)
        failure_keywords = [
            "찾지 못했습니다",
            "찾을 수 없습니다",
            "조건에 맞는 빵집이 없",
            "해당하는 빵집이 없",
            "추천할 빵집이 없",
            "적합한 빵집이 없",
            "검색 결과가 없",
        ]
        
        for keyword in failure_keywords:
            if keyword in llm_response:
                logger.info(f"🚫 [NOT_RECOMMENDATION] 실패 키워드 '{keyword}' 감지")
                return False
        
        # 2. 지식/설명 모드 키워드 체크
        knowledge_keywords = [
            "종류가 있",
            "종류는",
            "차이점",
            "차이가",
            "역사",
            "기원",
            "유래",
            "만드는 법",
            "만드는 방법",
            "레시피",
            "특징은",
            "정의는",
        ]
        
        knowledge_count = sum(1 for kw in knowledge_keywords if kw in llm_response)
        
        if knowledge_count >= 2:
            logger.info(f"🚫 [NOT_RECOMMENDATION] 지식 모드로 판단 (키워드 {knowledge_count}개)")
            return False
        
        # 3. 추천 키워드 체크
        recommendation_keywords = [
            "추천드립니다",
            "추천드려요",
            "추천해드립니다",
            "추천합니다",
            "코스",
            "방문하시면",
            "가보시면",
            "매장",
            "빵집",
            "베이커리",
            "이동 시간",
            "영업시간",
            "주소",
            "전화",
        ]
        
        recommendation_count = sum(1 for kw in recommendation_keywords if kw in llm_response)
        
        # 4. 리스트 형식 체크
        has_numbered_list = bool(re.search(r'[1-9]\.|①|②|③|④|⑤', llm_response))
        
        # 5. 판단 로직
        is_recommendation = False
        
        if recommendation_count >= 2:
            is_recommendation = True
            logger.info(f"✅ [IS_RECOMMENDATION] 추천 키워드 {recommendation_count}개 감지")
        elif has_numbered_list and recommendation_count >= 1:
            is_recommendation = True
            logger.info(f"✅ [IS_RECOMMENDATION] 번호 리스트 + 추천 키워드 감지")
        else:
            logger.info(f"🚫 [NOT_RECOMMENDATION] 추천 응답 조건 미충족 (키워드: {recommendation_count}, 리스트: {has_numbered_list})")
        
        return is_recommendation
    
    # ==========================================
    # 2. LLM 응답 파싱
    # ==========================================
    
    def extract_bakery_names_from_llm_response(self, llm_text: str) -> List[str]:
        """
        LLM 응답에서 추천된 빵집 이름을 파싱합니다.
        
        예시 패턴:
        - "🥖 추천 1: 더 베이커"
        - "🥖 추천 2: 폴레폴레 유성본점"
        
        Args:
            llm_text: LLM 응답 텍스트
            
        Returns:
            List[str]: 파싱된 빵집 이름 리스트
        """
        # 패턴 1: "🥖 추천 N: 빵집이름" 형식
        pattern1 = r'🥖\s*추천\s*\d+\s*:\s*([^\n]+)'
        matches1 = re.findall(pattern1, llm_text)
        
        # 패턴 2: "N. 빵집이름" 형식
        pattern2 = r'^\s*\d+\.\s*([^\n:]+?)(?:\n|:|\(|$)'
        matches2 = re.findall(pattern2, llm_text, re.MULTILINE)
        
        def normalize_bakery_name(name):
            """빵집 이름 정규화"""
            if not name:
                return ""
            
            # 앞뒤 공백 제거
            name = name.strip()
            
            # "===" 같은 구분선 제거
            name = re.split(r'[=]{2,}', name)[0].strip()
            
            # 연속 공백 정리
            name = re.sub(r'\s+', ' ', name)
            
            # 너무 긴/짧은 이름 제외
            if len(name) > 50 or len(name) < 2:
                return ""
            
            # 숫자만인 이름 제외
            if name.isdigit():
                return ""
            
            return name
        
        # 두 패턴 결과 합치기
        bakery_names = []
        for match in matches1:
            name = normalize_bakery_name(match)
            if name:
                bakery_names.append(name)
        
        # pattern1에서 충분히 찾았으면 pattern2는 스킵
        if len(bakery_names) >= 3:
            logger.info(f"🔍 [PARSE] LLM 응답에서 {len(bakery_names)}개 빵집 이름 파싱 (패턴1)")
            for idx, name in enumerate(bakery_names, 1):
                logger.info(f"  [{idx}] '{name}'")
            return bakery_names
        
        for match in matches2:
            name = normalize_bakery_name(match)
            if name and name not in bakery_names:
                bakery_names.append(name)
        
        logger.info(f"🔍 [PARSE] LLM 응답에서 {len(bakery_names)}개 빵집 이름 파싱")
        for idx, name in enumerate(bakery_names, 1):
            logger.info(f"  [{idx}] '{name}'")
        
        return bakery_names
    
    # ==========================================
    # 3. DB 퍼지 매칭
    # ==========================================
    
    def find_bakery_fuzzy(self, bakery_name: str) -> Optional[Any]:
        """
        퍼지 매칭을 통해 DB에서 빵집을 찾습니다.
        
        매칭 전략:
        1. 정확한 이름으로 검색
        2. 정규화된 이름으로 검색 (공백 무시)
        3. 부분 매칭 검색
        
        Args:
            bakery_name: 찾을 빵집 이름
            
        Returns:
            Bakery 모델 인스턴스 또는 None
        """
        if not bakery_name:
            return None
        
        # 1. 정확한 이름으로 검색
        try:
            return self.Bakery.objects.get(name=bakery_name)
        except self.Bakery.DoesNotExist:
            pass
        except self.Bakery.MultipleObjectsReturned:
            return self.Bakery.objects.filter(name=bakery_name).first()
        
        # 2. 정규화된 이름으로 검색
        normalized_search = self._normalize_for_matching(bakery_name)
        if normalized_search:
            for bakery in self.Bakery.objects.all():
                if self._normalize_for_matching(bakery.name) == normalized_search:
                    return bakery
        
        # 3. 부분 매칭
        if len(bakery_name) >= 3:
            try:
                clean_name = bakery_name.replace(' ', '')
                candidates = self.Bakery.objects.filter(name__icontains=clean_name)
                if candidates.exists():
                    return candidates.first()
            except Exception:
                pass
        
        return None
    
    def _normalize_for_matching(self, name: str) -> str:
        """매칭용 이름 정규화 (공백, 괄호, 특수문자 제거)"""
        if not name:
            return ""
        
        # 괄호 제거
        name = re.sub(r'\([^)]*\)', '', name)
        name = re.sub(r'\[[^\]]*\]', '', name)
        
        # 공백 제거
        name = name.replace(' ', '')
        
        # 특수문자 제거 (한글, 영문, 숫자만)
        name = re.sub(r'[^가-힣a-zA-Z0-9]', '', name)
        
        return name.strip()
    
    # ==========================================
    # 4. 메인 enrichment 메서드
    # ==========================================
    
    def answer_query_with_enrichment(
        self, 
        query: str, 
        use_llm: bool = True
    ) -> Dict[str, Any]:
        """
        RAG 시스템을 호출하고 응답을 DB 데이터로 enrichment합니다.
        
        처리 순서:
        1. RAG 시스템 호출 (벡터 검색 + LLM)
        2. LLM 응답이 추천인지 판별
        3. 추천이면 빵집 이름 파싱
        4. DB에서 빵집 찾기 (퍼지 매칭)
        5. DB 정보로 enrichment
        
        Args:
            query: 사용자 질의
            use_llm: LLM 사용 여부
            
        Returns:
            {
                'llm_response': str,
                'results': List[Dict] | None  # 추천일 때만 포함
            }
        """
        # RAGWrapper import (지연 import로 순환 참조 방지)
        from .rag_wrapper import RAGWrapper
        
        # 1. RAG 호출
        rag_result = RAGWrapper.chat(message=query, use_llm=use_llm)
        llm_response = rag_result.get('llm_response', '')
        
        # 2. 추천 응답인지 판별
        if not self.is_recommendation_response(llm_response):
            logger.info("🚫 [NOT_RECOMMENDATION] results를 포함하지 않습니다")
            return {
                'llm_response': llm_response,
                # results 키 없음!
            }
        
        logger.info("✅ [IS_RECOMMENDATION] results 처리 시작")
        
        # 3. 빵집 이름 파싱
        bakery_names = self.extract_bakery_names_from_llm_response(llm_response)
        
        enriched_results = []
        
        if bakery_names:
            # 4. LLM이 추천한 빵집을 DB에서 찾기
            logger.info(f"🔍 [DB_MATCH] LLM이 추천한 {len(bakery_names)}개 빵집을 DB에서 찾습니다")
            
            for idx, bakery_name in enumerate(bakery_names, 1):
                bakery = self.find_bakery_fuzzy(bakery_name)
                
                if bakery:
                    logger.info(f"✅ [DB_MATCH] [{idx}] 성공 - ID: {bakery.id}, 이름: {bakery.name}")
                    enriched_results.append({
                        'id': bakery.id,
                        'name': bakery.name,
                        'place_name': bakery.name,
                        'district': bakery.district,
                        'address': bakery.road_address or bakery.jibun_address,
                        'rate': bakery.rate,
                        'phone': bakery.phone,
                        'url': bakery.url,
                    })
                else:
                    logger.warning(f"⚠️ [DB_MATCH] [{idx}] DB에 없는 빵집: {bakery_name}")
                    # DB에 없으면 이름만 포함
                    enriched_results.append({
                        'id': None,
                        'name': bakery_name,
                        'place_name': bakery_name,
                        'district': '',
                        'address': '',
                        'rate': '',
                        'phone': '',
                        'url': '',
                    })
        else:
            # 5. Fallback: RAG results 사용
            logger.warning("⚠️ [PARSE] LLM 응답에서 빵집 이름 파싱 실패 - RAG results로 fallback")
            rag_results = rag_result.get('results', [])
            
            for idx, rag_result_item in enumerate(rag_results):
                bakery_name = rag_result_item.get('place_name') or rag_result_item.get('name', '')
                if not bakery_name:
                    continue
                
                bakery = self.find_bakery_fuzzy(bakery_name)
                
                if bakery:
                    enriched_results.append({
                        'id': bakery.id,
                        'name': bakery.name,
                        'place_name': bakery.name,
                        'district': bakery.district,
                        'address': bakery.road_address or bakery.jibun_address,
                        'rate': bakery.rate,
                        'phone': bakery.phone,
                        'url': bakery.url,
                    })
                else:
                    enriched_results.append({
                        'id': None,
                        'name': bakery_name,
                        'place_name': bakery_name,
                        'district': rag_result_item.get('district', ''),
                        'address': rag_result_item.get('address', ''),
                        'rate': rag_result_item.get('rating', ''),
                        'phone': rag_result_item.get('phone', ''),
                        'url': rag_result_item.get('url', ''),
                    })
        
        logger.info(f"📊 [ENRICHMENT] 최종 결과: {len(enriched_results)}개 빵집")
        
        return {
            'llm_response': llm_response,
            'results': enriched_results if enriched_results else None,
        }