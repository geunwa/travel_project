# 평가 시연 가이드

> 본 문서는 **평가자에게 과제 완성도를 순서대로 설명**하기 위한 시연 가이드입니다.
> 실시간 시연은 캐시가 없는 **2026-12-31**을 기준으로 진행하여 실제 API 호출 과정을 확인합니다.
> 명령어는 프로젝트 폴더에서 가상환경을 활성화한 뒤 실행합니다(Windows PowerShell 기준).

```powershell
cd travel_project
.\.venv\Scripts\Activate.ps1
```

### 시연 직전 점검 목록

| 점검 | 확인 방법 |
|---|---|
| 최신 코드가 GitHub에 올라가 있는지 | `git status` 깨끗함, `git log --oneline -1`이 `origin/main`과 같은지 |
| 가상환경 활성화 | 프롬프트 앞에 `(.venv)` 표시 |
| 시연 날짜 캐시 없음 | `results\travel_2026-12-31.*` 파일이 없어야 함 (있으면 삭제) |
| 인터넷 연결 · API 응답 | 다른 날짜로 1회 사전 실행 후 결과 삭제: `python main.py --date "2027-03-01"` → `Remove-Item results\travel_2027-03-01.*` |
| `.env`는 화면에 열지 않음 | VS Code 탭에서 닫아 두기 |

### API 장애 시 예비 방안

| 상황 | 대응 |
|---|---|
| Gemini 503(과부하) | 자동 1회 재시도 → 실패 시 맛집을 유지한 기본 리포트 생성. 오류 요약의 `SERVER_ERROR`를 오류 처리 시연으로 활용 |
| 실시간 실행 실패로 캐시 시연 불가 (`failed` 기록) | 저장소 샘플로 캐시 시연: `python main.py --date "2027-05-05"` (오류 없이 저장된 샘플이라 항상 `(캐시)`) |
| 네트워크 단절 | 발표 자료의 예비 화면(터미널 재생)과 저장소 샘플 `results/travel_2027-05-05.*`, `travel_2027-08-15.*`로 설명 |

---

## 1. 과제 소개

**Python 응용: API 활용 국내 여행지 추천 프로그램**

- 사용자가 여행 날짜를 입력하면,
- **① LLM(Gemini)** 이 해당 시기에 좋은 여행지를 JSON으로 추천하고,
- **② 지도 API(Kakao Local)** 로 그 도시들의 맛집을 검색한 뒤,
- **③ LLM** 이 이를 종합해 **최종 여행 리포트(Markdown)** 를 생성합니다.

> 핵심: 단일 API 호출이 아니라 **여러 API를 엮어 인사이트를 만드는 흐름**을 구현했습니다.
> LLM 출력(JSON)의 `recommended_cities`가 지도 API의 입력이 되고, 두 결과가 다시 LLM의 입력이 됩니다.

---

## 2. 최종 결과물 체크리스트 ✅

| 요구 결과물 | 구현 여부 | 위치 / 확인 방법 |
|---|:---:|---|
| **CLI 기반 Python 프로그램** | ✅ | `python main.py --date "YYYY-MM-DD"` |
| 진행 로그 + 저장 경로 안내 | ✅ | 실행 시 `[1/3] → [2/3] → [3/3]` 콘솔 출력, 마지막에 저장 경로 |
| **원본 데이터 JSON** (1차 추천 + 맛집 + errors) | ✅ | `results/travel_YYYY-MM-DD.json` |
| **최종 여행 리포트 Markdown** | ✅ | `results/travel_YYYY-MM-DD.md` |
| **README.md** (개요/실행법/키설정/확인법/보안) | ✅ | 프로젝트 루트 `README.md` |

### 실시간 시연

```powershell
python main.py --date "2026-12-31"
```

**기대 출력 (추천 도시·맛집 수는 실행마다 달라질 수 있음):**

```
[1/3] 1차 추천 생성 중(LLM)...
  - recommended_cities: ['도시1', '도시2', '도시3']
[2/3] 맛집 검색 중(지도/장소 API)...
  - 도시1: 맛집 5곳 검색 완료   (추천된 도시마다 한 줄씩 출력)
[3/3] 최종 리포트 생성 중(LLM)...
  - 리포트 생성 완료

완료! results\travel_2026-12-31.md 를 확인하세요.
원본 데이터: results\travel_2026-12-31.json
```

시연 후 생성되는 파일:
- `results/travel_2026-12-31.json` (원본 데이터: `recommendation`, `restaurants_by_city`, `errors`)
- `results/travel_2026-12-31.md` (최종 리포트: 1~6 섹션 + 7. 오류 요약)

> Gemini가 일시 과부하(503)이면 자동으로 1회 재시도하고, 그래도 실패하면 수집한 맛집 데이터로 기본 리포트를 만들어 저장합니다. 이 경우 실패 기록이 남아 같은 날짜로 다시 실행하면 캐시를 쓰지 않고 새로 호출합니다.

---

## 3. 과제 목표 달성 설명

| 목표 | 프로젝트에서의 구현 근거 |
|---|---|
| **REST API 요청/응답, GET/POST 차이** | Gemini는 `POST .../models/gemini-flash-latest:generateContent`(본문에 프롬프트, `google-genai` SDK 경유), Kakao는 `GET .../v2/local/search/keyword.json?query=...`(쿼리 파라미터 + `Authorization: KakaoAK` 헤더) |
| **LLM 출력 → JSON 구조화 → 다음 단계 입력** | 1차 추천 JSON을 파싱하고 키·타입 검증(`_validate_recommendation`) → `recommended_cities`를 맛집 검색 입력으로 전달 → 맛집 목록과 함께 리포트 생성 입력으로 전달 |
| **API 대표 오류 대응** (인증/쿼터/네트워크/파싱) | `classify_error`가 HTTP 상태 코드와 예외 종류로 `AUTH_ERROR`(401/403)·`QUOTA_ERROR`(429)·`SERVER_ERROR`(5xx)·`NETWORK_ERROR`·`PARSE_ERROR`·`EMPTY_RESULT`로 분류 → `errors`에 `{step, type, status, message}`로 기록 → 콘솔 안내와 리포트 '오류 요약'에 반영 |
| **.env로 키 관리하는 이유** | 키 노출 방지·교체 용이·과금 사고 예방 → `python-dotenv`로 로드, `.gitignore`로 `.env` 제외, Git 이력에 `.env` 없음 |

---

## 4. 기능 요구 사항 충족 설명

| 요구 사항 | 구현 내용 |
|---|---|
| **CLI (argparse)** | `main.py`에서 `--date` 필수 옵션 파싱 |
| **날짜 형식 검증** | 정규식(`YYYY-MM-DD`, 월·일 두 자리) + 실제 날짜 검사. 실패 시 사용법 출력 후 종료(코드 1) |
| **LLM API (택1)** | ✅ **Google Gemini** (`gemini-flash-latest`) |
| **지도 API (택1)** | ✅ **Kakao Local** (키워드 검색 + 음식점 카테고리 `FD6`), `PlaceSearchProvider` 인터페이스로 교체 가능 |
| **1차 JSON 스키마** | `recommended_city`(string), `recommended_cities`(string[]), `weather`(string), `events`(string[] 1~3), `reason`(string) |
| **맛집 검색** | 도시명 정규화(`부산광역시→부산`, `대구` 유지) 후 도시별 5곳, 필드: `name/address/category/phone/url/x/y` |
| **검색 0건 처리** | 중단 없이 `데이터 없음 (장소 검색 결과 0건)`으로 리포트 진행 |
| **최종 리포트** | 추천 지역·이유·날씨·행사·도시별 맛집·도시별 1일 일정(오전/오후/저녁) + 오류 요약 |
| **에러 처리** | 키 미설정 즉시 종료 / 지도 실패 시 `데이터 없음 (검색 실패: 유형)`으로 계속 / LLM 파싱 실패 시 **재시도 1회** / 리포트 일시 오류 시 재시도 1회 후 기본 리포트 |
| **결과 저장** | 프로젝트 폴더 `results/`에 JSON(추천+맛집+errors) & MD 저장 |

### 검증용 시연 명령어

**① 잘못된 날짜 형식 → 사용법 출력, 종료 코드 1**

```powershell
python main.py --date "2026-1-5"; "exit=$LASTEXITCODE"
```

**② 인자 없이 실행 → argparse 사용법 출력, 종료 코드 2**

```powershell
python main.py; "exit=$LASTEXITCODE"
```

**③ API 키 미설정 → 즉시 종료 + 설정 방법 안내 (이 실행에서만 `.env`를 읽지 않도록 막음, `.env` 파일은 그대로)**

```powershell
python -c "import os, sys, dotenv; dotenv.load_dotenv=lambda *a, **k: False; os.environ.pop('GEMINI_API_KEY', None); os.environ.pop('KAKAO_REST_API_KEY', None); sys.argv=['main.py', '--date', '2026-12-31']; import main; main.main()"; "exit=$LASTEXITCODE"
```

**④ 지도 API 인증 실패(401) → 맛집 '데이터 없음' 처리 후 리포트 계속 생성**

현재 터미널에서만 잘못된 Kakao 키를 쓰고, 실행 후 바로 지웁니다(환경변수가 `.env`보다 우선).

```powershell
$env:KAKAO_REST_API_KEY = "INVALID_KEY_FOR_TEST"
python main.py --date "2027-01-01"
Remove-Item Env:KAKAO_REST_API_KEY
```

**기대 출력:**

```
[2/3] 맛집 검색 중(지도/장소 API)...
  - 도시1: 인증 실패. API 키 값·키 종류·권한 설정을 확인하세요 [AUTH_ERROR]
    → 맛집 섹션은 '데이터 없음'으로 처리하고 계속 진행합니다.
  ...
[3/3] 최종 리포트 생성 중(LLM)...
  - 리포트 생성 완료
```

리포트 '7. 오류 요약'과 JSON `errors`에 `place_search | AUTH_ERROR | failed`가 기록됩니다.
실행 결과 예시는 저장소 샘플 `results/travel_2027-08-15.*`에서도 확인할 수 있습니다.

---

## 5. 보너스 과제 구현 여부

| 보너스 | 구현 | 설명 |
|---|:---:|---|
| **복수 지역 추천** | ✅ | `recommended_cities`로 2~3개 도시 추천 → 도시별 맛집 검색(루프) → 리포트에 도시별 정리 |
| **결과 캐싱** | ✅ | 같은 `--date` 재실행 시 저장된 JSON·MD가 있으면 **모든 API 호출을 생략**. 실패(`failed`) 기록이 있으면 캐시를 쓰지 않음 |

### 캐싱 시연

> 2번 섹션의 첫 실행이 오류 없이 완료된 후 같은 명령어를 다시 실행하세요.

```powershell
python main.py --date "2026-12-31"
```

**기대 출력 (캐시 히트 시):**

```
[캐시] 기존 데이터를 재사용합니다: results/travel_2026-12-31.json
[1/3] (캐시) 추천 도시: ...
[2/3] (캐시) 맛집 총 N곳 로드 완료 (M개 지역)
[3/3] (캐시) 기존 리포트를 재사용합니다.

완료! results\travel_2026-12-31.md 를 확인하세요.
원본 데이터: results\travel_2026-12-31.json
```

→ 모든 단계가 `(캐시)`로 표시되며, **Gemini·Kakao API를 한 번도 호출하지 않습니다.**
(JSON만 있고 MD가 없으면 [3/3] 리포트만 Gemini로 새로 생성합니다. 첫 실행에 `failed`가 기록됐다면 "[캐시] 이전 실행에 실패 기록이 있어..." 안내 후 다시 호출합니다.)

---

## 6. 개발 환경 & 제약 사항 준수

### 개발 환경

| 항목 | 준수 여부 |
|---|:---:|
| Python 3.10 이상 | ✅ (3.14.7에서 실행 확인) |
| 터미널 실행 가능 (CLI) | ✅ (`python main.py --date ...`) |

### 제약 사항 (보안 — 필수)

| 항목 | 준수 여부 | 근거 |
|---|:---:|---|
| API 키를 코드/README/결과물에 직접 작성 안 함 | ✅ | 모든 키는 `.env`/환경변수에서 로드, 결과물·문서에 키 문자열 없음 확인 |
| `.env` / 환경변수 사용 | ✅ | `python-dotenv`로 로드 |
| `.env`를 Git에서 제외 | ✅ | `.gitignore`에 `.env` 등록, `git log --all -- .env` 이력 없음 |
| 키 설정 예시 제공 | ✅ | `.env.example` 파일로 형식만 안내 |

### 운영 안정성 (권장)

| 항목 | 준수 여부 |
|---|:---:|
| 키 미설정 시 즉시 종료 + 안내 | ✅ |
| 지도 API 실패 시에도 리포트 생성 진행 | ✅ |
| LLM JSON 파싱 실패 시 재시도 **최대 1회** | ✅ |

---

## 부록: API 키 설정 방법 (평가자용)

```powershell
# 1) .env.example을 복사해 .env 생성
Copy-Item .env.example .env      # macOS/Linux: cp .env.example .env

# 2) .env 파일에 본인 키 입력
GEMINI_API_KEY=여기에_Gemini_키
KAKAO_REST_API_KEY=여기에_Kakao_REST_API_키
```

> 상세 설정과 오류 대응 체크리스트는 `README.md`를 참고하세요.

---

**저장소:** https://github.com/geunwa/travel_project
