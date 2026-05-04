import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime

# --- 페이지 설정 ---
st.set_page_config(page_title="월말 정산표 초안 작성 POC", layout="wide")

# --- 경로 및 파일명 설정 ---
SAMPLE_DIR = "샘플데이터"
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
    
    # 1. 취합 및 증빙 매칭
    merged = pd.merge(exp_df, rec_df, on=['거래일자', '거래처명', '금액'], how='left')
    
    def check_status(row):
        if pd.notnull(row['파일명']): return "증빙 완료"
        return "증빙 누락"
    
    merged['매칭상태'] = merged.apply(check_status, axis=1)

    # 2. 계정과목 분류 (AI Mock 로직)
    def classify_account(row):
        merchant = str(row['거래처명'])
        if rule_df is not None:
            for _, r in rule_df.iterrows():
                if str(r['거래처 키워드']) in merchant:
                    return r['비용 항목'], r['계정과목'], 0.95
        
        if any(k in merchant for k in ['식당', '민족', '바게뜨']): return '복리후생비', '81100', 0.80
        if any(k in merchant for k in ['택시', 'T', '우버']): return '여비교통비', '81400', 0.85
        return '검토 필요', '미분류', 0.50

    results = merged.apply(classify_account, axis=1, result_type='expand')
    merged['AI비용항목'] = results[0]
    merged['AI계정과목'] = results[1]
    merged['신뢰도'] = results[2]
    
    # 초기 수정값 세팅
    merged['수정_비용항목'] = merged['AI비용항목']
    merged['수정_계정과목'] = merged['AI계정과목']
    
    return merged, round(time.time() - start_time, 2)

# --- UI 레이아웃 ---
st.title("📂 월말 정산표 초안 작성 POC 프로토타입")
st.info("💡 **안내:** AI 분석 결과는 초안일 뿐이며, 최종 회계 판단은 담당자가 수행해야 합니다.")

# 1. 데이터 입력 섹션
st.header("1. 데이터 입력")
col1, col2, col3 = st.columns(3)

with col1:
    exp_file = st.file_uploader("지출 내역 업로드", type=['csv', 'xlsx'])
with col2:
    rec_file = st.file_uploader("증빙 자료 목록 업로드", type=['csv', 'xlsx'])
with col3:
    rule_file = st.file_uploader("계정과목 기준표 (선택)", type=['csv', 'xlsx'])

if st.button("📁 '샘플데이터' 폴더 파일 로드"):
    if os.path.exists(FILE_PATHS["지출내역"]):
        st.session_state.exp_df = safe_read_csv(FILE_PATHS["지출내역"])
        st.session_state.rec_df = safe_read_csv(FILE_PATHS["증빙자료"])
        if os.path.exists(FILE_PATHS["계정과목"]):
            st.session_state.rule_df = safe_read_csv(FILE_PATHS["계정과목"])
        st.success("데이터 로드 완료")
    else:
        st.error("파일을 찾을 수 없습니다.")

if exp_file: st.session_state.exp_df = pd.read_csv(exp_file) if exp_file.name.endswith('csv') else pd.read_excel(exp_file)
if rec_file: st.session_state.rec_df = pd.read_csv(rec_file) if rec_file.name.endswith('csv') else pd.read_excel(rec_file)
if rule_file: st.session_state.rule_df = pd.read_csv(rule_file) if rule_file.name.endswith('csv') else pd.read_excel(rule_file)

# 2. 데이터 미리보기 및 분석 실행
if st.session_state.exp_df is not None:
    with st.expander("입력 데이터 미리보기"):
        t1, t2, t3 = st.tabs(["지출 내역", "증빙 자료", "계정과목 기준표"])
        with t1: st.dataframe(st.session_state.exp_df, use_container_width=True)
        with t2: st.dataframe(st.session_state.rec_df, use_container_width=True)
        with t3: st.dataframe(st.session_state.rule_df if st.session_state.rule_df is not None else pd.DataFrame(), use_container_width=True)

    if st.button("🤖 AI 초안 생성 시작", type="primary"):
        res, p_time = run_ai_analysis(st.session_state.exp_df, st.session_state.rec_df, st.session_state.rule_df)
        st.session_state.processed_data = res
        st.session_state.process_time = p_time
        st.session_state.analysis_done = True

# 3. 사용자 검토 및 수정
if st.session_state.analysis_done:
    st.header("2. AI 초안 검토 및 수정")
    df = st.session_state.processed_data
    
    st.markdown("##### 🔍 상세 검토 테이블")
    st.caption("수정 항목 컬럼을 더블 클릭하여 내용을 변경할 수 있습니다.")
    
    # 수정 가능한 테이블 (data_editor)
    edited_df = st.data_editor(
        df[['거래일자', '거래처명', '금액', '사용부서', '사용자', '매칭상태', 'AI비용항목', '수정_비용항목', 'AI계정과목', '수정_계정과목', '신뢰도']],
        use_container_width=True,
        column_config={
            "신뢰도": st.column_config.ProgressColumn("AI신뢰도", format="%.2f", min_value=0, max_value=1),
            "수정_비용항목": st.column_config.TextColumn("수정_비용항목 (최종)"),
            "수정_계정과목": st.column_config.TextColumn("수정_계정과목 (최종)")
        }
    )
    
    if st.button("✅ 검토 완료 및 데이터 반영"):
        st.session_state.processed_data.update(edited_df)
        st.success("사용자 수정 사항이 반영되었습니다. 아래에서 최종 정산표를 확인하세요.")

    # 4. 최종 정산표 미리보기 (NEW)
    st.divider()
    st.header("3. 최종 정산표 초안 미리보기")
    
    # 최종적으로 필요한 컬럼만 추출 및 이름 변경
    final_cols = ['거래일자', '거래처명', '금액', '사용부서', '사용자', '매칭상태', '수정_비용항목', '수정_계정과목']
    final_df = st.session_state.processed_data[final_cols].copy()
    final_df.columns = ['거래일자', '거래처명', '금액', '사용부서', '사용자', '증빙여부', '비용항목(확정)', '계정과목(확정)']
    
    st.markdown("##### 📋 확정된 정산 데이터")
    st.dataframe(final_df, use_container_width=True)

    # 5. POC 성과 대시보드
    st.divider()
    st.header("4. POC 성과 대시보드")
    
    total = len(df)
    mod_count = (df['AI비용항목'] != df['수정_비용항목']).sum()
    mod_rate = (mod_count / total * 100)
    missing_count = (df['매칭상태'] == "증빙 누락").sum()
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("전체 건수", f"{total}건")
    m2.metric("수정 비율", f"{mod_rate:.1f}%", delta="-30% 목표")
    m3.metric("처리 시간", f"{st.session_state.process_time}초")
    m4.metric("증빙 누락", f"{missing_count}건")

    # OKR 판정
    st.subheader("🎯 달성 여부")
    sat = st.slider("업무 효율 체감 점수 (1~5)", 1, 5, 4)
    
    kr_status = [mod_rate <= 30, st.session_state.process_time < 10, sat >= 4]
    score = sum(kr_status)
    
    if score >= 2: st.success(f"**판정: 확산 검토** (KR {score}/3 달성)")
    else: st.error(f"**판정: 재실험 필요** (KR {score}/3 달성)")

    # 다운로드 버튼
    csv = final_df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 최종 정산표 CSV 다운로드",
        data=csv,
        file_name=f"settlement_final_{datetime.now().strftime('%Y%m%d')}.csv",
        mime='text/csv'
    )
