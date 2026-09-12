import os
from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("GEMINI_API_KEY가 .env에 없습니다.")
    exit(1)

# 신규 라이브러리: Client 객체 생성
client = genai.Client(api_key=api_key)

# 모델명은 3.6-flash로 교체
response = client.models.generate_content(
    model="gemini-3.6-flash",
    contents="안녕? 한 문장으로 인사해줘.",
)

print("Gemini 응답:", response.text)