# 국내 여행 추천 프로그램

특정 날짜를 입력하면 Gemini(LLM)가 해당 시기에 적합한 국내 여행지를 추천하고,
Kakao Local API로 도시별 맛집 정보를 수집하여 리포트를 생성하는 프로그램이다.
결과는 콘솔 출력, JSON, Markdown 리포트로 저장되며, Streamlit 기반 웹 화면으로도 확인할 수 있다.

## 주요 기능

- 날짜 입력에 따른 여행지 추천 (Gemini 기반)
  - 추천 도시, 날씨 요약, 행사/축제, 추천 이유 제공
- 도시별 맛집 정보 수집 (Kakao Local API)
  - 상호명, 주소, 카테고리, 전화번호, 카카오맵 URL, 좌표(경도/위도)
  - 도시명 정규화: 괄호·특수문자 제거 후 핵심 지명(중앙 명사) 추출 및 표준 지명 매핑 (`CITY_ALIAS`)
- 결과 저장
  - JSON 파일 (원본 데이터)
  - Markdown 리포트 (사람이 읽기 좋은 형태)
- 오류 처리 및 오류 요약 리포트 제공
- Streamlit 웹 GUI 제공
  - 날짜별 리포트 선택, 맛집 목록, 지도 표시, 카카오맵 링크

## 보너스 구현 사항

- 복수 지역 추천: 하나의 날짜에 대해 여러 도시를 추천하고 각 도시별로 맛집을 검색
- 결과 캐싱: 동일한 날짜의 원본 JSON이 이미 존재하면 API 호출을 생략하고 저장된 결과를 재사용

## 프로젝트 구조

```
travel_project/
├── main.py              # CLI 실행 진입점 (인자 파싱, 실행 흐름 제어)
├── utils.py             # 추천/검색/리포트 생성/저장/캐싱 로직
├── app.py               # Streamlit 웹 GUI
├── results/             # 생성된 결과 저장 폴더
│   ├── travel_YYYY-MM-DD.json
│   └── travel_YYYY-MM-DD.md
├── .env                 # API 키 저장 (git 미포함)
├── .env.example         # API 키 형식 안내용 예시 파일
├── requirements.txt     # 의존성 목록
└── README.md
```

## 실행 환경

- Python 3.10 이상
- 필요 라이브러리
  - streamlit
  - pandas
  - google-genai (Gemini API)
  - requests (Kakao Local API 호출)
  - python-dotenv (.env 로드)

## 설치 방법

```bash
# 1. 저장소 클론
git clone https://github.com/geunwa/travel_project.git
cd travel_project

# 2. 가상환경 생성 및 활성화 (선택)
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. 의존성 설치
pip install -r requirements.txt
```

## 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하고 다음 키를 입력한다.

```
GEMINI_API_KEY=발급받은_Gemini_API_키
KAKAO_REST_API_KEY=발급받은_카카오_REST_API_키
```

`.env.example`을 복사해 시작할 수 있다.

```bash
cp .env.example .env      # Windows PowerShell: Copy-Item .env.example .env
```

API 키가 설정되지 않은 경우, 프로그램 실행 시 설정 방법을 안내하고 종료한다.

## API 요청 방식 (REST/HTTP 메서드)

본 프로그램은 두 종류의 REST API를 목적에 맞는 HTTP 메서드로 호출한다.

| 단계 | API | 메서드 | 이유 |
|------|-----|:---:|------|
| 1차 추천·리포트 | Gemini | POST | 프롬프트를 요청 본문(body)에 담아 전송. 데이터 양이 많고, 조회가 아닌 생성 작업 |
| 맛집 검색 | Kakao Local | GET | 검색어를 URL 쿼리 파라미터로 전달. 데이터 조회 목적 |

- **GET**: 데이터 조회에 사용. 파라미터가 URL에 노출되며, 캐싱이 가능하다.
- **POST**: 데이터 생성/전송에 사용. 파라미터를 요청 본문(body)에 담아 전달하므로 민감하거나 대용량인 데이터에 적합하다.

## LLM 출력을 JSON으로 강제하는 이유

Gemini의 1차 추천 응답을 자유 텍스트가 아닌 JSON으로 강제한다 (`generate_city_recommendation`).

- **파싱 용이**: `json.loads()`로 즉시 딕셔너리로 변환할 수 있다 (`_extract_json_from_text`).
- **검증 용이**: 필수 키(`REQUIRED_KEYS`)의 존재와 타입을 코드로 확인할 수 있다 (`_validate_recommendation`).
- **다음 단계 연결**: 파싱한 `recommended_cities`를 맛집 검색 API의 입력으로 바로 전달할 수 있다.
- **안정성**: 예측 가능한 구조라 후속 처리 오류가 줄고, 파싱 실패 시 재시도 로직(최대 1회)을 적용할 수 있다.

## API 키를 환경변수로 관리하는 이유

- **보안**: 코드·저장소에 키가 노출되지 않는다. `.gitignore`로 `.env`를 제외한다.
- **운영 편의**: 키 교체 시 코드 수정이 필요 없고, 배포 환경별로 키를 분리할 수 있다.
- **버전관리 회피**: Git 커밋 이력에 키가 남지 않는다.
- **과금 안전**: 쿼터·과금이 있는 서비스에서 키 유출로 인한 사고를 예방한다.

## 실행 방법

### 1. CLI 실행

여행 날짜를 `--date` 인자로 전달한다. (형식: YYYY-MM-DD)

```bash
python main.py --date "2027-03-01"
```

- 실행 흐름
  - [1/3] Gemini로 추천 도시, 날씨, 행사/축제, 추천 이유 생성
  - [2/3] Kakao Local API로 도시별 맛집 검색
  - [3/3] Gemini로 최종 Markdown 리포트 생성
- 실행 결과는 콘솔에 출력되며, `results/` 폴더에 JSON과 Markdown 리포트가 저장된다.
- 동일한 날짜의 원본 데이터가 존재하면 API 호출을 생략하고 캐시를 재사용한다.

날짜 형식이 올바르지 않으면 사용법을 안내하고 종료한다.

### 2. 웹 GUI 실행

```bash
streamlit run app.py
```

- 브라우저에서 `localhost:8501`(또는 지정된 포트)로 접속한다.
- 사이드바에서 날짜를 선택하면 해당 리포트를 확인할 수 있다.
- 맛집 위치는 지도에 표시되며, 각 맛집의 카카오맵 링크를 통해 상세 정보로 이동할 수 있다.

## 출력 결과 예시

### JSON 구조

```json
{
  "date": "2027-03-01",
  "recommendation": {
    "recommended_cities": ["제주", "광양", "부산"],
    "weather": "3월 초는 남부 지방을 중심으로 완연한 봄기운이 시작되는 시기입니다. 낮 기온은 포근하지만 일교차가 크므로 따뜻한 겉옷이 필요합니다.",
    "events": ["광양 매화축제", "제주 산방산 유채꽃 봄맞이"],
    "reason": "삼일절 연휴를 활용해 가장 먼저 봄 소식을 만날 수 있는 남부권 도시들입니다."
  },
  "restaurants_by_city": {
    "제주": [
      {
        "name": "고집돌우럭 함덕점",
        "address": "제주특별자치도 제주시 조천읍 신북로 491-9",
        "category": "음식점 > 한식",
        "phone": "0507-1353-6061",
        "url": "http://place.map.kakao.com/28082185",
        "x": 126.66309886995431,
        "y": 33.54381497240532
      }
    ]
  },
  "errors": []
}
```

### Markdown 리포트

`results/travel_YYYY-MM-DD.md` 파일에 다음 항목이 포함된 리포트가 생성된다.

- 추천 지역
- 추천 이유
- 날씨 요약
- 행사/축제
- 도시별 맛집 추천 (카카오맵 링크 포함)
- 도시별 1일 일정 제안
- 오류 요약

## 오류 처리

- 날짜 형식 오류, API 키 미설정 시 안내 메시지를 출력하고 종료한다.
- API 호출 실패, 데이터 누락 등 예외 상황을 처리하여 프로그램이 비정상 종료되지 않도록 한다.
- 실행 중 발생한 오류는 리스트로 누적되어 결과의 `errors` 항목과 리포트의 "오류 요약" 섹션에 기록된다.

## 오류 대응 체크리스트

### Kakao Local API 401 / 403 발생 시

| 확인 순서 | 확인 항목 | 확인 방법 |
|:---:|---|---|
| 1 | `.env`의 `KAKAO_REST_API_KEY` 값이 올바른지 | `.env` 파일 직접 확인 |
| 2 | **REST API 키**인지 (JavaScript 키 아님) | Kakao Developers 콘솔 → 앱 키 |
| 3 | 요청 헤더가 `Authorization: KakaoAK {키}` 인지 | `utils.py` `headers` 변수 확인 |
| 4 | 앱 플랫폼에 Web 도메인이 등록되어 있는지 | Kakao Developers 콘솔 → 플랫폼 |

### Gemini API 오류 발생 시

| 상황 | 원인 | 대응 |
|---|---|---|
| 인증 오류 | 키 오류/만료 | `.env`의 `GEMINI_API_KEY` 확인 |
| 쿼터 초과 | 무료 한도 소진 | 잠시 후 재시도 / 쿼터 확인 |
| JSON 파싱 실패 | LLM 응답 형식 이탈 | 자동 재시도 1회 → 실패 시 기본값 사용 |

## 주의 사항

- API 키는 절대 코드나 리포트에 직접 작성하지 않는다. 반드시 `.env`로 관리한다.
- `.env`는 `.gitignore`에 포함되어 저장소에 올라가지 않는다.
- 무료 API 쿼터에 유의한다. 캐싱 기능으로 동일 날짜의 중복 호출을 방지할 수 있다.
- 캐시는 날짜 단위로 유지되며, 최신 정보를 다시 받으려면 `results/`의 해당 JSON을 삭제 후 재실행한다.