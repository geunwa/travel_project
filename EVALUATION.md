# 평가 시연 가이드

> 본 문서는 **평가자에게 과제 완성도를 순서대로 설명**하기 위한 시연 가이드입니다.
> 시연 날짜는 캐시가 없는 **2026-12-31**을 기준으로 진행하여 실시간 API 호출 과정을 확인합니다.

---

## 1. 과제 소개

**Python 응용: API 활용 국내 여행지 추천 프로그램**

- 사용자가 여행 날짜를 입력하면,
- **① LLM(Gemini)** 이 해당 시기에 좋은 여행지를 추천하고,
- **② 지도 API(Kakao Local)** 로 그 도시의 맛집을 검색한 뒤,
- **③ LLM** 이 이를 종합해 **최종 여행 리포트(Markdown)** 를 생성합니다.

> 핵심: 단일 API 호출이 아니라 **여러 API를 엮어 인사이트를 만드는 흐름**을 구현했습니다.

---

## 2. 최종 결과물 체크리스트 ✅

| 요구 결과물 | 구현 여부 | 위치 / 확인 방법 |
|---|:---:|---|
| **CLI 기반 Python 프로그램** | ✅ | `python main.py --date "YYYY-MM-DD"` |
| 진행 로그 + 저장 경로 안내 | ✅ | 실행 시 `[1/3] → [2/3] → [3/3]` 콘솔 출력 |
| **원본 데이터 JSON** (1차 추천 + 맛집 + errors) | ✅ | `results/travel_YYYY-MM-DD.json` |
| **최종 여행 리포트 Markdown** | ✅ | `results/travel_YYYY-MM-DD.md` |
| **README.md** (개요/실행법/키설정/확인법/보안) | ✅ | 프로젝트 루트 `README.md` |

### 실시간 시연 (터미널에 아래 명령어를 복사해 실행)

```bash
python main.py --date "2026-12-31"
```


**기대 출력:**

```
[1/3] 1차 추천 생성 중(LLM)...
  - recommended_cities: [...]
[2/3] 맛집 검색 중(지도/장소 API)...
  - 맛집 검색 완료
[3/3] 최종 리포트 생성 중(LLM)...
  - 리포트 생성 완료

완료! results/travel_2026-12-31.md 를 확인하세요.
```

시연 후 생성되는 파일:
- `results/travel_2026-12-31.json` (원본 데이터)
- `results/travel_2026-12-31.md` (최종 리포트)

---

## 3. 과제 목표 달성 설명


| 목표 | 프로젝트에서의 구현 근거 |
|---|---|
| **REST API 요청/응답, GET/POST 차이** | LLM 호출은 `POST`(본문에 프롬프트), 맛집 검색은 `GET`(쿼리 파라미터) |
| **LLM 출력 → JSON 구조화 → 다음 단계 입력** | 1차 추천을 JSON으로 파싱 → `recommended_cities`를 맛집 검색 입력으로 연결 |
| **API 대표 오류 대응** (인증/쿼터/네트워크/파싱) | `try-except`로 분기, 오류를 `errors` 리스트에 기록 후 리포트에 요약 |
| **.env로 키 관리하는 이유** | 키 노출 방지·교체 용이·과금 사고 예방 → `.gitignore`로 `.env` 제외 |

---

## 4. 기능 요구 사항 충족 설명

| 요구 사항 | 구현 내용 |
|---|---|
| **CLI (argparse)** | `main.py`에서 `--date` 필수 옵션 파싱, 잘못된 형식 시 사용법 출력 후 종료 |
| **날짜 형식 검증** | `YYYY-MM-DD` 형식 검증 (예: `2026-13-99` 입력 시 오류 안내) |
| **LLM API (택1)** | ✅ **Google Gemini** (`gemini-2.5-flash`) |
| **지도 API (택1)** | ✅ **Kakao Local** (키워드 기반 맛집 검색) |
| **1차 JSON 스키마** | `recommended_cities`, `weather`, `events[]`, `reason` 포함 |
| **맛집 검색** | 추천 도시 기준 맛집 검색, 필드: `name/address/category/url/x/y` |
| **검색 0건 처리** | 중단 없이 "데이터 없음"으로 다음 단계 진행 |
| **최종 리포트** | 추천지역·이유·날씨·행사·맛집·1일 일정 포함 |
| **에러 처리** | 키 미설정 즉시 종료 / 지도 실패 시 리포트 계속 / JSON 파싱 실패 시 **재시도 1회** |
| **결과 저장** | `results/`에 JSON(추천+맛집+errors) & MD 저장 |

### 검증용 시연 명령어

**① 잘못된 날짜 형식 검증**

```bash
python main.py --date "2026-99-99"
```


**② 인자 없이 실행 시 사용법 출력 확인**

```bash
python main.py
```


---

## 5. 보너스 과제 구현 여부

| 보너스 | 구현 | 설명 |
|---|:---:|---|
| **복수 지역 추천** | ✅ | `recommended_cities`로 2~3개 도시 추천 → 도시별 맛집 검색·정리 |
| **결과 캐싱** | ✅ | 같은 `--date` 재실행 시 저장된 JSON이 있으면 API 호출을 건너뛰고 리포트 재생성 |
| **(개인) Streamlit 웹 GUI** | ✅ | `streamlit run app.py` — 날짜별 리포트·맛집 지도·카카오맵 링크 표시 |

### 캐싱 시연

```bash
python main.py --date "2026-12-31"
```

→ **API를 호출하지 않고** 기존 JSON을 재사용하는 로그 확인
→ "외부 API 비용/속도 최적화"를 구현했음을 증명

### 웹 GUI 시연 (개인적인 선택, 브라우저 열림)

```bash
streamlit run app.py
```


---

## 6. 개발 환경 & 제약 사항 준수

### 개발 환경

| 항목 | 준수 여부 |
|---|:---:|
| Python 3.10 이상 | ✅ |
| 터미널 실행 가능 (CLI) | ✅ (`python main.py --date ...`) |

### 제약 사항 (보안 — 필수)

| 항목 | 준수 여부 | 근거 |
|---|:---:|---|
| API 키를 코드/README/결과물에 직접 작성 안 함 | ✅ | 모든 키는 `.env`에서 로드 |
| `.env` / 환경변수 사용 | ✅ | `python-dotenv`로 로드 |
| `.env`를 Git에서 제외 | ✅ | `.gitignore`에 `.env` 등록 (GitHub 미노출) |
| 키 설정 예시 제공 | ✅ | `.env.example` 파일로 형식만 안내 |

### 운영 안정성 (권장)

| 항목 | 준수 여부 |
|---|:---:|
| 키 미설정 시 즉시 종료 + 안내 | ✅ |
| 지도 API 실패 시에도 리포트 생성 진행 | ✅ |
| LLM JSON 파싱 실패 시 재시도 **최대 1회** | ✅ |

---

## 📎 부록: API 키 설정 방법 (평가자용)

```bash
# 1) .env.example을 복사해 .env 생성
cp .env.example .env      # Windows PowerShell: Copy-Item .env.example .env

# 2) .env 파일에 본인 키 입력
GEMINI_API_KEY=여기에_Gemini_키
KAKAO_REST_API_KEY=여기에_Kakao_키
```

> 상세 설정은 `README.md`를 참고하세요.

---

**저장소:** https://github.com/geunwa/travel_project