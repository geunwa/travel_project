import json
import re
import time
from pathlib import Path

import requests
from google import genai
from google.genai import types

# ─── 경로/상수 ───────────────────────────────────────────────
# 실행 위치와 무관하게 프로젝트 폴더 기준으로 results/ 사용
BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"

REQUIRED_KEYS = {"recommended_cities", "weather", "events", "reason"}
GEMINI_MODEL = "gemini-flash-latest"

_NO_AFC = types.GenerateContentConfig(
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
)


# ─── 오류 분류 ───────────────────────────────────────────────
# errors 항목 구조: {"step", "type", "status", "message"}
#   type   : AUTH_ERROR / QUOTA_ERROR / SERVER_ERROR / NETWORK_ERROR /
#            PARSE_ERROR / EMPTY_RESULT / UNKNOWN_ERROR
#   status : retry(재시도함) / failed(최종 실패) / empty(0건)
ERROR_HINTS = {
    "AUTH_ERROR": "인증 실패. API 키 값·키 종류·권한 설정을 확인하세요",
    "QUOTA_ERROR": "쿼터 초과(429). 잠시 후 다시 시도하세요",
    "SERVER_ERROR": "서버 오류(5xx). 일시적 장애일 수 있습니다",
    "NETWORK_ERROR": "네트워크 오류(연결 실패/시간 초과)",
    "PARSE_ERROR": "응답 파싱 실패(JSON 형식/필수 키 불일치)",
    "EMPTY_RESULT": "검색 결과 0건",
    "UNKNOWN_ERROR": "알 수 없는 오류",
}


class ParseError(ValueError):
    """LLM 응답을 JSON으로 파싱하지 못했거나 스키마 검증에 실패한 경우."""


def classify_error(e: Exception) -> str:
    """예외를 오류 유형 문자열로 분류한다."""
    # HTTP 상태 코드: requests는 e.response.status_code, google-genai는 e.code
    status = None
    response = getattr(e, "response", None)
    if response is not None and hasattr(response, "status_code"):
        status = response.status_code
    if status is None and isinstance(getattr(e, "code", None), int):
        status = e.code

    if status in (401, 403):
        return "AUTH_ERROR"
    if status == 429:
        return "QUOTA_ERROR"
    if status is not None and status >= 500:
        return "SERVER_ERROR"
    if isinstance(e, (requests.ConnectionError, requests.Timeout)):
        return "NETWORK_ERROR"
    if isinstance(e, (json.JSONDecodeError, ParseError)):
        return "PARSE_ERROR"
    return "UNKNOWN_ERROR"


def _add_error(errors: list, step: str, err_type: str, status: str, message: str, **extra) -> dict:
    item = {"step": step, "type": err_type, "status": status, "message": message, **extra}
    errors.append(item)
    return item


def format_errors_md(errors: list) -> str:
    """리포트의 '오류 요약' 섹션 본문."""
    if not errors:
        return "- 없음"
    return "\n".join(
        f"- {e.get('step', '')} | {e.get('type', '')} | {e.get('status', '')} | {e.get('message', '')}"
        for e in errors
    )


# ─── 키워드 전처리 ───────────────────────────────────────────
# 긴 접미사부터 검사해야 "광역시"가 "시"보다 먼저 매칭된다.
_CITY_SUFFIXES = ("특별자치시", "특별자치도", "광역시", "특별시", "시", "군", "구")
# '도'가 행정구역이 아니라 섬을 뜻하는 지명의 표준 표기
_CITY_ALIASES = {"제주도": "제주", "거제도": "거제", "강화도": "강화", "울릉도": "울릉"}


def normalize_city_keyword(city) -> str:
    """도시명 전처리: 괄호·특수문자 제거 → 첫 단어 → 별칭 매핑 → 행정구역 접미사 제거.

    접미사를 떼고도 2글자 이상 남을 때만 제거한다(대구, 양구, 중구 보호).

    예시:
        "경주시" -> "경주"        "부산광역시" -> "부산"
        "제주(제주시)" -> "제주"  "제주특별자치도" -> "제주"
        "대구" -> "대구"          "제주도" -> "제주"
    """
    city = re.sub(r"[\(\)\[\]·,/]", " ", str(city))
    city = re.sub(r"\s+", " ", city).strip()
    if not city:
        return ""
    city = city.split(" ")[0]
    city = _CITY_ALIASES.get(city, city)

    for suffix in _CITY_SUFFIXES:
        if city.endswith(suffix) and len(city) - len(suffix) >= 2:
            return city[: -len(suffix)]
    return city


# ─── 공통 헬퍼 ───────────────────────────────────────────────
def _ensure_results_dir() -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULTS_DIR


def _extract_json_from_text(text: str) -> dict:
    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text or "")
    if code_block:
        candidate = code_block.group(1).strip()
    else:
        brace_match = re.search(r"\{[\s\S]*\}", text or "")
        candidate = brace_match.group(0).strip() if brace_match else (text or "").strip()
    return json.loads(candidate)


def _validate_recommendation(data) -> list[str]:
    """1차 추천 JSON 검증. 문제 목록을 반환(빈 리스트면 통과)."""
    if not isinstance(data, dict):
        return [f"최상위가 객체가 아님({type(data).__name__})"]

    problems = []
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        problems.append(f"필수 키 누락: {sorted(missing)}")

    cities = data.get("recommended_cities")
    if "recommended_cities" in data:
        if not isinstance(cities, list) or not cities:
            problems.append("recommended_cities: 비어 있지 않은 배열이어야 함")
        elif not all(isinstance(c, str) and c.strip() for c in cities):
            problems.append("recommended_cities: 모든 원소가 문자열이어야 함")

    for key in ("weather", "reason"):
        if key in data and not (isinstance(data[key], str) and data[key].strip()):
            problems.append(f"{key}: 비어 있지 않은 문자열이어야 함")

    events = data.get("events")
    if "events" in data and not (isinstance(events, list) and all(isinstance(e, str) for e in events)):
        problems.append("events: 문자열 배열이어야 함")

    return problems


def _to_float(value):
    """좌표 문자열을 float로 변환, 실패 시 None 반환."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ─── [1/3] LLM 1차 추천 ──────────────────────────────────────
def generate_city_recommendation(date_text: str, api_key: str, errors: list) -> dict:
    """Gemini로 날짜 기반 국내 도시 2~3곳 추천. 실패 시 1회만 재시도.

    반환: {"recommended_city": str, "recommended_cities": [str],
           "weather": str, "events": [str], "reason": str}
    재시도 후에도 실패하면 errors에 status="failed"를 남기고 기본값을 반환한다.
    """
    client = genai.Client(api_key=api_key)

    schema_text = """{
    "recommended_cities": ["도시1", "도시2", "도시3"],
    "weather": "해당 시기 일반적인 날씨 요약(문자열)",
    "events": ["행사/축제1", "행사/축제2"],
    "reason": "추천 근거 2~4문장(문자열)"
}"""

    prompt = f"""당신은 여행 전문가입니다.
{date_text} 날짜를 기준으로 국내에서 여행하기 좋은 도시 2~3곳을 추천해주세요.

규칙:
- recommended_cities: 도시명 문자열 2~3개 (예: "제주", "강릉")
- events: 행사/축제 후보 1~3개
- reason: 2~4문장

반드시 아래 JSON 형식으로만 답변하세요.
```json
{schema_text}
```"""

    strict_prompt = f"""반드시 JSON 객체 하나만 출력하세요. 설명·코드블록·다른 텍스트는 절대 포함하지 마세요.
필수 키 4개(recommended_cities, weather, events, reason)를 모두 포함하세요.
{date_text} 날짜 기준 국내 여행 도시 2~3곳 추천:
{schema_text}"""

    last_type = "UNKNOWN_ERROR"
    for attempt, p in enumerate([prompt, strict_prompt], start=1):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL, contents=p, config=_NO_AFC
            )
            try:
                data = _extract_json_from_text(response.text)
            except json.JSONDecodeError as e:
                raise ParseError(f"JSON 파싱 실패: {e}") from e

            problems = _validate_recommendation(data)
            if problems:
                raise ParseError("; ".join(problems))

            # 정리: 공백 제거, 중복 제거, 최대 3개
            cities = list(dict.fromkeys(c.strip() for c in data["recommended_cities"]))[:3]
            data["recommended_cities"] = cities
            data["recommended_city"] = cities[0]          # 필수 스키마(단수) 병기
            data["events"] = data["events"][:3]
            return data

        except Exception as e:
            last_type = classify_error(e)
            _add_error(errors, "recommendation", last_type, "retry",
                       f"LLM 시도 {attempt} 실패: {e}")

    _add_error(errors, "recommendation", last_type, "failed",
               "재시도 1회 후에도 실패하여 기본값을 사용했습니다")
    return {
        "recommended_city": "서울",
        "recommended_cities": ["서울"],
        "weather": "정보 없음",
        "events": [],
        "reason": "LLM 응답 실패로 기본값을 사용했습니다.",
    }


# ─── [2/3] 지도/장소 검색 ────────────────────────────────────
class PlaceSearchProvider:
    """지도/장소 검색 제공자 공통 인터페이스.

    다른 제공자(예: Naver Local)로 교체할 때는 이 클래스를 상속해 search()만 구현한다.
    search() 계약:
      입력: keyword(str), size(int)
      출력: [{"name", "address", "category", "phone", "url", "x", "y"}] (0건이면 [])
      실패: 예외를 그대로 발생시킨다(분류·기록은 search_restaurants가 담당).
    """

    name = "base"

    def search(self, keyword: str, size: int) -> list[dict]:
        raise NotImplementedError


class KakaoLocalProvider(PlaceSearchProvider):
    """Kakao Local 키워드 검색 (GET, 헤더 Authorization: KakaoAK {키})."""

    name = "kakao"
    URL = "https://dapi.kakao.com/v2/local/search/keyword.json"

    def __init__(self, api_key: str):
        self._headers = {"Authorization": f"KakaoAK {api_key}"}

    def search(self, keyword: str, size: int) -> list[dict]:
        params = {"query": keyword, "size": size, "category_group_code": "FD6"}
        response = requests.get(self.URL, headers=self._headers, params=params, timeout=10)
        response.raise_for_status()
        documents = response.json().get("documents", [])
        return [
            {
                "name": doc.get("place_name", ""),
                "address": doc.get("road_address_name") or doc.get("address_name", ""),
                "category": doc.get("category_name", ""),
                "phone": doc.get("phone", ""),
                "url": doc.get("place_url", ""),
                "x": _to_float(doc.get("x")),   # 경도 (longitude)
                "y": _to_float(doc.get("y")),   # 위도 (latitude)
            }
            for doc in documents
        ]


def search_restaurants(city: str, provider: PlaceSearchProvider, errors: list, size: int = 5) -> list[dict]:
    """한 도시의 맛집 검색. 실패·0건이면 errors에 기록하고 [] 반환(프로그램은 계속 진행)."""
    keyword = normalize_city_keyword(city)
    query = f"{keyword} 맛집"
    try:
        if not keyword:
            raise ParseError(f"검색 키워드가 비어 있음 (city={city!r})")
        restaurants = provider.search(query, size)
    except Exception as e:
        err_type = classify_error(e)
        _add_error(errors, "place_search", err_type, "failed",
                   f"{provider.name} 오류: {e}", city=city, query=query)
        return []

    if not restaurants:
        _add_error(errors, "place_search", "EMPTY_RESULT", "empty",
                   f"0 results for query={query}", city=city, query=query)
    return restaurants


def search_restaurants_by_cities(
    cities: list[str], provider: PlaceSearchProvider, errors: list, size: int = 5
) -> dict[str, list]:
    """여러 도시를 순회하며 {도시: [맛집 리스트]} 반환."""
    return {city: search_restaurants(city, provider, errors, size) for city in cities}


# ─── [3/3] LLM 최종 리포트 ───────────────────────────────────
def empty_reason(city: str, errors: list) -> str:
    """맛집이 비어 있는 도시의 '데이터 없음' 사유(검색 실패와 0건을 구분)."""
    err = next((e for e in reversed(errors)
                if e.get("step") == "place_search" and e.get("city") == city), None)
    if err and err.get("status") == "failed":
        return f"데이터 없음 (검색 실패: {err.get('type', 'UNKNOWN_ERROR')})"
    return "데이터 없음 (장소 검색 결과 0건)"


def _restaurants_block_md(cities: list, restaurants_by_city: dict, errors: list) -> str:
    """폴백 리포트용 도시별 맛집 Markdown."""
    lines = []
    for city in cities:
        lines.append(f"### {city}")
        rlist = restaurants_by_city.get(city, [])
        if not rlist:
            lines.append(f"- {empty_reason(city, errors)}")
        for i, r in enumerate(rlist, 1):
            name = f"[{r['name']}]({r['url']})" if r.get("url") else r.get("name", "")
            lines.append(f"{i}. {name}")
            lines.append(f"   - {r.get('address', '')} | {r.get('category', '')}")
        lines.append("")
    return "\n".join(lines).rstrip()


def _schedule_block_md(cities: list, restaurants_by_city: dict) -> str:
    """폴백 리포트용 기본 1일 일정(검색된 맛집 이름 활용)."""
    lines = ["(LLM 리포트 생성 실패로 기본 일정 템플릿을 제공합니다)", ""]
    for city in cities:
        rlist = restaurants_by_city.get(city, [])
        lunch = rlist[0]["name"] if len(rlist) > 0 else "현지 식당"
        dinner = rlist[1]["name"] if len(rlist) > 1 else "현지 식당"
        lines += [
            f"### {city}",
            f"- 오전: {city} 대표 명소 둘러보기",
            f"- 오후: 점심 '{lunch}' 후 주변 산책·행사 방문",
            f"- 저녁: 저녁 '{dinner}' 후 일정 마무리",
            "",
        ]
    return "\n".join(lines).rstrip()


def _fallback_report(date_text, cities, weather, events, reason, restaurants_by_city, errors) -> str:
    return f"""# {date_text} 국내 여행 추천 리포트

## 1. 추천 지역
{", ".join(cities) if cities else "정보 없음"}

## 2. 추천 이유
{reason or "정보 없음"}

## 3. 날씨 요약
{weather or "정보 없음"}

## 4. 행사/축제
{chr(10).join(f"- {e}" for e in events) if events else "- 없음"}

## 5. 도시별 맛집 추천
{_restaurants_block_md(cities, restaurants_by_city, errors)}

## 6. 도시별 1일 일정 제안
{_schedule_block_md(cities, restaurants_by_city)}

## 7. 오류 요약
{format_errors_md(errors)}
"""


def generate_final_report(
    date_text: str,
    recommendation: dict,
    restaurants_by_city: dict,
    errors: list,
    api_key: str,
) -> str:
    """Gemini로 최종 Markdown 리포트 생성.

    일시 오류(5xx/네트워크/쿼터)는 1회만 재시도하고, 그래도 실패하면
    맛집 데이터를 그대로 담은 폴백 리포트를 반환한다.
    '오류 요약' 섹션은 LLM이 아니라 코드가 항상 마지막에 붙인다.
    """
    client = genai.Client(api_key=api_key)

    cities = recommendation.get("recommended_cities", [])
    weather = recommendation.get("weather", "")
    events = recommendation.get("events", [])
    reason = recommendation.get("reason", "")

    cities_block = ""
    for city in cities:
        rlist = restaurants_by_city.get(city, [])
        cities_block += f"\n### {city}\n"
        if rlist:
            for i, r in enumerate(rlist, 1):
                cities_block += (
                    f"{i}. {r['name']} - {r['address']} ({r['category']}) "
                    f"[url:{r.get('url', '')}]\n"
                )
        else:
            cities_block += f"- {empty_reason(city, errors)}\n"

    prompt = f"""당신은 여행 작가입니다.
아래 정보를 바탕으로 {date_text} 국내 여행 리포트를 Markdown 형식으로 작성해주세요.
첫 줄은 반드시 "# {date_text} 국내 여행 추천 리포트" 로 시작하세요.

추천 도시 목록: {', '.join(cities)}
날씨: {weather}
행사/축제: {', '.join(events) if events else '없음'}
추천 이유: {reason}

도시별 맛집 목록 (각 항목의 [url:...]은 해당 맛집의 카카오맵 링크입니다):
{cities_block}

다음 6개 섹션만 이 순서와 번호로 작성하세요:
## 1. 추천 지역 (아래 도시명을 그대로 사용: {', '.join(cities)})
## 2. 추천 이유
## 3. 날씨 요약
## 4. 행사/축제
## 5. 도시별 맛집 추천 (도시마다 ### 소제목, 목록에 '데이터 없음 (...)'으로 적힌 도시는 괄호 안 사유까지 그대로 표기)
## 6. 도시별 1일 일정 제안 (도시마다 오전/오후/저녁)

'오류 요약' 섹션은 작성하지 마세요. 프로그램이 자동으로 추가합니다.

맛집 출력 규칙(중요):
- 각 맛집의 이름은 반드시 마크다운 링크 형식 [맛집이름](카카오맵url) 으로 작성하세요.
- 카카오맵url은 위 목록의 [url:...] 안에 있는 주소를 사용하세요.
- url이 비어 있으면 링크 없이 이름만 출력하세요.
- 링크 아래 줄에 주소와 카테고리를 함께 표기하세요.
- 목록에 없는 맛집을 지어내지 마세요.

주의: 반드시 위 날짜({date_text})의 계절에 맞는 내용만 작성하세요."""

    for attempt in (1, 2):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL, contents=prompt, config=_NO_AFC
            )
            text = (response.text or "").rstrip()
            if not text:
                raise ParseError("빈 응답")
            return text + f"\n\n## 7. 오류 요약\n{format_errors_md(errors)}\n"
        except Exception as e:
            err_type = classify_error(e)
            transient = err_type in ("SERVER_ERROR", "NETWORK_ERROR", "QUOTA_ERROR")
            if attempt == 1 and transient:
                _add_error(errors, "report", err_type, "retry", f"리포트 생성 시도 1 실패: {e}")
                time.sleep(3)
                continue
            _add_error(errors, "report", err_type, "failed", f"리포트 생성 실패: {e}")
            break

    # 오류를 추가한 뒤에 폴백을 만들어야 리포트 실패도 오류 요약에 포함된다
    return _fallback_report(date_text, cities, weather, events, reason, restaurants_by_city, errors)


# ─── 저장/캐시 ───────────────────────────────────────────────
def _raw_json_path(date_text: str) -> Path:
    """원본 데이터 JSON 경로. 예: results/travel_2025-03-15.json"""
    return RESULTS_DIR / f"travel_{date_text}.json"


def _report_md_path(date_text: str) -> Path:
    """리포트 Markdown 경로. 예: results/travel_2025-03-15.md"""
    return RESULTS_DIR / f"travel_{date_text}.md"


def _display_path(path: Path) -> str:
    """콘솔 표시용 경로(프로젝트 기준 상대 경로)."""
    try:
        return str(path.relative_to(BASE_DIR))
    except ValueError:
        return str(path)


def save_results(
    date_text: str,
    recommendation: dict,
    restaurants_by_city: dict,
    report: str,
    errors: list,
) -> dict:
    """리포트(.md)와 원본 데이터(.json)를 results/에 저장(같은 날짜는 덮어씀)하고 경로 반환."""
    _ensure_results_dir()

    md_path = _report_md_path(date_text)
    json_path = _raw_json_path(date_text)

    md_path.write_text(report, encoding="utf-8")

    raw_data = {
        "date_text": date_text,
        "recommendation": recommendation,
        "restaurants_by_city": restaurants_by_city,
        "errors": errors,
    }
    json_path.write_text(json.dumps(raw_data, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"md_path": _display_path(md_path), "json_path": _display_path(json_path)}


def load_cached_raw(date_text: str) -> dict | None:
    """같은 날짜의 원본 JSON이 있으면 dict로 반환, 없거나 손상되면 None."""
    json_path = _raw_json_path(date_text)
    if not json_path.exists():
        return None
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_cached_report(date_text: str) -> str | None:
    """같은 날짜의 리포트 md가 있으면 문자열로 반환, 없으면 None."""
    md_path = _report_md_path(date_text)
    if not md_path.exists():
        return None
    try:
        return md_path.read_text(encoding="utf-8")
    except Exception:
        return None
