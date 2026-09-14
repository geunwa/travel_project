# 평가자용 체크리스트 & 시연 가이드

> 이 문서는 평가자가 **위에서 아래로 명령어를 복사-붙여넣기**하며
> 프로그램을 실시간으로 검증할 수 있도록 구성되어 있습니다.
> 예상 소요 시간: 약 5분

---

## 0. 사전 준비

### 0-1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 0-2. API 키 설정

프로젝트 루트에 `.env` 파일을 만들고 아래 두 키를 입력합니다.

```
GEMINI_API_KEY=발급받은_Gemini_API_키
KAKAO_REST_API_KEY=발급받은_카카오_REST_API_키
```

**API 키 발급 링크**
- Gemini API 키: https://aistudio.google.com/app/apikey
- Kakao REST API 키: https://developers.kakao.com/console/app
  - 앱 생성 → [앱 설정 > 앱 키] → **REST API 키** 사용

---

## 1. CLI 실행 시연 (핵심)

### 1-1. 기본 실행

```bash
python main.py --date "2027-03-01"
```

**확인 포인트**
- [ ] 콘솔에 `[1/3] → [2/3] → [3/3]` 단계가 순서대로 출력됨
- [ ] `results/travel_2027-03-01.json` 생성됨
- [ ] `results/travel_2027-03-01.md` 생성됨

### 1-2. 생성된 결과 즉시 확인

```bash
# JSON 결과 확인 (한글이 깨지면 인코딩 옵션 필요 - 아래 주의 참고)
python -c "print(open('results/travel_2027-03-01.json', encoding='utf-8').read())"
```

```bash
# Markdown 리포트 확인
python -c "print(open('results/travel_2027-03-01.md', encoding='utf-8').read())"
```

> ⚠️ **한글 깨짐 주의**
> PowerShell에서 `cat` 으로 열면 한글이 깨져 보일 수 있으나,
> **이는 터미널 출력 인코딩 문제이며 파일은 UTF-8로 정상 저장되어 있습니다.**
> PowerShell에서 확인하려면:
> ```powershell
> Get-Content results/travel_2027-03-01.json -Encoding UTF8
> ```

**확인 포인트**
- [ ] `recommended_cities` 에 2~3개 도시가 축약형(예: "제주", "광양", "부산")으로 들어있음
- [ ] `restaurants_by_city` 의 키가 `recommended_cities` 와 일치함
- [ ] 각 맛집에 상호명/주소/카테고리/전화/URL/좌표(x,y)가 있음

---

## 2. 필수 요구사항 매핑

| 요구사항 | 확인 방법 | 체크 |
| --- | --- | --- |
| CLI 기반 실행 | `python main.py --date ...` 동작 | [ ] |
| LLM 여행지 추천 | JSON `recommendation` 필드 | [ ] |
| Kakao 맛집 수집 | JSON `restaurants_by_city` 필드 | [ ] |
| JSON 저장 | `results/*.json` 존재 | [ ] |
| Markdown 저장 | `results/*.md` 존재 | [ ] |
| 오류 처리 | 아래 3번 | [ ] |

---

## 3. 오류 처리 시연

### 3-1. 잘못된 날짜 형식

```bash
python main.py --date "2027/03/01"
```

- [ ] 사용법(형식: YYYY-MM-DD)을 안내하고 정상 종료 (비정상 종료 아님)

### 3-2. API 키 미설정

`.env` 를 잠시 비우거나 이름을 바꾼 뒤 실행:

```bash
python main.py --date "2027-03-01"
```

- [ ] API 키 설정 방법을 안내하고 정상 종료

> 시연 후 `.env` 를 원래대로 복구하세요.

---

## 4. 보너스 기능 시연

### 4-1. 복수 지역 추천

```bash
python -c "import json; d=json.load(open('results/travel_2027-03-01.json', encoding='utf-8')); print('추천 도시:', d['recommendation']['recommended_cities']); print('맛집 수집 도시:', list(d['restaurants_by_city'].keys()))"
```

- [ ] 추천 도시가 여러 개이고, 각 도시별 맛집이 수집됨
- [ ] 두 리스트(추천 도시 / 수집 도시)가 일치함

### 4-2. 결과 캐싱 (재실행)

```bash
python main.py --date "2027-03-01"
```

- [ ] `[1/3]~[3/3]` API 호출 없이 **캐시를 재사용**한다는 메시지가 출력됨
- [ ] 첫 실행보다 눈에 띄게 빠르게 완료됨

### 4-3. Streamlit 웹 GUI

```bash
streamlit run app.py
```

- [ ] 브라우저에서 http://localhost:8501 접속됨
- [ ] 사이드바에서 날짜 선택 시 리포트 표시
- [ ] 맛집 위치가 지도에 표시됨
- [ ] 각 맛집의 카카오맵 링크로 이동 가능

---

## 5. 코드 구조 참고 (선택)

| 파일 | 역할 |
| --- | --- |
| `main.py` | CLI 진입점, 인자 파싱, 실행 흐름 제어 |
| `utils.py` | 추천/검색/리포트/저장/캐싱 로직 |
| `app.py` | Streamlit 웹 GUI |

```bash
# 각 파일 라인 수로 역할 분리 확인
wc -l main.py utils.py app.py
```

---

## 참고 링크 모음

- 저장소: https://github.com/geunwa/travel_project
- Gemini API 키 발급: https://aistudio.google.com/app/apikey
- Kakao Developers 콘솔: https://developers.kakao.com/console/app
- Kakao Local API 문서(키워드 검색): https://developers.kakao.com/docs/latest/ko/local/dev-guide#search-by-keyword
