import os
import requests
from dotenv import load_dotenv

load_dotenv()

KAKAO_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KAKAO_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


def search_places(city, keyword, errors, size=5):
    if not KAKAO_API_KEY