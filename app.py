import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime

# --- 페이지 설정 ---
st.set_page_config(page_title="월말 정산표 초안 작성 POC", layout="wide")

# --- 경로 및 파일명 설정 ---
SAMPLE_DIR = "샘플데이터"
# 파일명이 실제 폴더 내 파일명과 정확히 일치해야 합니다.
FILE_PATHS = {
    "지출내역": os.path.join(SAMPLE_DIR, "지출내역.csv"),
    "증빙자료": os.path.join(SAMPLE_DIR, "증빙자료.csv"),
    "계정과목": os.path.join(SAMPLE_DIR, "계정과목 기준표.csv")
}

# --- 세션 상태 초기화 (데이터 휘발 방지) ---
if 'exp_df' not in st.session_state: st.session_state.exp_df = None
if 'rec_df' not in st.session_state: st.session_state.rec_df = None
if 'rule_df' not in st.session_state: st.session_state.rule_df = None
if 'processed_data' not in st.session_state: st.session_state.processed_data = None
if 'analysis_done' not in st.session_state: st.session_state.analysis_done = False
if 'process_time' not in st.session_state: st.session_state.process_time = 0

# --- CSV 읽기 함수 (인코딩 예외 처리) ---
def safe_read_csv(path):
    try:
        return pd.read_csv(path, encoding='utf-8-sig')
    except:
        return pd.read_csv(path, encoding='cp949')

# --- 핵심 로직: AI Mock 분석 함수 ---
def run_ai_analysis(exp_df, rec_df, rule_df):
    start_time = time.time()
    
    # 1. 취합 및 증빙 매칭 (거래일자, 거래처명, 금액 기준)
    merged = pd.merge(exp_df, rec_df, on=['거래일자', '거래처명', '금액'], how='left')
    
    def check_status(row):
        if pd.notnull(row['파일명']): return "일치 (증빙확인)"
        return "누락 의심 (증빙없음)"
    
    merged['매칭상태'] = merged.apply(check_status, axis=1)
    merged['누락판단근거'] = merged['매칭상태'].apply(lambda x: "증빙 파일 매칭 실패" if "누락" in x else "정상 매칭")

    # 2. 계정과목 분류 (AI Mock 로직)
    def classify_account(row):
        merchant = str(row['거래처명'])
        # 기준표 매칭 로직
        if rule_df is not None:
            for _, r in rule_df.iterrows():
                if str(r['거래처 키워드']) in merchant:
                    return r['비용 항목'], r['계정과목'], 0.95
        
        # 기본 규칙 (Fallback)
        if any(k in merchant for k in ['식당', '민족', '바게뜨']): return '복리후생비', '81100', 0.80
        if any(k in merchant for k in ['택시', 'T', '우버']): return '여비교통비', '81400', 0.85
        return '검토 필요', '미분류', 0.50

    results = merged.apply(classify_account, axis=1, result_type='expand')
    merged['AI비용항목'] = results[0]
    merged['AI계정과목'] = results[1]
    merged['신뢰도'] = results[2]
    
    # 사용자 수정용 컬럼
    merged['수정_비용항목'] = merged['AI비용항목']
    merged['수정_계정과목'] = merged['AI계정과목']
    
    return merged, round(time.time() - start_time, 2)

# --- UI 레이아웃 ---
st.title("📂 월말 정산표 초안 작성 POC 프로토타입")
st.info("이 프로토타입은 회계 판단을 자동화하지 않습니다. 모든 결과는 담당자의 검토가 필요합니다.")

# 1. 데이터 입력 섹션
st.header("1. 데이터 입력")
col1, col2, col3 = st.columns(3)

with col1:
    exp_file = st.file_uploader("지출 내역 업로드", type=['csv', 'xlsx'])
with col2:
    rec_file = st.file_uploader("증빙 자료 목록 업로드", type=['csv', 'xlsx'])
with col3:
    rule_file = st.file_uploader("계정과목 기준표 (선택)", type=['csv', 'xlsx'])

# 샘플 데이터 불러오기 버튼
if st.button("📁 '샘플데이터' 폴더 파일 로드"):
    if os.path.exists(FILE_PATHS["지출내역"]) and os.path.exists(FILE_PATHS["증빙자료"]):
        st.session_state.exp_df = safe_read_csv(FILE_PATHS["지출내역"])
        st.session_state.rec_df = safe_read_csv(FILE_PATHS["증빙자료"])
        if os.path.exists(FILE_PATHS["계정과목"]):
            st.session_state.rule_df = safe_read_csv(FILE_PATHS["계정과목"])
        st.success("데이터를 성공적으로 불러왔습니다. 아래에서 확인하세요.")
    else:
        st.error(f"파일을 찾을 수 없습니다. 경로를 확인하세요: {SAMPLE_DIR}")

# 파일 업로드 시 세션에 저장
if exp_file: st.session_state.exp_df = pd.read_csv(exp_file) if exp_file.name.endswith('csv') else pd.read_excel(exp_file)
if rec_file: st.session_state.rec_df = pd.read_csv(rec_file) if rec_file.name.endswith('csv') else pd.read_excel(rec_file)
if rule_file: st.session_state.rule_df = pd.read_csv(rule_file) if rule_file.name.endswith('csv') else pd.read_excel(rule_file)

# 2. 데이터 미리보기 (데이터가 세션에 있을 때만 표시)
if st.session_state.exp_df is not None:
    with st.expander("입력 데이터 미리보기", expanded=True):
        c1, c2, c3 = st.tabs(["지출 내역", "증빙 자료", "계정과목 기준표"])
        with c1: st.dataframe(st.session_state.exp_df, use_container_width=True)
        with c2: st.dataframe(st.session_state.rec_df, use_container_width=True)
        with c3:
            if st.session_state.rule_df is not None:
                st.dataframe(st.session_state.rule_df, use_container_width=True)
            else:
                st.info("로드된 계정과목 기준표가 없습니다.")

    # 3. AI 분석 실행 버튼
    if st.button("🤖 AI 초안 생성 시작", type="primary"):
        with st.spinner("분석 중..."):
            processed_df, p_time = run_ai_analysis(
                st.session_state.exp_df, 
                st.session_state.rec_df, 
                st.session_state.rule_df
            )
            st.session_state.processed_data = processed_df
            st.session_state.process_time = p_time
            st.session_state.analysis_done = True
        st.balloons()

# 4. 분석 결과 및 사용자 검토
if st.session_state.analysis_done:
    df = st.session_state.processed_data
    st.header("2. AI 분석 결과 및 사용자 검토")
    
    tab1, tab2, tab3 = st.tabs(["📋 전체 취합 목록", "⚠️ 누락 의심 항목", "🔍 분류 초안 수정"])
    
    with tab1:
        st.dataframe(df[['거래일자', '거래처명', '금액', '매칭상태', 'AI비용항목', 'AI계정과목']], use_container_width=True)
    
    with tab2:
        missing = df[df['매칭상태'].str.contains("누락")]
        st.warning(f"누락 의심 항목 {len(missing)}건이 발견되었습니다.")
        st.table(missing[['거래일자', '거래처명', '금액', '사용자', '누락판단근거']])
        
    with tab3:
        st.markdown("##### 📝 항목 수정")
        edited_df = st.data_editor(
            df[['거래일자', '거래처명', '금액', 'AI비용항목', '수정_비용항목', 'AI계정과목', '수정_계정과목', '신뢰도']],
            use_container_width=True,
            key="editor"
        )
        if st.button("수정 사항 확정 저장"):
            st.session_state.processed_data.update(edited_df)
            st.toast("변경 사항이 저장되었습니다.")

    # 5. 성과 대시보드
    st.divider()
    st.header("3. POC 성과 대시보드")
    
    total = len(df)
    modified_count = (df['AI비용항목'] != df['수정_비용항목']).sum()
    mod_rate = (modified_count / total * 100)
    
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric("전체 건수", f"{total}건")
    col_m2.metric("수정 비율", f"{mod_rate:.1f}%", delta="-30% 목표")
    col_m3.metric("처리 시간", f"{st.session_state.process_time}초")
    col_m4.metric("누락 의심", f"{len(missing)}건")
    
    # 성과 판정 섹션
    st.subheader("🎯 최종 성과 판정")
    res_c1, res_c2 = st.columns(2)
    with res_c1:
        precision_input = st.number_input("실제 누락 확인 건수 (사용자 검토 결과)", value=len(missing))
        sat_score = st.slider("업무 효율 만족도 (1~5점)", 1, 5, 4)
    
    with res_c2:
        precision = (precision_input / len(missing) * 100) if len(missing) > 0 else 100
        kr_checks = [mod_rate <= 30, precision >= 70, sat_score >= 4]
        success_count = sum(kr_checks)
        
        if success_count >= 2:
            st.success(f"### 결과: 확산 검토 추천 ({success_count}/3 달성)")
        else:
            st.error(f"### 결과: 보완 필요 ({success_count}/3 달성)")

    st.download_button(
        "📥 최종 정산표 다운로드", 
        st.session_state.processed_data.to_csv(index=False).encode('utf-8-sig'), 
        "정산표_초안.csv", 
        "text/csv"
    )
