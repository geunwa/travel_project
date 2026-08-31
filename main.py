from utils import (
    load_api_key,
    get_area_code_from_user,
    get_content_type_from_user,
    get_page_number_from_user,
    request_places,
    parse_items,
    get_total_count,
    print_places,
)
import requests


def main():
    api_key = load_api_key()

    if not api_key:
        print("API 키를 읽지 못했습니다.")
        print(".env 파일에 API_KEY가 있는지 확인해주세요.")
        return

    region_name, area_code = get_area_code_from_user()
    content_name, content_type_id = get_content_type_from_user()
    page_no = get_page_number_from_user()

    try:
        response = request_places(api_key, area_code, content_type_id, page_no)

        print("\n상태 코드:", response.status_code)

        if response.status_code != 200:
            print("요청에 실패했습니다.")
            print(response.text)
            return

        data = response.json()

        header = data.get("response", {}).get("header", {})
        result_code = header.get("resultCode")
        result_msg = header.get("resultMsg")

        print("결과 코드:", result_code)
        print("결과 메시지:", result_msg)

        if result_code != "0000":
            print("API 응답에 문제가 있습니다.")
            print(response.text)
            return

        items = parse_items(data)
        total_count = get_total_count(data)

        print_places(region_name, content_name, items, total_count, page_no)

    except requests.exceptions.Timeout:
        print("요청 시간이 초과되었습니다. 잠시 후 다시 시도해주세요.")
    except requests.exceptions.RequestException as e:
        print("네트워크 요청 중 오류가 발생했습니다:", e)
    except ValueError:
        print("JSON 데이터 처리 중 오류가 발생했습니다.")
    except Exception as e:
        print("예상하지 못한 오류가 발생했습니다:", e)


if __name__ == "__main__":
    main()