# tripsnap

1. 빵집 추천 프로젝트

2. 민경 백엔드 구현
- 로그인 구현 (~25.11.25)
- 필수 구현 : 카카오 자동 로그인 필수 연동

번호 | 요구사항명 | 요구사항 상세 | 기술 스택 | 우선순위
|--|--|--|--|--|
**F500** | **사용자 및 인증 관리** | |||
F501  | 사용자 등록 API| 이메일/비밀번호를 받아 사용자 정보를 DB에 저장하고, 인증 토큰을 발행한다. |Flask/Django | 필수 |
F502 | 로그인 API | 이메일/비밀번호 검증 후, 유효한 인증 토큰을 발행하여 FE에 전달한다. | Flask/Django | 필수|
F503 | 프로필 정보 관리 API | 사용자 프로필 정보(닉네임, 사진 URL, 비밀번호)의 조회 및 수정 요청을 처리한다. | Flask/Django | 필수 |
F504 | 토큰 기반 인증 미들웨어 | 모든 인증이 필요한 API 요청에 대해 토큰의 유효성을 검사하는 미들웨어를 적용한다. | Flask/Django |필수| 


---

# 📌 Branch 전략

## 브랜치 구조
- **main**  
  - 실제 서비스에 배포되는 안정적인 코드만 모아둡니다.  
- **develop**  
  - 팀원들이 작업한 기능(feature)을 합치는 통합 브랜치입니다.  
  - main에 바로 머지하지 않고, 먼저 develop에서 테스트/통합 후 안정화합니다.  
- **feature/\***  
  - 개인별 또는 기능별 작업 브랜치입니다.  
  - 예: `feature/yeonjae`, `feature/minkyung`  

---

## 브랜치 생성 및 사용법
```bash
# develop 브랜치에서 새로운 기능 브랜치 생성
git checkout develop
git pull origin develop
git checkout -b feature/yeonjae

# 작업 후 커밋 & 푸시
git add .
git commit -m "feat: 채팅방 생성 기능 추가"
git push origin feature/yeonjae
```

- 작업이 끝나면 **feature → develop**으로 Pull Request(PR)을 생성합니다.  
- 코드 리뷰 후 머지합니다.  
- 일정 주기 또는 배포 시점에 **develop → main**으로 머지합니다.  

---

## 브랜치 삭제 규칙
- 기능 구현이 끝나고 **develop에 머지된 feature 브랜치는 삭제**합니다.  
- 삭제 전에는 반드시 PR 리뷰와 머지가 완료되어야 합니다.  
- 삭제 방법:
  ```bash
  # 로컬 브랜치 삭제
  git branch -d feature/yeonjae

  # 원격 브랜치 삭제
  git push origin --delete feature/yeonjae
  ```

---

# 📝 Commit Convention

## 커밋 타입
| 타입 | 설명 | 예시 |
|------|------|------|
| **feat** | 새로운 기능 추가 | `feat: 회원가입 API 추가` |
| **fix** | 버그 수정 | `fix: 로그인 오류 수정` |
| **docs** | 문서 수정 | `docs: 브랜치 전략 문서 추가` |
| **style** | 코드 스타일 변경 | `style: 불필요한 공백 제거` |
| **refactor** | 코드 리팩토링 | `refactor: User 모델 구조 개선` |
| **test** | 테스트 코드 추가/수정 | `test: 회원가입 API 단위 테스트 추가` |
| **chore** | 빌드, 패키지, 설정 변경 | `chore: requirements.txt 업데이트` |

---

## 작성 예시
```bash
# 한 줄 요약만 있는 경우
git commit -m "feat: 회원가입 API 추가"

# 본문 설명이 필요한 경우
git commit -m "fix: 로그인 오류 수정
- 비밀번호 검증 로직 수정
- 잘못된 에러 메시지 반환 문제 해결"
```

---

## 팀 규칙
- main에는 직접 커밋하지 않습니다.  
- 항상 develop에서 브랜치를 따서 작업합니다.  
- 커밋은 작은 단위로 자주 합니다.  
- 커밋 메시지는 명확하게 작성해, 로그만 봐도 어떤 작업인지 알 수 있도록 합니다.  

