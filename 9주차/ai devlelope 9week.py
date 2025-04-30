import streamlit as st
import pandas as pd
from datetime import datetime
import json
import os

# 페이지 설정
st.set_page_config(
    page_title="사진첩 앱",
    page_icon="📸",
    layout="wide"
)

# 스타일 적용
st.markdown("""
    <style>
    .main {
        padding: 0rem 1rem;
    }
    .block-container {
        padding-top: 2rem;
    }
    .photo-container {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 20px;
        background-color: white;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        transition: transform 0.3s;
    }
    .photo-container:hover {
        transform: translateY(-5px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
    .img-container {
        height: 200px;
        display: flex;
        align-items: center;
        justify-content: center;
        overflow: hidden;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .img-container img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }
    h1 {
        color: #2e4057;
        text-align: center;
        padding: 20px 0;
        background-color: #f8f9fa;
        border-radius: 10px;
        margin-bottom: 30px;
    }
    h3 {
        color: #2e4057;
        margin-bottom: 10px;
    }
    .photo-info {
        margin-top: 10px;
    }
    .delete-btn {
        background-color: #ff4757;
        color: white;
        border: none;
        padding: 5px 10px;
        border-radius: 5px;
        cursor: pointer;
    }
    .add-btn {
        background-color: #1e88e5;
        color: white;
        border: none;
        padding: 10px 15px;
        border-radius: 5px;
        cursor: pointer;
        margin-top: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# 초기 데이터 로드 함수
def load_data():
    if os.path.exists("photos.json"):
        with open("photos.json", "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        # 기본 사진 4장
        return {
            "photos": [
                {
                    "id": 1,
                    "name": "해변의 일몰",
                    "types": ["풍경", "여행"],
                    "year": 2023,
                    "url": "https://weekly.chosun.com/news/photo/202306/26908_50337_5156.jpg"
                },
                {
                    "id": 2,
                    "name": "산악 풍경",
                    "types": ["풍경"],
                    "year": 2022,
                    "url": "data:image/jpeg;base64,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"
                },
                {
                    "id": 3,
                    "name": "도시 야경",
                    "types": ["거리", "여행"],
                    "year": 2024,
                    "url": "https://www.adobe.com/kr/creativecloud/photography/discover/media_18ec078ac12361c5bd437dae615fd5dd92bfbfe51.jpeg?width=1200&format=pjpg&optimize=medium"
                },
                {
                    "id": 4,
                    "name": "꽃 클로즈업",
                    "types": ["접사"],
                    "year": 2023,
                    "url": "https://images.unsplash.com/photo-1596478528745-662331c50d9c?fm=jpg&q=60&w=3000&ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D"
                }
            ]
        }

# 데이터 저장 함수
def save_data(data):
    with open("photos.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 앱 제목
st.title("📸 나의 사진첩")

# 데이터 로드
data = load_data()

# 사이드바: 사진 추가 폼
with st.sidebar:
    st.header("📊 사진 추가")
    
    # 예시 사진 자동 완성 토글
    auto_fill = st.toggle("예시 사진 정보 자동 완성", False)
    
    if auto_fill:
        photo_name = "아름다운 자연 풍경"
        photo_url = "https://i.namu.wiki/i/VBoCHB3kYoTDQqh6X-bNiMhnul9HYeCB0P1nCMP7aU5AxlDns4mbLNS0YHHOC3vxOMN86Ma0FEFo_WcNL6qvMg.webp"
        current_year = datetime.now().year
    else:
        photo_name = ""
        photo_url = ""
        current_year = datetime.now().year
    
    # 입력 폼
    with st.form(key="add_photo"):
        name = st.text_input("사진 이름", value=photo_name)
        
        # 사진 종류 선택 (최대 2개)
        photo_types = ["인물", "풍경", "여행", "접사", "패션", "음식", "거리", "스포츠", "연예인", "기타"]
        types = st.multiselect(
            "사진 종류 (최대 2개)",
            options=photo_types,
            max_selections=2,
            default=["풍경"] if auto_fill else None
        )
        
        # 연도 입력
        year = st.number_input("촬영 연도", min_value=1900, max_value=current_year, value=current_year)
        
        # URL 입력
        url = st.text_input("사진 URL", value=photo_url)
        
        # 제출 버튼
        submit = st.form_submit_button("사진 추가")
        
        if submit:
            if name and url and types:
                # 새 사진의 ID 생성
                new_id = max([photo["id"] for photo in data["photos"]], default=0) + 1
                
                # 새 사진 추가
                data["photos"].append({
                    "id": new_id,
                    "name": name,
                    "types": types,
                    "year": year,
                    "url": url
                })
                
                # 데이터 저장
                save_data(data)
                
                # 페이지 새로고침
                st.rerun()
            else:
                st.error("모든 필드를 채워주세요.")

# 레이아웃 옵션 선택
col_count = st.radio("한 줄에 표시할 사진 수", [2, 4], horizontal=True)

# 필터 옵션
st.subheader("필터 옵션")
filter_col1, filter_col2 = st.columns(2)

with filter_col1:
    # 사진 종류별 필터링
    all_types = list(set([t for photo in data["photos"] for t in photo["types"]]))
    selected_types = st.multiselect("사진 종류별 필터링", options=all_types)

with filter_col2:
    # 연도별 필터링
    all_years = sorted(list(set([photo["year"] for photo in data["photos"]])), reverse=True)
    selected_years = st.multiselect("연도별 필터링", options=all_years)

# 데이터 필터링
filtered_photos = data["photos"]

if selected_types:
    filtered_photos = [photo for photo in filtered_photos if any(t in selected_types for t in photo["types"])]

if selected_years:
    filtered_photos = [photo for photo in filtered_photos if photo["year"] in selected_years]

# 사진 표시
if not filtered_photos:
    st.info("표시할 사진이 없습니다. 다른 필터를 선택하거나 새 사진을 추가해주세요.")
else:
    # 열 생성
    cols = st.columns(col_count)
    
    # 사진별로 순회하며 표시
for i, photo in enumerate(filtered_photos):
    with cols[i % col_count]:
        with st.container():
            # 사진 표시
            st.image(photo["url"], use_container_width=True)
            # 사진 정보
            st.subheader(photo["name"])
            st.write(f"**종류**: {', '.join(photo['types'])}")
            st.write(f"**촬영 연도**: {photo['year']}")
            # 삭제 버튼
            if st.button(f"삭제", key=f"delete_{photo['id']}"):
                data["photos"] = [p for p in data["photos"] if p["id"] != photo["id"]]
                save_data(data)
                st.rerun()

# 여기 아래에 추가!
if st.button("사진첩 초기화(처음 상태로 되돌리기)"):
    if os.path.exists("photos.json"):
        os.remove("photos.json")
    st.rerun()

# 갤러리 정보 표시
st.divider()
st.write(f"총 {len(data['photos'])} 장의 사진이 있습니다. 현재 {len(filtered_photos)} 장이 표시되고 있습니다.")
st.caption("© 2025 인공지능서비스개발I - Streamlit 사진첩 프로젝트")

#cd "c:\Users\tree1\Desktop\인공지능 서비스 개발 창의 융합"
#streamlit run 인공지능 서비스 개발 9주차.py