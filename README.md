# Gemini + Kakao 국내 여행 추천 프로그램

## 1. 프로그램 개요

이 프로그램은 Google Gemini API와 Kakao Local API를 활용하여  
사용자가 입력한 여행 날짜에 맞는 국내 도시를 추천하고  
맛집 정보와 함께 여행 리포트를 자동 생성하는 Python CLI 프로그램입니다.

---

## 2. 주요 기능

- Gemini LLM으로 날짜 기반 국내 도시 추천 (날씨, 행사, 추천 이유 포함)
- Kakao Local API로 추천 도시 맛집 검색 (최대 5곳)
- Gemini LLM으로 Markdown 형식 여행 리포트 자동 생성
- `results/` 폴더에 JSON 원본 데이터 + Markdown 리포트 저장
- 같은 날짜 재실행 시 캐시 재사용 (API 호출 생략)
- LLM 응답 파싱 실패 시 1회 재시도 후 기본값 반환
- LLM 리포트 생성 실패 시 폴백 리포트 자동 조립
- 실행 중 발생한 오류를 누적하여 리포트 하단에 기록

---

## 3. 사용 기술

- Python 3.10+
- google-genai (Gemini 3.6 Flash)   ← 2.5 → 3.6 으로 변경
- requests (Kakao Local API)
- python-dotenv

---

## 4. 파일 구성

    travel_project/
    ├─ main.py          # CLI 진입점 (argparse, 파이프라인 실행)
    ├─ utils.py         # API 호출, 파싱, 저장 함수 모음
    ├─ README.md        # 프로젝트 설명 및 실행 방법
    ├─ requirements.txt # 필요한 라이브러리 목록
    ├─ .env             # API 키 설정 파일 (직접 생성, 제출 제외)
    ├─ .env.example     # API 키 형식 예시
    ├─ .gitignore       # .env, results/ 등 제외 목록
    └─ results/         # 실행 결과 저장 폴더 (자동 생성)
        ├─ 2025-03-15.json
        └─ 2025-03-15.md

### 파일 설명

- `main.py` : CLI 인자 파싱, API 키 로드, 3단계 파이프라인 실행
- `utils.py` : LLM 추천 생성, 맛집 검색, 리포트 생성, 결과 저장, 캐시 로드
- `README.md` : 프로젝트 설명 및 실행 방법
- `requirements.txt` : 필요한 라이브러리 목록
- `.env.example` : API 키 입력 형식을 보여주는 예시 파일

---

## 5. 실행 방법

### 1) 프로젝트 폴더로 이동

    cd travel_project

### 2) 필요한 라이브러리 설치

    pip install -r requirements.txt

### 3) API 키 설정

`.env.example` 파일을 참고하여 `.env` 파일을 직접 생성합니다.

`.env` 파일 예시:

    GEMINI_API_KEY=발급받은_Gemini_키
    KAKAO_REST_API_KEY=발급받은_Kakao_REST_키

### 4) 프로그램 실행

    python main.py --date "YYYY-MM-DD"

실행 예시:

    python main.py --date "2025-03-15"

---

## 6. API 키 발급 방법

### Gemini API 키

1. [Google AI Studio](https://aistudio.google.com/) 접속
2. 로그인 후 **Get API Key** 클릭
3. 발급받은 키를 `.env`의 `GEMINI_API_KEY`에 입력

### Kakao REST API 키

1. [Kakao Developers](https://developers.kakao.com/) 접속
2. 로그인 후 **내 애플리케이션 > 애플리케이션 추가**
3. **앱 키 > REST API 키** 복사
4. 발급받은 키를 `.env`의 `KAKAO_REST_API_KEY`에 입력

### 주의사항

- 실제 API 키가 들어 있는 `.env` 파일은 제출하지 않습니다.
- 제출용으로는 `.env.example` 파일만 포함하는 것을 권장합니다.

제출용 `.env.example` 예시:

    GEMINI_API_KEY=YOUR_GEMINI_API_KEY
    KAKAO_REST_API_KEY=YOUR_KAKAO_REST_API_KEY

---

## 7. 실행 예시

### 명령어

    python main.py --date "2025-03-15"

### 터미널 출력

    [1/3] 1차 추천 생성 중(LLM)...
      - recommended_city: "경주"
    [2/3] 맛집 검색 중(지도/장소 API)...
      - 맛집 5곳 검색 완료
    [3/3] 최종 리포트 생성 중(LLM)...
      - 리포트 생성 완료

    완료! results/2025-03-15.md 를 확인하세요.
    원본 데이터: results/2025-03-15.json

### 캐시 재사용 시 (같은 날짜 재실행)

    [캐시] 2025-03-15 원본 데이터가 존재하여 재사용합니다.
    [1/3] (캐시) 추천 도시: 경주
    [2/3] (캐시) 맛집 5곳 로드 완료
    [3/3] 최종 리포트 생성 중(LLM)...
      - 리포트 생성 완료

    완료! results/2025-03-15.md 를 확인하세요.
    원본 데이터: results/2025-03-15.json

---

## 8. 결과물 확인 방법

실행 후 `results/` 폴더에 두 파일이 생성됩니다.

| 파일 | 내용 |
|------|------|
| `YYYY-MM-DD.json` | 추천 데이터, 맛집 목록, 오류 기록 원본 |
| `YYYY-MM-DD.md` | 최종 여행 리포트 (Markdown) |

### 리포트 포함 섹션

- 추천 지역
- 추천 이유
- 날씨 요약
- 행사/축제
- 맛집 추천
- 1일 일정 제안
- 오류 요약

---

## 9. 예외 처리 내용

| 상황 | 처리 방식 |
|------|----------|
| API 키 미설정 | 즉시 종료 + 설정 방법 안내 |
| 날짜 형식 오류 | 즉시 종료 + 올바른 형식 안내 |
| LLM JSON 파싱 실패 | strict 프롬프트로 1회 재시도 |
| LLM 2회 모두 실패 | 기본값 반환 + errors 기록 |
| Kakao 인증 실패 | errors 기록 후 다음 단계 진행 |
| Kakao 검색 결과 0건 | errors 기록 후 다음 단계 진행 |
| 네트워크 타임아웃 | errors 기록 후 다음 단계 진행 |
| LLM 리포트 생성 실패 | 폴백 리포트 자동 조립 후 저장 |

---

## 10. 과제 요구사항 반영 내용

- 외부 API 2종 활용 (Gemini, Kakao Local)
- Python CLI 프로그램 구현 (argparse)
- `requests` 라이브러리 사용
- `.env` 파일을 통한 API 키 분리
- CLI 인자 입력 및 검증
- JSON 응답 파싱 + 재시도 로직
- Markdown 리포트 자동 생성 및 파일 저장
- 단계별 예외 처리 + 오류 누적 기록
- 함수 분리를 통한 코드 구조화 (utils.py)
- 캐싱으로 불필요한 API 호출 방지

---

## 11. 제출 안내

제출 시 포함하는 파일:

- `main.py`
- `utils.py`
- `README.md`
- `requirements.txt`
- `.env.example`

### 주의

- 실제 API 키가 포함된 `.env` 파일은 제출하지 않습니다.
- `results/` 폴더는 제출하지 않아도 됩니다 (실행 시 자동 생성).
- 제출 전 `python main.py --date "2025-03-15"` 로 정상 실행되는지 확인합니다.

---

## 12. 작성자

- 이름: 조근화