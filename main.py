import os
import sys
import argparse
from datetime import datetime

from dotenv import load_dotenv

from utils import (
    generate_city_recommendation,
    search_restaurants_by_cities,   # [변경] 복수 지역 검색 함수
    generate_final_report,
    save_results,
    load_cached_raw,
)


def parse_args():
    """CLI 인자 파싱: --date 필수"""
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Gemini + Kakao 국내 여행 추천 프로그램 (복수 지역)",
    )
    parser.add_argument(
        "--date",
        required=True,
        help='여행 날짜 (형식: YYYY-MM-DD, 예: --date "2025-03-15")',
    )
    return parser.parse_args()


def validate_date(date_text: str) -> str:
    """
    YYYY-MM-DD 형식 검증.
    실패 시 사용법 출력 후 종료.
    """
    try:
        datetime.strptime(date_text, "%Y-%m-%d")
        return date_text
    except ValueError:
        print("[오류] 날짜 형식이 올바르지 않습니다.")
        print('사용법: python main.py --date "YYYY-MM-DD"')
        print('예시:   python main.py --date "2025-03-15"')
        sys.exit(1)


def load_keys():
    """
    .env에서 API 키 로드.
    미설정 시 즉시 종료 + 설정 방법 안내.
    """
    load_dotenv()

    gemini_key = os.getenv("GEMINI_API_KEY")
    kakao_key  = os.getenv("KAKAO_REST_API_KEY")

    missing = []
    if not gemini_key:
        missing.append("GEMINI_API_KEY")
    if not kakao_key:
        missing.append("KAKAO_REST_API_KEY")

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


def main():
    args      = parse_args()
    date_text = validate_date(args.date)
    gemini_key, kakao_key = load_keys()

    # 실행 중 발생하는 오류를 누적 (JSON/리포트에 기록)
    errors = []

    # ── 캐싱(보너스) ──────────────────────────────────────────
    # 같은 날짜 원본 JSON이 있으면 API 호출을 건너뜁니다.
    cached = load_cached_raw(date_text)
    if cached is not None:
        print(f"[캐시] {date_text} 원본 데이터가 존재하여 재사용합니다.")
        recommendation      = cached.get("recommendation", {})
        # [변경] restaurants(list) → restaurants_by_city(dict)
        restaurants_by_city = cached.get("restaurants_by_city", {})
        errors.extend(cached.get("errors", []))

        # [변경] 단수 city → 복수 cities
        cities = recommendation.get("recommended_cities", [])
        print(f"[1/3] (캐시) 추천 도시: {', '.join(cities) if cities else '(없음)'}")
        total = sum(len(v) for v in restaurants_by_city.values())
        print(f"[2/3] (캐시) 맛집 총 {total}곳 로드 완료 ({len(cities)}개 지역)")

    else:
        # ── [1/3] LLM 1차 추천 (복수 지역) ────────────────────
        print("[1/3] 1차 추천 생성 중(LLM)...")
        recommendation = generate_city_recommendation(
            date_text=date_text,
            api_key=gemini_key,
            errors=errors,
        )
        # [변경] 복수 도시 목록
        cities = recommendation.get("recommended_cities", [])
        print(f'  - recommended_cities: {cities}')

        # ── [2/3] Kakao 맛집 검색 (도시별 루프) ───────────────
        print("[2/3] 맛집 검색 중(지도/장소 API)...")
        restaurants_by_city = search_restaurants_by_cities(
            cities=cities,
            api_key=kakao_key,
            errors=errors,
            size=5,
        )
        # [변경] 도시별 검색 결과 출력
        for city in cities:
            count = len(restaurants_by_city.get(city, []))
            if count:
                print(f"  - {city}: 맛집 {count}곳 검색 완료")
            else:
                print(f"  - {city}: 검색 결과 0건 → '데이터 없음'으로 진행")

    # ── [3/3] LLM 최종 리포트 (지역별) ───────────────────────
    print("[3/3] 최종 리포트 생성 중(LLM)...")
    report_md = generate_final_report(
        date_text=date_text,
        recommendation=recommendation,
        restaurants_by_city=restaurants_by_city,   # [변경] dict 전달
        errors=errors,
        api_key=gemini_key,
    )
    print("  - 리포트 생성 완료")

    # ── 결과 저장 ─────────────────────────────────────────────
    saved = save_results(
        date_text=date_text,
        recommendation=recommendation,
        restaurants_by_city=restaurants_by_city,   # [변경] dict 전달
        report=report_md,
        errors=errors,
    )

    print(f"\n완료! {saved['md_path']} 를 확인하세요.")
    print(f"원본 데이터: {saved['json_path']}")

    if errors:
        print(f"\n[참고] 실행 중 {len(errors)}건의 오류가 기록되었습니다.")
        print("       리포트 하단 'errors 섹션'을 확인하세요.")


if __name__ == "__main__":
    main()