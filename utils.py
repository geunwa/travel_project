import json
import re
import json
import re
import requests
from pathlib import Path

from google import genai
from google.genai import types

# ─── 키워드 전처리 ───────────────────────────────────────────
def normalize_city_keyword(city: str) -> str:
    """도시명 전처리: 괄호·특수문자 제거, 공백 정리.
    
    예시:
        "제주(제주시)" → "제주 제주시"
        "전주·한옥마을" → "전주 한옥마을"
    """
    city = re.sub(r"[\(\)\[\]·]", " ", city)  # 괄호·중점 제거
    city = re.sub(r"\s+", " ", city).strip()   # 연속 공백 정리
    return city
# ─────────────────────────────────────────────────────────────

RESULTS_DIR = Path("results")
REQUIRED_KEYS = {"recommended_cities", "weather", "events", "reason"}
GEMINI_MODEL = "gemini-3.6-flash"

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
            errors.append(f"[1/3] LLM 시도 {attempt} 실패: {e}")

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
    keyword = normalize_city_keyword(city)   # ← 추가
    params = {
        "query": f"{keyword} 맛집",          # ← city → keyword 로 변경
        "size": size,
        "category_group_code": "FD6",
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        documents = response.json().get("documents", [])

        if not documents:
            errors.append(f"[2/3] Kakao 검색 결과 0건 (city={city})")
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
        errors.append(f"[2/3] Kakao API 오류 (city={city}): {e}")
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

    error_text = "\n".join(f"- {e}" for e in errors) if errors else "- 없음"

    prompt = f"""당신은 여행 작가입니다.
아래 정보를 바탕으로 {date_text} 국내 여행 리포트를 Markdown 형식으로 작성해주세요.

추천 도시 목록: {', '.join(cities)}
날씨: {weather}
행사/축제: {', '.join(events) if events else '없음'}
추천 이유: {reason}

도시별 맛집 목록 (각 항목의 [url:...]은 해당 맛집의 카카오맵 링크입니다):
{cities_block}

다음 섹션을 반드시 포함해주세요:
1. 추천 지역 (여러 도시를 함께 소개)
2. 추천 이유
3. 날씨 요약
4. 행사/축제
5. 도시별 맛집 추천 (도시마다 소제목으로 구분, 0건이면 '데이터 없음'으로 표기)
6. 도시별 1일 일정 제안 (각 도시별로 오전/오후/저녁 수준)
7. 오류 요약

맛집 출력 규칙(중요):
- 각 맛집의 이름은 반드시 마크다운 링크 형식 [맛집이름](카카오맵url) 으로 작성하세요.
- 카카오맵url은 위 목록의 [url:...] 안에 있는 주소를 사용하세요.
- url이 비어 있으면 링크 없이 이름만 출력하세요.
- 링크 아래 줄에 주소와 카테고리를 함께 표기하세요.

주의: 반드시 위 날짜({date_text})의 계절에 맞는 내용만 작성하세요.
Markdown 형식으로 작성하세요."""

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=_NO_AFC,
        )
        return response.text
    except Exception as e:
        errors.append(f"[3/3] 리포트 생성 실패: {e}")

        fallback_cities = ""
        for city in cities:
            rlist = restaurants_by_city.get(city, [])
            fallback_cities += f"\n### {city}\n"
            if rlist:
                for i, r in enumerate(rlist, 1):
                    url = r.get("url", "")
                    # 폴백은 코드가 직접 마크다운 링크를 조립 (LLM 미사용이라 확실함)
                    if url:
                        name_md = f"[{r['name']}]({url})"
                    else:
                        name_md = r["name"]
                    fallback_cities += (
                        f"{i}. {name_md}\n"
                        f"   * 주소: {r['address']}\n"
                        f"   * 카테고리: {r['category']}\n"
                    )
            else:
                fallback_cities += "- 데이터 없음\n"

        schedule_block = "\n".join(
            f"""### {c}
- 오전: {c} 도착 및 체크인
- 점심: 현지 맛집 방문
- 오후: 주요 관광지 탐방
- 저녁: 야경 감상"""
            for c in cities
        )

        fallback = f"""# {date_text} 국내 여행 리포트

## 추천 지역
{', '.join(cities)}

## 추천 이유
{reason}

## 날씨 요약
{weather}

## 행사/축제
{chr(10).join(f'- {ev}' for ev in events) if events else '- 정보 없음'}

## 도시별 맛집 추천
{fallback_cities}

## 도시별 1일 일정 제안
{schedule_block}

## 오류 요약
{error_text}
"""
        return fallback


def save_results(
    date_text: str,
    recommendation: dict,
    restaurants_by_city: dict,
    report: str,
    errors: list,
) -> dict:
    """JSON 원본 데이터와 Markdown 리포트를 results/ 폴더에 저장."""
    results_dir = _ensure_results_dir()

    json_path = results_dir / f"travel_{date_text}.json"
    md_path = results_dir / f"travel_{date_text}.md"

    raw_data = {
        "date": date_text,
        "recommendation": recommendation,
        "restaurants_by_city": restaurants_by_city,
        "errors": errors,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(raw_data, f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)

    return {
        "json_path": str(json_path),
        "md_path": str(md_path),
    }


def load_cached_raw(date_text: str) -> dict | None:
    """같은 날짜 JSON 캐시가 있으면 로드, 없으면 None 반환."""
    json_path = RESULTS_DIR / f"travel_{date_text}.json"
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None
    return None
