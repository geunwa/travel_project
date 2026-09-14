import json
import sys
import subprocess
from pathlib import Path

import pandas as pd
import streamlit as st

RESULTS_DIR = Path("results")


def load_result_files():
    """results 폴더의 travel_*.json 파일 목록을 최신순으로 반환"""
    if not RESULTS_DIR.exists():
        return []
    files = sorted(RESULTS_DIR.glob("travel_*.json"), reverse=True)
    return files


def load_result(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------- UI ----------------
st.set_page_config(page_title="국내 여행 추천", page_icon="🧳", layout="wide")
st.title("🧳 국내 여행 추천 리포트")

files = load_result_files()
if not files:
    st.warning("results 폴더에 결과 파일이 없습니다. 먼저 main.py를 실행해 주세요.")
    st.stop()

# 사이드바: 날짜(파일) 선택
file_labels = [f.stem.replace("travel_", "") for f in files]
selected_label = st.sidebar.selectbox("📅 날짜 선택", file_labels)
selected_file = files[file_labels.index(selected_label)]

data = load_result(selected_file)
rec = data.get("recommendation", {})

# 1) 추천 요약
st.header(f"📆 {data.get('date', '')} 여행 추천")
st.subheader("추천 도시")
st.write(" · ".join(rec.get("recommended_cities", [])))

col1, col2 = st.columns(2)
with col1:
    st.subheader("🌤️ 날씨")
    st.write(rec.get("weather", ""))
with col2:
    st.subheader("🎉 행사/축제")
    for ev in rec.get("events", []):
        st.write(f"- {ev}")

st.subheader("💡 추천 이유")
st.write(rec.get("reason", ""))

st.divider()

# 2) 도시별 맛집 + 지도
st.header("🍽️ 도시별 맛집")
restaurants_by_city = data.get("restaurants_by_city", {})

for city, shops in restaurants_by_city.items():
    st.subheader(f"📍 {city}")

    for i, s in enumerate(shops, 1):
        name = s.get("name", "")
        url = s.get("url", "")
        title = f"{i}. [{name}]({url})" if url else f"{i}. {name}"
        st.markdown(title)
        st.caption(f"{s.get('address', '')} | {s.get('category', '')}")
        # 카카오맵으로 바로 열기 링크
        if s.get("x") and s.get("y"):
            kakao = f"https://map.kakao.com/link/map/{name},{s['y']},{s['x']}"
            st.markdown(f"　🗺️ [카카오맵에서 보기]({kakao})")

    # 좌표로 지도 표시 (x=경도, y=위도)
    coords = [
        {"lat": s["y"], "lon": s["x"]}
        for s in shops
        if s.get("x") is not None and s.get("y") is not None
    ]
    if coords:
        st.map(pd.DataFrame(coords))

    st.divider()

# 3) 오류 요약
errors = data.get("errors", [])
if errors:
    st.header("⚠️ 오류 요약")
    for e in errors:
        st.write(f"- {e}")
else:
    st.success("오류 없이 정상 생성된 리포트입니다.")


# ─── ▶ 실행 버튼으로도 자동 실행되게 ───
# 일반 python으로 실행하면 streamlit으로 자기 자신을 재실행
if __name__ == "__main__" and not st.runtime.exists():
    subprocess.run([sys.executable, "-m", "streamlit", "run", __file__])