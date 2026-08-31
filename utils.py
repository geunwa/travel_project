import os
from pathlib import Path
from urllib.parse import unquote

import requests
from dotenv import load_dotenv


AREA_CODE_MAP = {
    "서울": 1,
    "서울특별시": 1,
    "인천": 2,
    "인천광역시": 2,
    "대전": 3,
    "대전광역시": 3,
    "대구": 4,
    "대구광역시": 4,
    "광주": 5,
    "광주광역시": 5,
    "부산": 6,
    "부산광역시": 6,
    "울산": 7,
    "울산광역시": 7,
    "세종": 8,
    "세종특별자치시": 8,
    "경기": 31,
    "경기도": 31,
    "강원": 32,
    "강원도": 32,
    "충북": 33,
    "충청북도": 33,
    "충남": 34,
    "충청남도": 34,
    "경북": 35,
    "경상북도": 35,
    "경남": 36,
    "경상남도": 36,
    "전북": 37,
    "전라북도": 37,
    "전북특별자치도": 37,
    "전남": 38,
    "전라남도": 38,
    "제주": 39,
    "제주도": 39,
    "제주특별자치도": 39,
}

CONTENT_TYPE_MAP = {
    "1": ("관광지", 12),
    "2": ("문화시설", 14),
    "3": ("음식점", 39),
}

NUM_OF_ROWS = 10


def load_api_key():
    """현재 파일 기준 같은 폴더의 .env에서 API_KEY를 읽어온다."""
    env_path = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_path)

    api_key = os.getenv("API_KEY")
    if not api_key:
        return None

    return unquote(api_key)


def print_region_guide():
    print("\n조회 가능한 지역 예시:")
    print("서울, 부산, 대구, 인천, 광주, 대전, 울산, 세종")
    print("경기, 강원, 충북, 충남, 경북, 경남, 전북, 전남, 제주")


def get_area_code_from_user():
    """지역명을 입력받아 (지역명, 지역코드)를 반환한다."""
    while True:
        print_region_guide()
        region_name = input("지역명을 입력하세요: ").strip()

        if region_name in AREA_CODE_MAP:
            return region_name, AREA_CODE_MAP[region_name]

        print("잘못된 지역명입니다. 다시 입력해주세요.")


def print_content_type_guide():
    print("\n조회할 종류를 선택하세요:")
    print("1. 관광지")
    print("2. 문화시설")
    print("3. 음식점")


def get_content_type_from_user():
    """종류 번호를 입력받아 (종류명, contentTypeId)를 반환한다."""
    while True:
        print_content_type_guide()
        choice = input("번호를 입력하세요: ").strip()

        if choice in CONTENT_TYPE_MAP:
            return CONTENT_TYPE_MAP[choice]

        print("잘못된 번호입니다. 1, 2, 3 중에서 다시 입력해주세요.")


def get_page_number_from_user():
    """페이지 번호를 입력받아 정수로 반환한다."""
    while True:
        page_input = input("\n페이지 번호를 입력하세요(1 이상): ").strip()

        if not page_input.isdigit():
            print("숫자만 입력해주세요.")
            continue

        page_no = int(page_input)

        if page_no < 1:
            print("페이지 번호는 1 이상이어야 합니다.")
            continue

        return page_no


def request_places(api_key, area_code, content_type_id, page_no):
    """관광정보 API를 호출한다."""
    url = "https://apis.data.go.kr/B551011/KorService2/areaBasedList2"

    params = {
        "serviceKey": api_key,
        "numOfRows": NUM_OF_ROWS,
        "pageNo": page_no,
        "MobileOS": "ETC",
        "MobileApp": "TravelProject",
        "_type": "json",
        "areaCode": area_code,
        "contentTypeId": content_type_id,
    }

    return requests.get(url, params=params, timeout=10)


def parse_items(response_json):
    """응답 JSON에서 item 목록을 추출한다."""
    body = response_json.get("response", {}).get("body", {})
    items = body.get("items", {}).get("item", [])

    if isinstance(items, dict):
        items = [items]

    return items


def get_total_count(response_json):
    """응답 JSON에서 전체 데이터 개수를 추출한다."""
    body = response_json.get("response", {}).get("body", {})
    total_count = body.get("totalCount", 0)

    try:
        return int(total_count)
    except (TypeError, ValueError):
        return 0


def print_places(region_name, content_name, items, total_count, page_no):
    """조회된 결과를 보기 좋게 출력한다."""
    print(f"\n[{region_name}] {content_name} 조회 결과")
    print(f"전체 개수: {total_count}")
    print(f"현재 페이지: {page_no}")
    print(f"현재 출력 개수: {len(items)}")

    if total_count > 0:
        start_num = (page_no - 1) * NUM_OF_ROWS + 1
        end_num = min(page_no * NUM_OF_ROWS, total_count)
        print(f"현재 범위: {start_num} ~ {end_num}")

    if not items:
        print("조회된 데이터가 없습니다.")
        print("페이지 번호가 너무 큰지 확인해주세요.")
        return

    for idx, item in enumerate(items, start=1):
        title = item.get("title", "제목 없음")
        addr1 = item.get("addr1", "")
        addr2 = item.get("addr2", "")
        tel = item.get("tel", "")
        mapx = item.get("mapx", "없음")
        mapy = item.get("mapy", "없음")

        full_address = f"{addr1} {addr2}".strip()
        if not full_address:
            full_address = "주소 없음"

        if not tel:
            tel = "전화번호 없음"

        print(f"\n{idx}. {title}")
        print(f"   주소: {full_address}")
        print(f"   전화: {tel}")
        print(f"   좌표: ({mapy}, {mapx})")