import json
import re
import requests
from pathlib import Path
from datetime import datetime
from google import genai
from google.genai import types

# ─── 키워드 전처리 ───────────────────────────────────────────
# 시/군/구 등 행정구역 접미사 제거 (광역단위 도/특별시/광역시는 그대로 둠)
# 긴 접미사부터 검사해야 "특별자치시"가 "시"보다 먼저 매칭됨
_CITY_SUFFIXES = ("특별자치시", "시", "군", "구")


def normalize_city_keyword(city: str) -> str:
    """도시명 전처리: 괄호·특수문자 제거 + 시/군/구 접미사 제거.

    Kakao 검색 정확도를 높이기 위한 전처리이며, 전국 모든 지명에
    일관된 규칙을 적용한다(특정 도시 하드코딩 없음).

    예시:
        "경주시"        -> "경주"
        "제주(제주시)"   -> "제주"
        "전주·한옥마을"  -> "전주"
        "제주특별자치도" -> "제주특별자치도" (광역단위는 유지, Kakao가 처리)
    """
    city = re.sub(r"[\(\)\[\]·]", " ", city)   # 괄호·중점 제거
    city = re.sub(r"\s+", " ", city).strip()    # 연속 공백 정리
    city = city.split(" ")[0]                    # 첫 단어만 사용

    # 접미사 제거 (제거 후에도 글자가 남을 때만)
    for suffix in _CITY_SUFFIXES:
        if city.endswith(suffix) and len(city) > len(suffix):
            return city[: -len(suffix)]

    return city
# ─────────────────────────────────────────────────────────────


RESULTS_DIR = Path("results")
REQUIRED_KEYS = {"recommended_cities", "weather", "events", "reason"}
GEMINI_MODEL = "gemini-flash-latest"

_NO_AFC = types.GenerateContentConfig(
    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
)


def _ensure_results_dir() -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULTS_DIR


def _extract_json_from_text(text: str) -> dict:
    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if code_block:
        candidate = code_block.group(1).strip()
    else:
        brace_match = re.search(r"\{[\s\S]*\}", text)
        candidate = brace_match.group(0).strip() if brace_match else text.strip()
    return json.loads(candidate)


def _validate_recommendation(data: dict) -> bool:
    if not REQUIRED_KEYS.issubset(data.keys()):
        return False
    cities = data.get("recommended_cities")
    return isinstance(cities, list) and len(cities) > 0


def _to_float(value):
    """좌표 문자열을 float로 변환, 실패 시 None 반환."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def generate_city_recommendation(date_text: str, api_key: str, errors: list) -> dict:
    """Gemini LLM으로 날짜 기반 국내 도시 2~3곳 추천. 파싱 실패 시 1회 재시도."""
    client = genai.Client(api_key=api_key)

    prompt = f"""당신은 여행 전문가입니다.
{date_text} 날짜를 기준으로 국내에서 여행하기 좋은 도시 2~3곳을 추천해주세요.

반드시 아래 JSON 형식으로만 답변하세요.
```json
{{
    "recommended_cities": ["도시1", "도시2", "도시3"],
    "weather": "해당 시기 전반적인 날씨 설명",
    "events": ["행사1", "행사2"],
    "reason": "추천 이유"
}}
```"""

    strict_prompt = f"""반드시 JSON만 출력하세요. 다른 텍스트는 절대 포함하지 마세요.
{date_text} 날짜 기준 국내 여행 도시 2~3곳 추천:
{{
    "recommended_cities": ["도시1", "도시2", "도시3"],
    "weather": "해당 시기 전반적인 날씨 설명",
    "events": ["행사1", "행사2"],
    "reason": "추천 이유"
}}"""

    for attempt, p in enumerate([prompt, strict_prompt], start=1):
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=p,
                config=_NO_AFC,
            )
            data = _extract_json_from_text(response.text)
            if _validate_recommendation(data):
                data["recommended_cities"] = data["recommended_cities"][:3]
                return data
            raise ValueError(f"필수 키 누락 또는 도시 목록 비어있음: {data}")
        except Exception as e:
            errors.append({
                "step": "recommendation",
                "status": "retry",
                "message": f"LLM 시도 {attempt} 실패: {e}",
            })

    return {
        "recommended_cities": ["서울"],
        "weather": "정보 없음",
        "events": [],
        "reason": "LLM 응답 파싱 실패로 기본값 사용",
    }


def search_restaurants(city: str, api_key: str, errors: list, size: int = 5) -> list[dict]:
    """Kakao Local API로 특정 도시 맛집 검색."""
    url = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {api_key}"}
    keyword = normalize_city_keyword(city)
    params = {
        "query": f"{keyword} 맛집",
        "size": size,
        "category_group_code": "FD6",
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        documents = response.json().get("documents", [])

        if not documents:
            errors.append({
                "step": "restaurant",
                "status": "empty",
                "message": f"Kakao 검색 결과 0건 (city={city})",
            })
            return []

        restaurants = []
        for doc in documents:
            restaurants.append({
                "name": doc.get("place_name", ""),
                "address": doc.get("road_address_name") or doc.get("address_name", ""),
                "category": doc.get("category_name", ""),
                "phone": doc.get("phone", ""),
                "url": doc.get("place_url", ""),
                "x": _to_float(doc.get("x")),   # 경도 (longitude)
                "y": _to_float(doc.get("y")),   # 위도 (latitude)
            })
        return restaurants

    except Exception as e:
        errors.append({
            "step": "restaurant",
            "status": "failed",
            "message": f"Kakao API 오류 (city={city}): {e}",
        })
        return []


def search_restaurants_by_cities(
    cities: list[str], api_key: str, errors: list, size: int = 5
) -> dict[str, list]:
    """여러 도시를 순회하며 맛집을 검색해 {도시: [맛집리스트]} 반환."""
    result: dict[str, list] = {}
    for city in cities:
        result[city] = search_restaurants(
            city=city, api_key=api_key, errors=errors, size=size
        )
    return result


def generate_final_report(
    date_text: str,
    recommendation: dict,
    restaurants_by_city: dict,
    errors: list,
    api_key: str,
) -> str:
    """Gemini LLM으로 지역별 최종 Markdown 여행 리포트 생성. 실패 시 폴백 리포트 반환."""
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
                url = r.get("url", "")
                # url을 함께 넘겨 LLM이 마크다운 링크로 렌더링하도록 유도
                cities_block += (
                    f"{i}. {r['name']} - {r['address']} ({r['category']}) "
                    f"[url:{url}]\n"
                )
        else:
            cities_block += "- 데이터 없음 (장소 검색 결과 0건)\n"

    prompt = f"""당신은 여행 작가입니다.
아래 정보를 바탕으로 {date_text} 국내 여행 리포트를 Markdown 형식으로 작성해주세요.

추천 도시 목록: {', '.join(cities)}
날씨: {weather}
행사/축제: {', '.join(events) if events else '없음'}
추천 이유: {reason}

도시별 맛집 목록 (각 항목의 [url:...]은 해당 맛집의 카카오맵 링크입니다):
{cities_block}

다음 섹션을 반드시 포함해주세요:
1. 추천 지역 (아래 도시명을 그대로 사용: {', '.join(cities)})
2. 추천 이유
3. 날씨 요약
4. 행사/축제
5. 도시별 맛집 추천 (도시마다 소제목으로 구분, 0건이면 '데이터 없음'으로 표기)
6. 도시별 1일 일정 제안 (각 도시별로 오전/오후/저녁 수준)

맛집 출력 규칙(중요):
- 각 맛집의 이름은 반드시 마크다운 링크 형식 [맛집이름](카카오맵url) 으로 작성하세요.
- 카카오맵url은 위 목록의 [url:...] 안에 있는 주소를 사용하세요.
- url이 비어 있으면 링크 없이 이름만 출력하세요.
- 링크 아래 줄에 주소와 카테고리를 함께 표기하세요.

주의: 반드시 위 날짜({date_text})의 계절에 맞는 내용만 작성하세요.
Markdown 형식으로 작성하세요."""

    error_text = (
        "\n".join(f"- {e['step']} | {e['status']} | {e['message']}" for e in errors)
        if errors else "- 없음"
    )
    # 프롬프트: "1~6번만 작성, '오류 요약'은 작성 금지"로 수정

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=_NO_AFC,
        )
        return response.text.rstrip() + f"\n\n## 7. 오류 요약\n{error_text}\n"
    
    except Exception as e:
        errors.append({
            "step": "report",
            "status": "failed",
            "message": f"리포트 생성 실패: {e}",
        })

        # append 이후에 계산해야 리포트 실패도 오류 요약에 포함됨
        if errors:
            error_text = "\n".join(
                f"- {err['step']} | {err['status']} | {err['message']}"
                for err in errors
            )
        else:
            error_text = "- 없음"

        return f"""# {date_text} 국내 여행 리포트

## 1. 추천 지역
{", ".join(cities) if cities else "정보 없음"}

## 2. 추천 이유
{reason or "정보 없음"}

## 3. 날씨 요약
{weather or "정보 없음"}

## 4. 행사/축제
{chr(10).join(f"- {e}" for e in events) if events else "- 없음"}

## 5. 맛집 추천
- 데이터 없음 (리포트 생성 실패로 상세 내용 생략)

## 6. 1일 일정 제안
- 데이터 없음 (리포트 생성 실패)

## 7. 오류 요약
{error_text}
"""

    # ─── 캐시 파일 경로 헬퍼 ──────────────────────────────────────
def _raw_json_path(date_text: str) -> Path:
    """원본 데이터 JSON 경로. 예: results/travel_2025-03-15.json"""
    return RESULTS_DIR / f"travel_{date_text}.json"


def _report_md_path(date_text: str) -> Path:
    """리포트 Markdown 경로. 예: results/travel_2025-03-15.md"""
    return RESULTS_DIR / f"travel_{date_text}.md"


def save_results(
    date_text: str,
    recommendation: dict,
    restaurants_by_city: dict,
    report: str,
    errors: list,
) -> dict:
    """리포트(.md)와 원본 데이터(.json)를 results/ 폴더에 저장하고 경로 반환."""
    _ensure_results_dir()

    md_path = _report_md_path(date_text)
    json_path = _raw_json_path(date_text)

    # ① 리포트 저장 (사람이 읽는 결과물)
    md_path.write_text(report, encoding="utf-8")

    # ② 원본 데이터 저장 (캐시/재현용) — 캐시 로드 시 읽는 키와 동일하게 구성
    raw_data = {
        "date_text": date_text,
        "recommendation": recommendation,
        "restaurants_by_city": restaurants_by_city,
        "errors": errors,
    }
    json_path.write_text(
        json.dumps(raw_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # main.py가 saved['md_path'], saved['json_path']로 접근하므로 키 이름 고정
    return {"md_path": str(md_path), "json_path": str(json_path)}


def load_cached_raw(date_text: str) -> dict | None:
    """같은 날짜의 원본 JSON이 있으면 dict로 반환, 없으면 None."""
    json_path = _raw_json_path(date_text)
    if not json_path.exists():
        return None
    try:
        return json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        # 손상된 캐시는 무시하고 새로 생성하도록 None 반환
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
# ─────────────────────────────────────────────────────────────