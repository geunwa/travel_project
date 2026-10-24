# 국내 여행 추천 프로그램

특정 날짜를 입력하면 Gemini(LLM)가 해당 시기에 적합한 국내 여행지를 추천하고,
Kakao Local API로 도시별 맛집 정보를 수집한 뒤, 다시 Gemini로 최종 여행 리포트를 생성하는 CLI 프로그램이다.
결과는 `results/` 폴더에 원본 데이터(JSON)와 리포트(Markdown)로 저장된다.

```
--date 입력 → [1/3] Gemini 1차 추천(JSON) → [2/3] Kakao 맛집 검색(도시별) → [3/3] Gemini 최종 리포트(Markdown) → results/ 저장
```

## 주요 기능

- 날짜 입력에 따른 여행지 추천 (Gemini)
  - 추천 도시 2~3곳, 날씨 요약, 행사/축제, 추천 이유를 JSON으로 생성
- 도시별 맛집 정보 수집 (Kakao Local)
  - 상호명, 주소, 카테고리, 전화번호, 카카오맵 URL, 좌표(경도 x / 위도 y)
  - 음식점 카테고리(`category_group_code=FD6`)로 필터링, 도시당 5곳
- 도시명 키워드 정규화 (`normalize_city_keyword`)
- 결과 저장: 원본 JSON + Markdown 리포트
- 오류 유형 분류 및 오류 요약 (JSON `errors`, 리포트 '7. 오류 요약')

## 보너스 구현 사항

- **복수 지역 추천**: 하나의 날짜에 2~3개 도시를 추천하고, 도시별로 맛집을 검색해 리포트에 지역별로 정리한다.
- **결과 캐싱**: 같은 `--date`의 원본 JSON이 있으면 API 호출을 생략하고 저장된 결과를 재사용한다.
  - 리포트(md)도 있으면 리포트까지 재사용(API 호출 0회), md가 없으면 리포트만 Gemini로 다시 생성
  - 이전 실행의 `errors`에 `status: failed`가 있으면 캐시를 쓰지 않고 새로 호출

## 프로젝트 구조

```
travel_project/
├── main.py              # CLI 진입점 (인자 파싱·날짜 검증·키 확인·실행 흐름·콘솔 로그)
├── utils.py             # 추천/검색/리포트 생성/오류 분류/저장/캐싱 로직
├── list_models.py       # (보조) 사용 가능한 Gemini 모델 목록 확인용
├── results/             # 실행 결과 저장 폴더
│   ├── travel_YYYY-MM-DD.json
│   └── travel_YYYY-MM-DD.md
├── .env                 # API 키 (git 제외)
├── .env.example         # API 키 형식 안내용 예시
├── requirements.txt     # 의존성 목록
├── EVALUATION.md        # 평가 시연 가이드
├── presentation.html    # 발표 자료
└── README.md
```

## 실행 환경

- Python 3.10 이상 (Python 3.14.7에서 실행 확인)
- Gemini 모델: `gemini-flash-latest` (`utils.py`의 `GEMINI_MODEL`)
- 라이브러리: google-genai, requests, python-dotenv

## 설치 방법

```bash
# 1. 저장소 클론
git clone https://github.com/geunwa/travel_project.git
cd travel_project

# 2. 가상환경 생성 및 활성화 (선택)
python -m venv .venv
source .venv/bin/activate          # Windows PowerShell: .\.venv\Scripts\Activate.ps1

# 3. 의존성 설치
pip install -r requirements.txt
```

## API 키 설정

프로젝트 루트에 `.env` 파일을 만들고 다음 키를 입력한다.

```
GEMINI_API_KEY=발급받은_Gemini_API_키
KAKAO_REST_API_KEY=발급받은_카카오_REST_API_키
```

`.env.example`을 복사해 시작할 수 있다.

```bash
cp .env.example .env      # Windows PowerShell: Copy-Item .env.example .env
```

`.env` 대신 환경변수로 설정해도 된다. 환경변수가 `.env`보다 우선한다.

```bash
export GEMINI_API_KEY="YOUR_KEY"          # macOS/Linux (현재 터미널 세션에만 적용)
$env:GEMINI_API_KEY="YOUR_KEY"            # Windows PowerShell (현재 세션에만 적용)
```

키가 하나라도 없으면 프로그램은 API를 호출하지 않고, 누락된 키 이름과 설정 방법을 출력한 뒤 종료한다(종료 코드 1).

### API 키를 환경변수/.env로 관리하는 이유

- **보안**: 코드·저장소에 키가 노출되지 않는다. `.gitignore`로 `.env`를 제외한다.
- **운영 편의**: 키를 교체해도 코드를 수정할 필요가 없고, 개발/운영 환경별로 다른 키를 쓸 수 있다.
- **버전관리 회피**: Git 커밋 이력에 키가 남지 않는다.
- **과금 안전**: 쿼터·과금이 걸린 서비스에서 키 유출로 인한 사고를 예방한다.
- 운영 환경에서는 `.env` 파일 대신 서버/CI의 환경변수나 비밀관리 서비스에 키를 등록하는 방식을 권장한다.

## 실행 방법

### 1. CLI 실행

```bash
python main.py --date "2027-05-05"
```

실행 예시:

```
[1/3] 1차 추천 생성 중(LLM)...
  - recommended_cities: ['태안', '담양', '춘천']
[2/3] 맛집 검색 중(지도/장소 API)...
  - 태안: 맛집 5곳 검색 완료
  - 담양: 맛집 5곳 검색 완료
  - 춘천: 맛집 5곳 검색 완료
[3/3] 최종 리포트 생성 중(LLM)...
  - 리포트 생성 완료

완료! results\travel_2027-05-05.md 를 확인하세요.
원본 데이터: results\travel_2027-05-05.json
```

- 날짜는 `YYYY-MM-DD` 형식(월·일 두 자리)이어야 한다. `2026-1-5`, `2026-13-99`처럼 형식이나 날짜가 틀리면 사용법을 출력하고 종료한다(종료 코드 1).
- `--date`를 빠뜨리면 argparse가 사용법을 출력하고 종료한다(종료 코드 2).
- 결과는 실행 위치와 관계없이 프로젝트 폴더의 `results/`에 저장된다.

### 2. 결과물 확인 방법

| 파일 | 내용 |
|---|---|
| `results/travel_YYYY-MM-DD.json` | 원본 데이터: 1차 추천(`recommendation`), 도시별 맛집(`restaurants_by_city`), 오류 목록(`errors`) |
| `results/travel_YYYY-MM-DD.md` | 최종 리포트: 추천 지역, 추천 이유, 날씨 요약, 행사/축제, 도시별 맛집, 도시별 1일 일정, 오류 요약 |

- 같은 날짜로 다시 실행하면 파일을 덮어쓴다.
- 저장소에는 샘플로 `travel_2027-05-05.*`(정상 실행)와 `travel_2027-08-15.*`(Kakao 인증 실패 재현)가 포함되어 있다.

## 데이터 구조

### 1차 추천 JSON (Gemini 응답 → 파싱·검증)

| 키 | 타입 | 설명 |
|---|---|---|
| `recommended_city` | string | 대표 추천 도시 (= `recommended_cities[0]`, 과제 필수 스키마) |
| `recommended_cities` | string[] | 추천 도시 2~3개 (보너스: 복수 지역). 공백·중복 제거 후 최대 3개 |
| `weather` | string | 해당 시기 일반적인 날씨 요약 |
| `events` | string[] | 행사/축제 후보 1~3개 (초과분은 잘라냄) |
| `reason` | string | 추천 근거 2~4문장 |

Gemini 응답은 `recommended_cities`, `weather`, `events`, `reason` 4개 키를 요구하며(`REQUIRED_KEYS`), `recommended_city`는 프로그램이 첫 번째 도시로 채운다.

### 원본 데이터 JSON 예시 (`results/travel_2027-05-05.json` 일부)

```json
{
  "date_text": "2027-05-05",
  "recommendation": {
    "recommended_cities": ["태안", "담양", "춘천"],
    "weather": "낮 기온이 20~23도 안팎으로 온화하고 맑아 야외 나들이를 즐기기에 가장 쾌적한 늦봄 날씨입니다.",
    "events": ["태안 세계튤립꽃박람회", "담양대나무축제"],
    "reason": "5월 초는 싱그러운 신록과 만개한 봄꽃을 만끽할 수 있어 ...",
    "recommended_city": "태안"
  },
  "restaurants_by_city": {
    "태안": [
      {
        "name": "수미정 본점",
        "address": "충남 태안군 안면읍 그네들길 147",
        "category": "음식점 > 한식 > 해물,생선 > 게,대게",
        "phone": "041-673-0001",
        "url": "http://place.map.kakao.com/24726724",
        "x": 126.35005390983788,
        "y": 36.533312119498355
      }
    ]
  },
  "errors": []
}
```

(`reason`과 맛집 목록은 일부만 표시했다. 전체는 샘플 파일을 참고한다.)

### errors 항목 구조

```json
{"step": "place_search", "type": "AUTH_ERROR", "status": "failed", "message": "kakao 오류: 401 Client Error: Unauthorized ...", "city": "강릉", "query": "강릉 맛집"}
```

| 키 | 값 |
|---|---|
| `step` | `recommendation`(1차 추천) / `place_search`(맛집 검색) / `report`(최종 리포트) |
| `type` | 오류 유형 (아래 표) |
| `status` | `retry`(재시도함) / `failed`(최종 실패) / `empty`(검색 0건) |
| `message` | 원인 메시지 |
| `city`, `query` | 맛집 검색 오류일 때만: 원래 도시명과 실제 검색어 |

## API 요청 방식 (REST/HTTP 메서드)

| 단계 | API | 메서드 | 엔드포인트 / 전달 방식 | 이유 |
|---|---|:---:|---|---|
| 1차 추천·최종 리포트 | Gemini | POST | `https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent`, 프롬프트를 요청 본문(JSON)에 담음 | 서버에 새 결과 생성을 요청. 프롬프트가 길어 본문 전송이 적합 |
| 맛집 검색 | Kakao Local | GET | `https://dapi.kakao.com/v2/local/search/keyword.json?query=태안+맛집&size=5&category_group_code=FD6`, 헤더 `Authorization: KakaoAK {키}` | 기존 데이터 조회. 검색 조건을 URL 쿼리로 전달 |

- **GET**: 데이터 조회. 파라미터가 URL에 드러나며 캐싱이 가능하다. 키는 URL이 아니라 헤더로 보낸다.
- **POST**: 데이터 생성/전송. 파라미터를 본문(body)에 담아 대용량·구조화 데이터 전송에 적합하다.
- 구현: Gemini는 `google-genai` SDK(`generate_content`)가 내부에서 POST 요청을 보내고, Kakao는 `requests.get`으로 직접 호출한다.

Gemini POST 본문 형태(SDK가 생성):

```json
{"contents": [{"role": "user", "parts": [{"text": "당신은 여행 전문가입니다. 2027-05-05 날짜를 기준으로 ..."}]}]}
```

## LLM 출력을 JSON으로 강제하는 이유

1차 추천 응답을 자유 텍스트가 아닌 JSON으로 받도록 프롬프트에서 요구한다(`generate_city_recommendation`).

- **파싱 용이**: `json.loads()`로 바로 딕셔너리로 바꾼다. 코드블록(```json)이나 앞뒤 설명이 섞여도 `_extract_json_from_text`가 JSON 부분만 추출한다.
- **검증 용이**: 필수 키와 타입을 코드로 검사한다(`_validate_recommendation`). 실패하면 어떤 키가 왜 틀렸는지 메시지로 남긴다.
  - 예: `필수 키 누락: ['reason']; recommended_cities: 모든 원소가 문자열이어야 함`
- **다음 단계 연결**: 검증된 `recommended_cities`를 그대로 맛집 검색의 입력으로 넘긴다.
- **복구 흐름**: 1회차 실패 → "JSON 객체 하나만, 필수 키 4개 포함"으로 강화한 프롬프트로 1회만 재시도 → 그래도 실패하면 기본값(서울)을 쓰고 `status: failed`를 기록한다. 이 결과는 캐시로 재사용되지 않는다.

## 도시명 키워드 정규화

LLM이 돌려준 도시명을 Kakao 검색어(`{키워드} 맛집`)로 바꾸기 전에 다음 순서로 정리한다(`normalize_city_keyword`).

1. 괄호·중점·쉼표·슬래시 제거, 공백 정리 후 첫 단어만 사용
2. 섬 지명 표준화: `제주도→제주`, `거제도→거제`, `강화도→강화`, `울릉도→울릉`
3. 행정구역 접미사 제거: `특별자치시`, `특별자치도`, `광역시`, `특별시`, `시`, `군`, `구` (긴 것부터 검사)
   - 접미사를 떼고 **2글자 이상 남을 때만** 제거한다. `대구`, `양구`, `중구`처럼 지명 자체가 접미사로 끝나는 경우를 보호한다.

| 입력 | 검색 키워드 |
|---|---|
| 경주시 | 경주 |
| 부산광역시 | 부산 |
| 제주(제주시) / 제주특별자치도 / 제주도 | 제주 |
| 대구 / 양구 | 대구 / 양구 (변경 없음) |

## 오류 처리

| 상황 | 동작 |
|---|---|
| 날짜 형식 오류 | 사용법 출력 후 종료 (코드 1) |
| API 키 미설정 | 누락 키 이름 + 설정 방법 출력 후 즉시 종료 (코드 1) |
| 1차 추천 파싱/호출 실패 | 강화 프롬프트로 1회 재시도 → 실패 시 기본값 사용, `failed` 기록 |
| 맛집 검색 실패 (인증/쿼터/네트워크 등) | 해당 도시는 빈 목록, 리포트에 `데이터 없음 (검색 실패: 유형)`, 다음 도시·리포트 계속 진행 |
| 맛집 검색 0건 | 해당 도시는 빈 목록, 리포트에 `데이터 없음 (장소 검색 결과 0건)`, 계속 진행 |
| 최종 리포트 생성 실패 | 일시 오류(5xx/네트워크/429)는 3초 후 1회 재시도 → 실패 시 수집한 데이터로 기본 리포트 생성 (맛집 목록 유지, 1일 일정은 템플릿) |

- 재시도는 단계마다 최대 1회이며 무한 재시도는 없다.
- 모든 오류는 `errors`에 누적되어 JSON과 리포트 '7. 오류 요약'에 기록된다. '오류 요약' 섹션은 LLM이 아니라 프로그램이 항상 마지막에 붙인다.

### 오류 유형 분류 (`classify_error`)

| type | 판단 기준 | 콘솔 안내 |
|---|---|---|
| `AUTH_ERROR` | HTTP 401 / 403 | 인증 실패. API 키 값·키 종류·권한 설정을 확인하세요 |
| `QUOTA_ERROR` | HTTP 429 | 쿼터 초과(429). 잠시 후 다시 시도하세요 |
| `SERVER_ERROR` | HTTP 5xx | 서버 오류(5xx). 일시적 장애일 수 있습니다 |
| `NETWORK_ERROR` | 연결 실패, 시간 초과(10초) | 네트워크 오류(연결 실패/시간 초과) |
| `PARSE_ERROR` | JSON 파싱 실패, 필수 키·타입 불일치 | 응답 파싱 실패 |
| `EMPTY_RESULT` | 맛집 검색 결과 0건 | 검색 결과 0건 |
| `UNKNOWN_ERROR` | 그 외 | 알 수 없는 오류 |

상태 코드는 Kakao(requests)는 `response.status_code`, Gemini(SDK)는 예외의 `code`에서 읽는다.

## 오류 대응 체크리스트

오류 확인 위치: 콘솔의 `[2/3]` 도시별 안내, `results/travel_YYYY-MM-DD.json`의 `errors`, 리포트의 '7. 오류 요약'.

### Kakao Local API 401 / 403 (`AUTH_ERROR`)

| 순서 | 확인 항목 | 확인 방법 |
|:---:|---|---|
| 1 | `.env`의 `KAKAO_REST_API_KEY` 값에 오타·공백·따옴표가 없는지 | `.env` 파일 직접 확인 |
| 2 | 같은 이름의 환경변수가 `.env`를 덮어쓰고 있지 않은지 | PowerShell `$env:KAKAO_REST_API_KEY` 확인, 필요 시 `Remove-Item Env:KAKAO_REST_API_KEY` |
| 3 | **REST API 키**인지 (JavaScript·Admin 키 아님) | Kakao Developers → 내 애플리케이션 → 앱 키 |
| 4 | 요청 헤더가 `Authorization: KakaoAK {키}` 형식인지 | `utils.py`의 `KakaoLocalProvider.__init__` |
| 5 | 앱에서 카카오맵(로컬) API 사용이 활성화되어 있는지 | Kakao Developers 콘솔 → 앱 설정 |

`errors`에 남는 예:

```
place_search | AUTH_ERROR | failed | kakao 오류: 401 Client Error: Unauthorized for url: https://dapi.kakao.com/v2/local/search/keyword.json?query=...
```

### Gemini API 오류

| type | 원인 | 대응 |
|---|---|---|
| `AUTH_ERROR` | 키 오류/만료/권한 없음 | `.env`의 `GEMINI_API_KEY` 확인 |
| `QUOTA_ERROR` | 무료 한도 소진 | 잠시 후 재실행, Google AI Studio에서 쿼터 확인 |
| `SERVER_ERROR` | 503 등 일시적 과부하 | 자동 1회 재시도. 실패 시 기본 리포트 생성 → 잠시 후 같은 날짜로 재실행(실패 기록이 있어 캐시 무시) |
| `PARSE_ERROR` | 응답 형식 이탈 | 자동 1회 재시도 → 실패 시 기본값 사용 |

## 지도/장소 API 교체 방법

맛집 검색은 `utils.py`의 공통 인터페이스 `PlaceSearchProvider`를 통해 호출한다. 현재 구현은 `KakaoLocalProvider`이다.

```python
class PlaceSearchProvider:
    name = "base"
    def search(self, keyword: str, size: int) -> list[dict]:
        raise NotImplementedError
```

`search()` 계약:

- 입력: `keyword`(예: `"태안 맛집"`), `size`(검색 개수)
- 출력: `[{"name", "address", "category", "phone", "url", "x", "y"}]` 목록. 0건이면 `[]`
- 실패: 예외를 그대로 발생시킨다. 오류 분류와 `errors` 기록은 `search_restaurants`가 맡는다.

Naver Local 등으로 바꿀 때는 이 클래스를 상속한 어댑터를 만들고, `main.py`에서 `KakaoLocalProvider(kakao_key)` 한 줄만 새 클래스로 바꾼다. 키 이름이 다르면 `load_keys()`도 함께 수정한다.

## 주요 함수 입출력

| 함수 | 입력 | 출력 | 실패 시 |
|---|---|---|---|
| `generate_city_recommendation` | `date_text`, `api_key`, `errors` | 1차 추천 dict | 1회 재시도 후 기본값 반환, `errors`에 기록 |
| `search_restaurants_by_cities` | `cities`, `provider`, `errors`, `size` | `{도시: [맛집 dict]}` | 해당 도시 `[]`, `errors`에 기록 |
| `generate_final_report` | `date_text`, `recommendation`, `restaurants_by_city`, `errors`, `api_key` | Markdown 문자열 | 기본 리포트 반환 |
| `save_results` | 위 결과 + `report` | `{"md_path", "json_path"}` | 예외 발생 (디스크 오류 등) |
| `load_cached_raw` / `load_cached_report` | `date_text` | dict / str 또는 `None` | 파일 없음·손상 시 `None` |

## 캐시 정책

- 기준: 같은 `--date`의 `results/travel_YYYY-MM-DD.json` 존재 여부
- 유효기간(TTL)은 두지 않는다. 날짜별 추천은 재실행할 때마다 달라질 수 있으므로, 한 번 만든 결과를 재사용하는 것이 목적이다.
- 재사용하지 않는 경우: JSON이 손상됨, 또는 `errors`에 `status: failed`가 있음
- 수동 갱신: 해당 날짜의 JSON(필요하면 md도)을 삭제하고 다시 실행한다.

```powershell
Remove-Item results\travel_2027-05-05.json, results\travel_2027-05-05.md
```

## 주의 사항

- API 키는 코드·README·결과물에 직접 쓰지 않는다. 반드시 `.env` 또는 환경변수로 관리한다.
- `.env`는 `.gitignore`에 포함되어 저장소에 올라가지 않는다. `results/`는 샘플 2세트(`travel_2027-05-05.*`, `travel_2027-08-15.*`)를 제외하고 저장소에서 제외된다.
- 오류 메시지에는 요청 URL(검색어)이 남을 수 있지만, Kakao 키는 헤더로만 전송되므로 기록되지 않는다.
- 무료 API 쿼터에 유의한다. 캐싱으로 같은 날짜의 중복 호출을 막는다.
- 커밋 전 점검: `git status`에 `.env`가 보이지 않는지, `git log --all --oneline -- .env` 출력이 비어 있는지 확인한다.

## 참고

- 다른 분의 과제를 보고 화면(그래픽) 구현도 해 보았으나, 과제 요구 범위가 아니어서 제출물에서는 제외했다.
