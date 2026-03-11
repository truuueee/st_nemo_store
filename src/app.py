import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import os
import json

# 페이지 설정
st.set_page_config(page_title="네모스토어 상가 매물 대시보드", layout="wide")

# CSS 커스텀 스타일 (네모 브랜드 느낌)
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .gallery-card {
        border: 1px solid #ddd;
        border-radius: 8px;
        padding: 10px;
        background-color: white;
        margin-bottom: 20px;
    }
    </style>
    """, unsafe_allow_html=True)

# 세션 상태 초기화
if 'selected_article' not in st.session_state:
    st.session_state.selected_article = None

# 데이터 로드 함수
@st.cache_data
def load_data():
    # 현재 파일(app.py)의 위치를 기준으로 DB 경로를 찾습니다.
    # 1. app.pyと同じ폴더에 있는 경우
    # 2. app.py의 부모(루트) 폴더에 있는 경우를 모두 체크합니다.
    current_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(current_dir)
    
    paths_to_try = [
        os.path.join(current_dir, "nemostore.db"),
        os.path.join(root_dir, "nemostore.db"),
        os.path.join(root_dir, "data", "nemostore.db"),  # data 폴더 추가
        os.path.join(os.getcwd(), "nemostore.db"),
        os.path.join(os.getcwd(), "data", "nemostore.db") # 현재 디렉토리의 data 폴더 추가
    ]
    
    db_path = None
    for p in paths_to_try:
        if os.path.exists(p):
            # 파일이 존재하고 테이블이 있는지 확인 (단순 경로 존재만으로는 부족할 수 있음)
            try:
                temp_conn = sqlite3.connect(p)
                temp_df = pd.read_sql("SELECT name FROM sqlite_master WHERE type='table' AND name='stores';", temp_conn)
                temp_conn.close()
                if not temp_df.empty:
                    db_path = p
                    break
            except:
                continue
    
    if db_path is None:
        raise FileNotFoundError(f"nemostore.db 파일을 찾을 수 없거나 'stores' 테이블이 없습니다. 시도한 경로: {paths_to_try}")

    conn = sqlite3.connect(db_path)
    query = "SELECT * FROM stores"
    df = pd.read_sql(query, conn)
    conn.close()
    
    # 데이터 정제
    cols_to_fill = ['deposit', 'monthlyRent', 'premium', 'maintenanceFee', 'size']
    df[cols_to_fill] = df[cols_to_fill].fillna(0)
    
    # ㎡당 월세 계산
    df['pricePerArea'] = (df['monthlyRent'] / df['size']).round(2)
    
    # 지하철역 이름만 추출
    df['subwayStation'] = df['nearSubwayStation'].str.split(',').str[0].str.strip()
    
    return df

# 데이터 로드
try:
    df = load_data()
except Exception as e:
    st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
    st.stop()

# 컬럼명 매핑 (한글화)
COL_MAP = {
    'title': '매물 제목',
    'businessLargeCodeName': '업종',
    'deposit': '보증금(만)',
    'monthlyRent': '월세(만)',
    'premium': '권리금(만)',
    'maintenanceFee': '관리비(만)',
    'floor': '층수',
    'size': '면적(㎡)',
    'nearSubwayStation': '상세 위치/지하철',
    'pricePerArea': '㎡당 월세(만)'
}

# 사이드바: 검색 필터
st.sidebar.header("🔍 상세 검색")

# 1. 검색어
search_query = st.sidebar.text_input("매물 제목 검색", placeholder="예: 해운대...")

# 2. 가격
st.sidebar.subheader("💰 가격 범위 (만원)")
deposit_range = st.sidebar.slider("보증금", int(df['deposit'].min()), int(df['deposit'].max()), (int(df['deposit'].min()), int(df['deposit'].max())))
rent_range = st.sidebar.slider("월세", int(df['monthlyRent'].min()), int(df['monthlyRent'].max()), (int(df['monthlyRent'].min()), int(df['monthlyRent'].max())))
premium_range = st.sidebar.slider("권리금", int(df['premium'].min()), int(df['premium'].max()), (int(df['premium'].min()), int(df['premium'].max())))

# 3. 업종 및 층수
st.sidebar.subheader("🏢 건물 정보")
selected_categories = st.sidebar.multiselect("업종 선택", df['businessLargeCodeName'].unique(), default=df['businessLargeCodeName'].unique())
selected_floors = st.sidebar.multiselect("층수 선택", sorted(df['floor'].unique()), default=df['floor'].unique())

# 데이터 필터링
filtered_df = df[
    (df['deposit'] >= deposit_range[0]) & (df['deposit'] <= deposit_range[1]) &
    (df['monthlyRent'] >= rent_range[0]) & (df['monthlyRent'] <= rent_range[1]) &
    (df['premium'] >= premium_range[0]) & (df['premium'] <= premium_range[1]) &
    (df['businessLargeCodeName'].isin(selected_categories)) &
    (df['floor'].isin(selected_floors))
]

if search_query:
    filtered_df = filtered_df[filtered_df['title'].str.contains(search_query, case=False, na=False)]

# 메인 레이아웃
st.title("🏬 네모스토어 상가 매물 분석 대시보드")
st.markdown("---")

# 탭 구성
tab1, tab2, tab3, tab4 = st.tabs(["📊 가격/업종 분석", "🖼️ 이미지 갤러리", "📍 위치 분석", "📋 데이터 상세"])

# --- Tab 1: 가격/업종 분석 ---
with tab1:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("검색된 매물", f"{len(filtered_df)}건")
    m2.metric("평균 월세", f"{filtered_df['monthlyRent'].mean():.0f}만")
    m3.metric("평균 권리금", f"{filtered_df['premium'].mean():.0f}만")
    m4.metric("평균 ㎡당 월세", f"{filtered_df['pricePerArea'].mean():.2f}만")

    st.markdown("---")
    
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("🏢 업종별 평균 가격")
        fig_biz = px.bar(filtered_df.groupby('businessLargeCodeName')['monthlyRent'].mean().reset_index(), 
                         x='businessLargeCodeName', y='monthlyRent', color='businessLargeCodeName',
                         labels={'businessLargeCodeName': '업종', 'monthlyRent': '평균 월세'},
                         title="업종별 평균 월세 비교")
        st.plotly_chart(fig_biz, use_container_width=True)

    with c2:
        st.subheader("🏗️ 층별 월세 분포")
        fig_floor = px.box(filtered_df, x='floor', y='monthlyRent', color='floor',
                           labels={'floor': '층', 'monthlyRent': '월세(만)'},
                           title="층수별 월세 범위 (가성비 확인)")
        st.plotly_chart(fig_floor, use_container_width=True)

# --- Tab 2: 이미지 갤러리 ---
with tab2:
    st.subheader("🖼️ 매물 실사진 갤러리")
    st.info("💡 이미지 아래 '상세보기' 버튼을 누르면 상세 제원과 가치 평가를 확인할 수 있습니다.")
    
    if len(filtered_df) == 0:
        st.warning("조건에 맞는 매물이 없습니다.")
    else:
        # 그리드 레이아웃
        n_cols = 4
        rows = (len(filtered_df) // n_cols) + (1 if len(filtered_df) % n_cols > 0 else 0)
        
        for r in range(rows):
            cols = st.columns(n_cols)
            for c in range(n_cols):
                idx = r * n_cols + c
                if idx < len(filtered_df):
                    row = filtered_df.iloc[idx]
                    with cols[c]:
                        # 이미지 파싱
                        try:
                            imgs = json.loads(row['smallPhotoUrls']) if row['smallPhotoUrls'] else []
                        except:
                            imgs = row['smallPhotoUrls'].split(',') if row['smallPhotoUrls'] else []
                        
                        img_url = imgs[0] if imgs else "https://via.placeholder.com/200?text=No+Image"
                        
                        st.image(img_url, use_container_width=True)
                        st.markdown(f"**{row['title'][:15]}**")
                        st.write(f"보증금: {row['deposit']} / 월세: {row['monthlyRent']}")
                        if st.button("상세보기", key=f"gal_{row['id']}"):
                            st.session_state.selected_article = row
                            st.rerun()

# --- 상세 페이지 레이아웃 (선택 시 표시) ---
if st.session_state.selected_article is not None:
    item = st.session_state.selected_article
    st.markdown("---")
    st.header(f"🔍 매물 상세 정보: {item['title']}")
    
    d1, d2 = st.columns([1, 1])
    with d1:
        try:
            o_imgs = json.loads(item['originPhotoUrls']) if item['originPhotoUrls'] else []
        except:
            o_imgs = item['originPhotoUrls'].split(',') if item['originPhotoUrls'] else []
        
        if o_imgs:
            st.image(o_imgs[0], caption=f"{item['title']} 원본 이미지", use_container_width=True)
        else:
            st.warning("상세 이미지가 없습니다.")
            
    with d2:
        st.subheader("📋 주요 제원")
        spec_data = {
            "업종": item['businessLargeCodeName'],
            "가격 (보증금/월세)": f"{item['deposit']} / {item['monthlyRent']} 만원",
            "권리금": f"{item['premium']} 만원",
            "관리비": f"{item['maintenanceFee']} 만원",
            "층수": f"{item['floor']} 층",
            "면적": f"{item['size']} ㎡",
            "지하철": item['nearSubwayStation']
        }
        st.table(pd.Series(spec_data).to_frame(name="정보"))
        
        # 벤치마킹 분석
        st.subheader("⚖️ 시장 가치 비교 (Benchmarking)")
        biz_avg = df[df['businessLargeCodeName'] == item['businessLargeCodeName']]['monthlyRent'].mean()
        diff = ((item['monthlyRent'] - biz_avg) / biz_avg * 100) if biz_avg > 0 else 0
        
        if diff < 0:
            st.success(f"✅ 동일 업종 평균 대비 **{abs(diff):.1f}% 저렴**한 매물입니다!")
        else:
            st.warning(f"⚠️ 동일 업종 평균 대비 **{diff:.1f}% 비싼** 편입니다.")
            
    if st.button("목록으로 돌아가기"):
        st.session_state.selected_article = None
        st.rerun()

# --- Tab 3: 위치 분석 ---
with tab3:
    st.subheader("📍 지역별 매물 밀집도 분석")
    st.info("💡 좌표 데이터 부재로 인해 지하철역 인근 분포로 대체하여 보여줍니다.")
    
    if 'subwayStation' in filtered_df.columns:
        station_counts = filtered_df['subwayStation'].value_counts().reset_index()
        station_counts.columns = ['subwayStation', 'count']
        
        fig_map = px.pie(station_counts, values='count', names='subwayStation', hole=0.4,
                         title="지하철역별 매물 분포 (상권 밀집도)",
                         labels={'subwayStation': '지하철역', 'count': '매물수'})
        st.plotly_chart(fig_map, use_container_width=True)
        
        st.subheader("🚇 지하철역별 평균 임대료")
        station_rent = filtered_df.groupby('subwayStation')['monthlyRent'].mean().reset_index()
        fig_station = px.bar(station_rent, x='subwayStation', y='monthlyRent', color='monthlyRent',
                             labels={'subwayStation': '지하철역', 'monthlyRent': '평균 월세'}, 
                             color_continuous_scale='Viridis')
        st.plotly_chart(fig_station, use_container_width=True)

# --- Tab 4: 데이터 상세 ---
with tab4:
    st.subheader("📋 필터링된 매물 데이터")
    
    # 한글화 및 선택적 표시
    list_df = filtered_df[list(COL_MAP.keys())].rename(columns=COL_MAP)
    
    # 다운로드 및 표시
    csv = list_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 필터링된 데이터 CSV 다운로드", csv, "nemostore_list.csv", "text/csv")
    
    st.dataframe(list_df, use_container_width=True)
