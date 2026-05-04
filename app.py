import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime

# --- 페이지 설정 ---
st.set_page_config(page_title="월말 정산표 초안 작성 POC", layout="wide")

# --- 경로 설정 ---
SAMPLE_DIR = "샘플데이터"
FILES = {
    "지출내역": os.path.join(SAMPLE_DIR, "지출내역.csv"),
    "증빙자료": os.path.join(SAMPLE_DIR, "증빙자료.csv"),
    "계정과목": os.path.join(SAMPLE_DIR, "계정과목 기준표.csv")
}

# --- 세션 상태 초기화 ---
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False

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
        merchant = row['거래처명']
        # 기준표 매칭
        if rule_df is not None:
            for _, r in rule_df.iterrows():
                if r['거래처 키워드'] in merchant:
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
st.info("💡 **안내:** 이 프로토타입은 회계 판단을 자동화하지 않습니다. 모든 결과는 담당자의 검토가 필요합니다.")

# 1. 데이터 입력 섹션
st.header("1. 데이터 입력")
col1, col2, col3 = st.columns(3)

with col1:
    exp_file = st.file_uploader("지출 내역 업로드", type=['csv', 'xlsx'])
with col2:
    rec_file = st.file_uploader("증빙 자료 목록 업로드", type=['csv', 'xlsx'])
with col3:
    rule_file = st.file_uploader("계정과목 기준표 (선택)", type=['csv', 'xlsx'])

st.markdown("---")
use_sample = st.button("📁 '샘플데이터' 폴더 파일로 실행")

# 데이터 로드
exp_df, rec_df, rule_df = None, None, None

if use_sample:
    if os.path.exists(FILES["지출내역"]) and os.path.exists(FILES["증빙자료"]):
        exp_df = pd.read_csv(FILES["지출내역"])
        rec_df = pd.read_csv(FILES["증빙자료"])
        if os.path.exists(FILES["계정과목"]):
            rule_df = pd.read_csv(FILES["계정과목"])
        st.success("샘플 폴더에서 데이터를 성공적으로 불러왔습니다.")
    else:
        st.error("샘플데이터 폴더 내에 파일이 존재하지 않습니다.")
elif exp_file and rec_file:
    exp_df = pd.read_csv(exp_file) if exp_file.name.endswith('csv') else pd.read_excel(exp_file)
    rec_df = pd.read_csv(rec_file) if rec_file.name.endswith('csv') else pd.read_excel(rec_file)
    if rule_file:
        rule_df = pd.read_csv(rule_file) if rule_file.name.endswith('csv') else pd.read_excel(rule_file)

# 2. 데이터 미리보기 및 분석
if exp_df is not None and rec_df is not None:
    with st.expander("입력 데이터 미리보기"):
        st.subheader("지출 내역")
        st.dataframe(exp_df.head(5), use_container_width=True)
        st.subheader("증빙 자료")
        st.dataframe(rec_df.head(5), use_container_width=True)

    if st.button("🤖 AI 초안 생성 시작"):
        processed_df, p_time = run_ai_analysis(exp_df, rec_df, rule_df)
        st.session_state.processed_data = processed_df
        st.session_state.process_time = p_time
        st.session_state.analysis_done = True

# 3. 분석 결과 및 사용자 검토
if st.session_state.analysis_done:
    df = st.session_state.processed_data
    st.header("2. AI 분석 결과 및 사용자 검토")
    
    tab1, tab2, tab3 = st.tabs(["📋 전체 취합 목록", "⚠️ 누락 의심", "🔍 분류 초안 수정"])
    
    with tab1:
        st.dataframe(df[['거래일자', '거래처명', '금액', '매칭상태', 'AI비용항목']], use_container_width=True)
    
    with tab2:
        missing = df[df['매칭상태'].str.contains("누락")]
        st.warning(f"누락 의심 항목 {len(missing)}건이 발견되었습니다.")
        st.table(missing[['거래일자', '거래처명', '금액', '사용자', '누락판단근거']])
        
    with tab3:
        st.caption("AI 제안 항목을 확인하고 수정하세요.")
        edited_df = st.data_editor(
            df[['거래일자', '거래처명', '금액', 'AI비용항목', '수정_비용항목', 'AI계정과목', '수정_계정과목', '신뢰도']],
            use_container_width=True,
            key="editor"
        )
        if st.button("수정 사항 확정"):
            st.session_state.processed_data.update(edited_df)
            st.toast("저장되었습니다.")

    # 4. 성과 대시보드
    st.divider()
    st.header("3. POC 성과 대시보드")
    
    total = len(df)
    modified_count = (df['AI비용항목'] != df['수정_비용항목']).sum()
    mod_rate = (modified_count / total * 100)
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("전체 건수", f"{total}건")
    c2.metric("AI 수정 비율", f"{mod_rate:.1f}%", delta="-30% 목표")
    c3.metric("처리 시간", f"{st.session_state.process_time}초")
    
    with st.expander("최종 성과 판정"):
        precision_input = st.number_input("실제 누락 확인 건수", value=len(missing))
        sat_score = st.slider("업무 효율 만족도", 1, 5, 4)
        
        # OKR 판정
        kr1 = mod_rate <= 30
        kr2 = (precision_input / len(missing) >= 0.7) if len(missing) > 0 else True
        kr3 = sat_score >= 4
        success_count = sum([kr1, kr2, kr3])
        
        if success_count >= 2: st.success(f"### 결과: 확산 검토 ({success_count}/3 달성)")
        else: st.error(f"### 결과: 개선 필요 ({success_count}/3 달성)")

    st.download_button("📥 최종 정산표 다운로드", df.to_csv(index=False).encode('utf-8-sig'), "정산표_초안.csv", "text/csv")
