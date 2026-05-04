import streamlit as st
import pandas as pd
import time
from datetime import datetime

# 페이지 설정
st.set_page_config(page_title="지출 정산 AI 초안 PoC", layout="wide")

# --- 세션 상태 초기화 ---
if 'step' not in st.session_state:
    st.session_state.step = 'upload'
if 'raw_data' not in st.session_state:
    st.session_state.raw_data = None
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'start_time' not in st.session_state:
    st.session_state.start_time = None

# --- AI Mock 로직 ---
def run_ai_analysis(df):
    """규칙 기반으로 AI 초안 생성 및 누락 항목 식별"""
    # 1. 카테고리 분류 초안
    def classify(vendor):
        vendor = str(vendor)
        if any(keyword in vendor for keyword in ['식당', '푸드', '밥', '기사']): return '식대'
        if any(keyword in vendor for keyword in ['택시', '철도', '버스', '카카오T']): return '여비교통비'
        if any(keyword in vendor for keyword in ['마트', '편의점', '다이소']): return '소모품비'
        if any(keyword in vendor for keyword in ['카페', '스타벅스', '투썸']): return '복리후생비'
        return '기타'

    df['비용항목(AI추천)'] = df['거래처명'].apply(classify)
    
    # 2. 누락 의심 항목 (3만원 이상인데 증빙이 '없음'인 경우)
    df['누락의심'] = False
    if '금액' in df.columns and '증빙여부' in df.columns:
        df.loc[(df['금액'] >= 30000) & (df['증빙여부'] == '없음'), '누락의심'] = True
    
    return df

# --- UI 화면 구성 ---

st.title("📂 지출 정산 AI 초안 생성 PoC")
st.caption("이 앱은 AI 초안을 활용한 정산표 작성 시간 단축 가능성을 검증하기 위한 프로토타입입니다.")

# 사이드바: 로그 및 지표 표시
with st.sidebar:
    st.header("📊 실시간 검증 지표")
    if st.session_state.start_time:
        elapsed = time.time() - st.session_state.start_time
        st.metric("진행 시간", f"{elapsed:.1f} 초")
    
    if st.session_state.processed_data is not None:
        suspicious_count = st.session_state.processed_data['누락의심'].sum()
        st.metric("누락 의심 항목", f"{suspicious_count} 건")

# Step 1: 파일 업로드
if st.session_state.step == 'upload':
    st.subheader("1. 파일 업로드")
    uploaded_file = st.file_uploader("엑셀 또는 CSV 파일을 선택하세요", type=['csv', 'xlsx'])
    
    if uploaded_file:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        
        st.session_state.raw_data = df
        st.success("파일 업로드 완료!")
        if st.button("데이터 확인 및 분석 시작"):
            st.session_state.step = 'preview'
            st.rerun()

# Step 2: 데이터 미리보기 및 AI 분석 실행
elif st.session_state.step == 'preview':
    st.subheader("2. 데이터 미리보기")
    st.dataframe(st.session_state.raw_data, use_container_width=True)
    
    if st.button("AI 분석 실행 (초안 생성)"):
        st.session_state.start_time = time.time() # 시간 측정 시작
        with st.spinner('AI가 항목을 분류하고 누락 내역을 찾는 중...'):
            time.sleep(1.5) # 분석 시뮬레이션
            st.session_state.processed_data = run_ai_analysis(st.session_state.raw_data.copy())
            st.session_state.step = 'edit'
            st.rerun()

# Step 3: 사용자 수정 (가장 중요한 검증 단계)
elif st.session_state.step == 'edit':
    st.subheader("3. AI 분석 결과 검토 및 수정")
    st.info("💡 AI가 추천한 '비용항목'을 확인하고 필요한 경우 수정하세요. 빨간색 강조(누락의심) 항목을 확인하세요.")

    # 수정 가능한 테이블 제공
    # '누락의심' 항목 시각화 조절 (Streamlit에서 행 색상 변경은 스타일링 함수 사용)
    def highlight_suspicious(s):
        return ['background-color: #ffcccc' if s.누락의심 else '' for _ in s]

    edited_df = st.data_editor(
        st.session_state.processed_data,
        column_config={
            "비용항목(AI추천)": st.column_config.SelectboxColumn(
                "비용항목(최종)",
                options=["식대", "여비교통비", "소모품비", "복리후생비", "기타"],
                required=True,
            ),
            "누락의심": st.column_config.CheckboxColumn("누락여부 확인", disabled=True)
        },
        disabled=["거래일자", "거래처명", "금액"], # 원본 데이터는 보호
        use_container_width=True,
        num_rows="fixed"
    )

    if st.button("최종 정산표 확정"):
        # 수정 로그 계산
        diff = (st.session_state.processed_data['비용항목(AI추천)'] != edited_df['비용항목(AI추천)']).sum()
        st.session_state.edit_count = diff
        st.session_state.final_data = edited_df
        st.session_state.end_time = time.time()
        st.session_state.step = 'final'
        st.rerun()

# Step 4: 최종 결과 및 로그
elif st.session_state.step == 'final':
    st.subheader("4. 최종 정산표 출력")
    
    duration = st.session_state.end_time - st.session_state.start_time
    
    col1, col2, col3 = st.columns(3)
    col1.metric("총 처리 시간", f"{duration:.1f} 초")
    col2.metric("사용자 수정 항목 수", f"{st.session_state.edit_count} 건")
    col3.metric("최종 확정 건수", f"{len(st.session_state.final_data)} 건")

    st.dataframe(st.session_state.final_data, use_container_width=True)
    
    # 결과 로그 출력 (PoC 검증용)
    st.divider()
    st.code(f"""
    [PoC Validation Log]
    - Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    - Processing Time: {duration:.2f}s
    - Items Modified by User: {st.session_state.edit_count}
    - Accuracy Draft Rate: {((len(st.session_state.final_data)-st.session_state.edit_count)/len(st.session_state.final_data))*100:.1f}%
    """)
    
    if st.button("처음으로 돌아가기"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
