import os
import re
import sys
import argparse
from datetime import datetime

from dotenv import load_dotenv

from utils import (
    ERROR_HINTS,
    KakaoLocalProvider,
    generate_city_recommendation,
    search_restaurants_by_cities,
    generate_final_report,
    save_results,
    load_cached_raw,
    load_cached_report,
)


def build_parser() -> argparse.ArgumentParser:
    """CLI 인자 정의: --date 필수 (과제 원문 표기인 -date도 같은 옵션으로 허용)"""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Gemini + Kakao 국내 여행 추천 프로그램 (복수 지역)",
    )
    parser.add_argument(
        "--date", "-date",
        dest="date",
        required=True,
        help='여행 날짜 (형식: YYYY-MM-DD, 예: --date "2026-12-31")',
    )
    return parser


def validate_date(date_text: str, parser: argparse.ArgumentParser) -> str:
    """YYYY-MM-DD 형식(자릿수 포함)과 실제 날짜 여부를 검증. 실패 시 사용법 출력 후 종료(코드 1)."""
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_text):
        try:
            datetime.strptime(date_text, "%Y-%m-%d")
            return date_text
        except ValueError:
            pass
    print(f"[오류] 날짜 형식이 올바르지 않습니다: {date_text!r}")
    parser.print_usage()
    print('예시: python main.py --date "2026-12-31"')
    sys.exit(1)


def load_keys():
    """.env/환경변수에서 API 키 로드. 미설정 시 즉시 종료 + 설정 방법 안내."""
    load_dotenv()

    gemini_key = os.getenv("GEMINI_API_KEY")
    kakao_key = os.getenv("KAKAO_REST_API_KEY")

    missing = [name for name, val in
               (("GEMINI_API_KEY", gemini_key), ("KAKAO_REST_API_KEY", kakao_key)) if not val]

    if missing:
        print(f"[오류] 다음 API 키가 설정되지 않았습니다: {', '.join(missing)}")
        print("\n[설정 방법]")
        print("1) 프로젝트 폴더에 .env 파일을 만들고 아래처럼 작성하세요.")
        print("   GEMINI_API_KEY=발급받은_키")
        print("   KAKAO_REST_API_KEY=발급받은_키")
        print("\n2) 또는 환경변수로 설정하세요.")
        print('   (macOS/Linux) export GEMINI_API_KEY="YOUR_KEY"')
        print('   (Windows PS)  $env:GEMINI_API_KEY="YOUR_KEY"')
        sys.exit(1)

    return gemini_key, kakao_key


def print_city_result(city: str, restaurants_by_city: dict, errors: list) -> None:
    """도시별 맛집 검색 결과를 콘솔에 출력(실패 시 오류 유형별 안내)."""
    count = len(restaurants_by_city.get(city, []))
    if count:
        print(f"  - {city}: 맛집 {count}곳 검색 완료")
        return

    err = next((e for e in reversed(errors)
                if e.get("step") == "place_search" and e.get("city") == city), None)
    err_type = err.get("type", "UNKNOWN_ERROR") if err else "EMPTY_RESULT"
    print(f"  - {city}: {ERROR_HINTS.get(err_type, err_type)} [{err_type}]")
    print("    → 맛집 섹션은 '데이터 없음'으로 처리하고 계속 진행합니다.")


def main():
    parser = build_parser()
    args = parser.parse_args()
    date_text = validate_date(args.date, parser)
    gemini_key, kakao_key = load_keys()

    errors = []       # 실행 중 발생한 오류 누적 (JSON/리포트에 기록)
    report_md = None  # 캐시 히트 시 [3/3] 재생성 생략용

    # ── 캐싱(보너스): 같은 날짜 원본 JSON이 있고 최종 실패 기록이 없으면 API 호출 생략
    cached = load_cached_raw(date_text)
    if cached and any(e.get("status") == "failed" for e in cached.get("errors", [])):
        print("[캐시] 이전 실행에 실패 기록이 있어 캐시를 사용하지 않고 새로 호출합니다.")
        cached = None

    if cached is not None:
        print(f"[캐시] 기존 데이터를 재사용합니다: results/travel_{date_text}.json")
        recommendation = cached.get("recommendation", {})
        restaurants_by_city = cached.get("restaurants_by_city", {})
        errors.extend(cached.get("errors", []))

        cities = recommendation.get("recommended_cities", [])
        if cities:
            recommendation.setdefault("recommended_city", cities[0])
        print(f"[1/3] (캐시) 추천 도시: {', '.join(cities) if cities else '(없음)'}")
        total = sum(len(v) for v in restaurants_by_city.values())
        print(f"[2/3] (캐시) 맛집 총 {total}곳 로드 완료 ({len(cities)}개 지역)")

        report_md = load_cached_report(date_text)

    else:
        # ── [1/3] LLM 1차 추천
        print("[1/3] 1차 추천 생성 중(LLM)...")
        recommendation = generate_city_recommendation(
            date_text=date_text, api_key=gemini_key, errors=errors
        )
        cities = recommendation.get("recommended_cities", [])
        print(f"  - recommended_cities: {cities}")
        if any(e.get("step") == "recommendation" and e.get("status") == "failed" for e in errors):
            print("  - 경고: LLM 응답 실패로 기본값을 사용합니다. 이 결과는 캐시로 재사용되지 않습니다.")

        # ── [2/3] 맛집 검색 (도시별 루프)
        print("[2/3] 맛집 검색 중(지도/장소 API)...")
        provider = KakaoLocalProvider(kakao_key)
        restaurants_by_city = search_restaurants_by_cities(
            cities=cities, provider=provider, errors=errors, size=5
        )
        for city in cities:
            print_city_result(city, restaurants_by_city, errors)

    # ── [3/3] LLM 최종 리포트 (캐시에 리포트가 없을 때만 생성)
    if report_md is None:
        print("[3/3] 최종 리포트 생성 중(LLM)...")
        report_md = generate_final_report(
            date_text=date_text,
            recommendation=recommendation,
            restaurants_by_city=restaurants_by_city,
            errors=errors,
            api_key=gemini_key,
        )
        if any(e.get("step") == "report" and e.get("status") == "failed" for e in errors):
            print("  - LLM 리포트 생성 실패 → 수집한 데이터로 기본 리포트를 생성했습니다.")
        else:
            print("  - 리포트 생성 완료")
    else:
        print("[3/3] (캐시) 기존 리포트를 재사용합니다.")

    # ── 결과 저장
    saved = save_results(
        date_text=date_text,
        recommendation=recommendation,
        restaurants_by_city=restaurants_by_city,
        report=report_md,
        errors=errors,
    )

    print(f"\n완료! {saved['md_path']} 를 확인하세요.")
    print(f"원본 데이터: {saved['json_path']}")

    if errors:
        print(f"\n[참고] 실행 중 {len(errors)}건의 오류가 기록되었습니다.")
        print("       리포트 하단 '7. 오류 요약'과 JSON의 errors를 확인하세요.")


if __name__ == "__main__":
    main()
