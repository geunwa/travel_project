# 국내 여행 추천 프로그램

특정 날짜를 입력하면 Gemini(LLM)가 해당 시기에 적합한 국내 여행지를 추천하고,
Kakao Local API로 도시별 맛집 정보를 수집하여 리포트를 생성하는 프로그램이다.
결과는 콘솔 출력, JSON, Markdown 리포트로 저장되며, Streamlit 기반 웹 화면으로도 확인할 수 있다.

## 주요 기능

- 날짜 입력에 따른 여행지 추천 (Gemini 기반)
  - 추천 도시, 날씨 요약, 행사/축제, 추천 이유 제공
- 도시별 맛집 정보 수집 (Kakao Local API)
  - 상호명, 주소, 카테고리, 전화번호, 카카오맵 URL, 좌표(경도/위도)
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

API 키가 설정되지 않은 경우, 프로그램 실행 시 설정 방법을 안내하고 종료한다.

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
| 2 | **REST API 키**인지 (JavaScript 키 아님) | Kakao Developers 콘솔 → 내 애플리케이션 → 앱 키 |
| 3 | 요청 헤더 형식이 `Authorization: KakaoAK {키}` 인지 | `utils.py` `headers` 변수 확인 |
| 4 | 앱의 플랫폼에 Web 도메인이 등록되어 있는지 | Kakao Developers 콘솔 → 플랫폼 → Web |

오류 로그 위치: 콘솔 출력 + `results/travel_YYYY-MM-DD.json` 의 `errors` 배열

### Gemini API 429 (할당량 초과) 발생 시

| 확인 순서 | 확인 항목 |
|:---:|---|
| 1 | 무료 등급 일일 한도(20회) 초과 여부 → 다음 날 재시도 |
| 2 | 캐시된 날짜로 실행하면 API 호출 없이 리포트 재생성 가능 |

```bash
# 캐시 재사용 예시 (API 호출 없음)
python main.py --date "2027-03-01"
```

## 지도 API 교체 가이드

현재 구현은 **Kakao Local API**를 사용하며, 교체 시 `utils.py`의 아래 함수만 수정하면 된다.

| 교체 대상 | 위치 | 유지해야 할 반환 형식 |
|---|---|---|
| API URL / 헤더 | `search_restaurants()` 내부 | 변경 가능 |
| 반환 데이터 형식 | `search_restaurants()` return 값 | 아래 형식 유지 필수 |

반환 형식 (이 구조를 유지하면 `main.py` 수정 불필요):

```python
[
    {
        "name": str,       # 장소명
        "address": str,    # 도로명 주소
        "category": str,   # 카테고리
        "phone": str,      # 전화번호
        "url": str,        # 장소 상세 URL
        "x": float,        # 경도 (longitude)
        "y": float,        # 위도 (latitude)
    }
]
```

## 과제 요구사항 대응

| 요구사항 | 구현 여부 |
| --- | --- |
| CLI 기반 실행 | 완료 |
| LLM(Gemini)을 이용한 여행지 추천 | 완료 |
| Kakao API 맛집 정보 수집 | 완료 |
| JSON 저장 | 완료 |
| Markdown 리포트 저장 | 완료 |
| 오류 처리 | 완료 |
| (보너스) 복수 지역 추천 | 완료 |
| (보너스) 결과 캐싱 | 완료 |
| (개인보너스) Streamlit GUI | 완료 |