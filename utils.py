import json
import re
import requests
from datetime import datetime
from pathlib import Path

from google import genai


# =============================================================
# 공통 상수
# =============================================================

RESULTS_DIR   = Path("results")
REQUIRED_KEYS = {"recommended_city", "weather", "events", "reason"}
GEMINI_MODEL  = "gemini-3.6-flash"


# =============================================================
# 내부 유틸
# =============================================================

def _ensure_results_dir() -> Path:
    """results/ 폴더가 없으면 생성 후 반환"""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    return RESULTS_DIR


def _extract_json_from_text(text: str) -> dict:
    """LLM 응답 텍스트에서 JSON 블록만 추출 후 파싱."""
    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if code_block:
        candidate = code_block.group(1).strip()
    else:
        brace_match = re.search(r"\{[\s\S]*\}", text)
        candidate = brace_match.group(0).strip() if brace_match else text.strip()
    return json.loads(candidate)


def _validate_recommendation(data: dict) -> bool:
    """필수 키 4개 모두 존재하면 True"""
    return REQUIRED_KEYS.issubset(data.keys())


def _build_fallback_report(
    date_text: str,
    city: str,
    reason: str,
    weather: str,
    events_text: str,
    restaurant_lines: str,
    errors_text: str,
) -> str:
    """LLM 리포트 생성 실패 시 최소 Markdown 직접 조립."""
    return (
        f"# {date_text} 국내 여행 추천 리포트\n"
        f"> LLM 리포트 생성에 실패하여 기본 형식으로 출력합니다.\n\n"
        f"## 추천 지역\n{city or '정보 없음'}\n\n"
        f"## 추천 이유\n{reason or '정보 없음'}\n\n"
        f"## 날씨 요약\n{weather or '정보 없음'}\n\n"
        f"## 행사/축제\n{events_text or '정보 없음'}\n\n"
        f"## 맛집 추천\n{restaurant_lines or '데이터 없음'}\n\n"
        f"## 1일 일정 제안\n정보를 불러오지 못했습니다.\n\n"
        f"## 오류 요약\n{errors_text or '없음'}\n"
    )


# =============================================================
# [1] LLM 1차 추천 생성
# =============================================================

def generate_city_recommendation(
    date_text: str,
    api_key: str,
    errors: list,
) -> dict:
    client = genai.Client(api_key=api_key)

    def _build_prompt(strict: bool = False) -> str:
        base = f"""당신은 국내 여행 전문가입니다.
여행 날짜: {date_text}

아래 JSON 형식으로만 답하세요. 설명 문장, 마크다운 없이 JSON만 출력하세요.

{{
  "recommended_city": "추천 도시명 (예: 제주, 강릉, 경주)",
  "weather": "해당 시기 일반적인 날씨 요약 (1~2문장)",
  "events": ["행사/축제 후보 1개", "행사/축제 후보 2개"],
  "reason": "추천 근거 (2~4문장)"
}}"""
        if strict:
            base = "반드시 JSON만 출력하세요. 앞뒤 설명 없이 { } 블록만.\n\n" + base
        return base

    # ── 1차 시도 ──────────────────────────────────────────────
    raw_text = ""
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=_build_prompt(strict=False),
        )
        raw_text = response.text
        data = _extract_json_from_text(raw_text)
        if _validate_recommendation(data):
            return data
        raise ValueError(f"필수 키 누락: {REQUIRED_KEYS - data.keys()}")

    except Exception as e:
        errors.append({
            "step"   : "llm_recommendation_attempt1",
            "type"   : type(e).__name__,
            "message": str(e),
            "raw"    : raw_text[:300] if raw_text else "",
        })

    # ── 재시도 1회 (strict 프롬프트) ──────────────────────────
    raw_text = ""
    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=_build_prompt(strict=True),
        )
        raw_text = response.text
        data = _extract_json_from_text(raw_text)
        if _validate_recommendation(data):
            return data
        raise ValueError(f"재시도 후에도 필수 키 누락: {REQUIRED_KEYS - data.keys()}")

    except Exception as e:
        errors.append({
            "step"   : "llm_recommendation_attempt2",
            "type"   : type(e).__name__,
            "message": str(e),
            "raw"    : raw_text[:300] if raw_text else "",
        })

    # ── 최종 실패 → 기본값 반환 ───────────────────────────────
    return {
        "recommended_city": "",
        "weather"         : "정보 없음",
        "events"          : [],
        "reason"          : "LLM 추천 생성에 실패했습니다.",
    }


# =============================================================
# [2] Kakao 맛집 검색
# =============================================================

def search_restaurants(
    city: str,
    api_key: str,
    errors: list,
    size: int = 5,
) -> list:
    if not city:
        errors.append({
            "step"   : "place_search",
            "type"   : "EMPTY_CITY",
            "message": "recommended_city가 비어 있어 맛집 검색을 건너뜁니다.",
        })
        return []

    url     = "https://dapi.kakao.com/v2/local/search/keyword.json"
    headers = {"Authorization": f"KakaoAK {api_key}"}
    query   = f"{city} 맛집"
    params  = {"query": query, "size": size, "sort": "accuracy"}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)

        if response.status_code in (401, 403):
            errors.append({
                "step"   : "place_search",
                "type"   : "AUTH_ERROR",
                "message": (
                    f"HTTP {response.status_code} - "
                    "키 설정을 확인하세요. "
                    "Kakao Developers > 앱 > 플랫폼/키 설정 확인"
                ),
            })
            print(f"  - 오류: 인증 실패({response.status_code}). 키 설정을 확인하세요.")
            print("  - 맛집 섹션은 '데이터 없음'으로 처리하고 계속 진행합니다.")
            return []

        response.raise_for_status()
        documents = response.json().get("documents", [])

        if not documents:
            errors.append({
                "step"   : "place_search",
                "type"   : "EMPTY_RESULT",
                "message": f"0 results for query={query}",
            })
            print(f"  - 검색 결과 0건 (query={query})")
            return []

        results = []
        for doc in documents:
            address = doc.get("road_address_name") or doc.get("address_name", "")
            results.append({
                "name"    : doc.get("place_name", ""),
                "address" : address,
                "category": doc.get("category_name", ""),
                "url"     : doc.get("place_url", ""),
                "x"       : doc.get("x", ""),
                "y"       : doc.get("y", ""),
            })
        return results

    except requests.exceptions.Timeout:
        errors.append({
            "step"   : "place_search",
            "type"   : "TIMEOUT",
            "message": f"요청 시간 초과 (query={query})",
        })
        print("  - 오류: 맛집 검색 시간 초과. '데이터 없음'으로 계속 진행합니다.")
        return []

    except requests.exceptions.RequestException as e:
        errors.append({
            "step"   : "place_search",
            "type"   : "NETWORK_ERROR",
            "message": str(e),
        })
        print(f"  - 오류: 네트워크 오류({e}). '데이터 없음'으로 계속 진행합니다.")
        return []

    except Exception as e:
        errors.append({
            "step"   : "place_search",
            "type"   : type(e).__name__,
            "message": str(e),
        })
        return []

# =============================================================
# [3] LLM 최종 리포트 생성
# =============================================================

def generate_final_report(
    date_text: str,
    recommendation: dict,
    restaurants: list,
    errors: list,
    api_key: str,
) -> str:
    city    = recommendation.get("recommended_city", "정보 없음")
    weather = recommendation.get("weather", "정보 없음")
    events  = recommendation.get("events", [])
    reason  = recommendation.get("reason", "정보 없음")

    restaurant_lines = (
        "\n".join(
            f"- {r['name']} | {r['address']} | {r['category']} | {r['url']}"
            for r in restaurants
        )
        if restaurants
        else "데이터 없음 (장소 검색 결과 0건)"
    )

    events_text = (
        "\n".join(f"- {e}" for e in events)
        if events
        else "정보 없음"
    )

    errors_text = (
        "\n".join(
            f"- [{e.get('step', '')}] {e.get('type', '')}: {e.get('message', '')}"
            for e in errors
        )
        if errors
        else "없음"
    )

    prompt = (
        f"당신은 국내 여행 전문 작가입니다.\n"
        f"아래 정보를 바탕으로 여행 리포트를 Markdown 형식으로 작성하세요.\n\n"
        f"[여행 날짜] {date_text}\n"
        f"[추천 도시] {city}\n"
        f"[추천 이유] {reason}\n"
        f"[날씨] {weather}\n"
        f"[행사/축제]\n{events_text}\n"
        f"[맛집 목록]\n{restaurant_lines}\n\n"
        f"[작성 규칙]\n"
        f"1. 아래 섹션 헤더를 반드시 포함하세요 (순서대로):\n"
        f"   - 추천 지역\n"
        f"   - 추천 이유\n"
        f"   - 날씨 요약\n"
        f"   - 행사/축제\n"
        f"   - 맛집 추천\n"
        f"   - 1일 일정 제안\n"
        f"   - 오류 요약(errors)\n"
        f"2. 불필요한 미사여구를 제외하고 가독성 좋게 작성하세요.\n"
    )

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
        )
        return response.text
    except Exception as e:
        errors.append({
            "step": "generate_final_report",
            "type": type(e).__name__,
            "message": str(e),
        })
        return _build_fallback_report(
            date_text, city, reason, weather, events_text, restaurant_lines, errors_text
        )

# =============================================================
# [4] 결과 저장 및 캐시 관리
# =============================================================

def save_results(date_text: str, recommendation: dict, restaurants: list, report: str, errors: list) -> dict:
    """JSON 원본 데이터와 Markdown 리포트를 results/ 폴더에 저장합니다."""
    out_dir = _ensure_results_dir()
    json_path = out_dir / f"{date_text}.json"
    md_path = out_dir / f"{date_text}.md"

    data = {
        "recommendation": recommendation,
        "restaurants": restaurants,
        "errors": errors
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report)

    return {"json_path": str(json_path), "md_path": str(md_path)}


def load_cached_raw(date_text: str):
    """기존에 검색한 동일한 날짜의 JSON 데이터가 있으면 불러옵니다."""
    json_path = RESULTS_DIR / f"{date_text}.json"
    if not json_path.exists():
        return None
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None