import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key) if api_key else None


def extract_json_text(text):
    text = text.strip()

    if text.startswith("```json"):
        text = text[7:].strip()
    elif text.startswith("```"):
        text = text[3:].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    start = text.find("{")
    end = text.rfind("}")

    if start != -1 and end != -1:
        text = text[start:end + 1]

    return text


def get_travel_recommendation(date_str, errors):
    if client is None:
        errors.append("OPENAI_API_KEY가 설정되지 않았습니다.")
        return {
            "recommended_city": "서울",
            "weather": "데이터 없음",
            "events": ["데이터 없음"],
            "reason": "OpenAI API 키가 없어 기본 추천을 사용했습니다."
        }

    prompt = f"""
너는 국내 여행 추천 도우미다.
사용자의 여행 날짜를 보고 국내 여행지 1곳을 추천하라.

반드시 아래 JSON 형식만 출력하라.
다른 문장, 설명, 코드블록은 붙이지 마라.

{{
  "recommended_city": "도시명",
  "weather": "간단한 날씨 설명",
  "events": ["이벤트1", "이벤트2"],
  "reason": "추천 이유"
}}

여행 날짜: {date_str}
"""

    for attempt in range(1, 4):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "너는 국내 여행 추천 도우미다. 반드시 JSON만 출력한다."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7
            )

            content = response.choices[0].message.content
            json_text = extract_json_text(content)
            data = json.loads(json_text)

            required_keys = ["recommended_city", "weather", "events", "reason"]
            for key in required_keys:
                if key not in data:
                    raise ValueError(f"필수 키 누락: {key}")

            if not isinstance(data["events"], list):
                data["events"] = [str(data["events"])]

            return data

        except Exception as e:
            errors.append(f"LLM JSON 파싱/생성 실패 ({attempt}회차): {e}")

    return {
        "recommended_city": "서울",
        "weather": "데이터 없음",
        "events": ["데이터 없음"],
        "reason": "LLM 응답 처리에 실패하여 기본 추천을 사용했습니다."
    }