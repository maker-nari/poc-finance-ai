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

# --- 세션 상태 초기화 ---
if 'exp_df' not in st.session_state: st.session_state.exp_df = None
if 'rec_df' not in st.session_state: st.session_state.rec_df = None
if 'rule_df' not in st.session_state: st.session_state.rule_df = None
if 'processed_data' not in st.session_state: st.session_state.processed_data = None
if 'analysis_done' not in st.session_state: st.session_state.analysis_done = False
if 'process_time' not in st.session_state: st.session_state.process_time = 0

# --- CSV 읽기 함수 ---
def safe_read_csv(path):
    try:
        return pd.read_csv(path, encoding='utf-8-sig')
    except:
        return pd.read_csv(path, encoding='cp949')

# --- AI 분석 로직 (초안 생성) ---
def run_ai_analysis(exp_df, rec_df, rule_df):
    start_time = time.time()
    
    # 1. 증빙 매칭
    merged = pd.merge(exp_df, rec_df, on=['거래일자', '거래처명', '금액'], how='left')
    merged['매칭상태'] = merged.apply(lambda x: "증빙 완료" if pd.notnull(x['파일명']) else "증빙 누락", axis=1)

    # 2. 계정과목 분류 (AI Mock)
    def classify(row):
        merchant = str(row['거래처명'])
        if rule_df is not None:
            for _, r in rule_df.iterrows():
                if str(r['거래처 키워드']) in merchant:
                    return r['비용 항목'], r['계정과목'], 0.95
        if any(k in merchant for k in ['식당', '민족', '바게뜨']): return '복리후생비', '81100', 0.80
        if any(k in merchant for k in ['택시', 'T', '우버']): return '여비교통비', '81400', 0.85
        return '검토 필요', '미분류', 0.50

    results = merged.apply(classify, axis=1, result_type='expand')
    merged['AI비용항목'] = results[0]
    merged['AI계정과목'] = results[1]
    merged['신뢰도'] = results[2]
    
    # [중요] 사용자가 수정할 '최종' 컬럼을 AI 초안으로 초기화
    merged['최종_비용항목'] = merged['AI비용항목']
    merged['최종_계정과목'] = merged['AI계정과목']
    
    return merged, round(time.time() - start_time, 2)

# --- 메인 UI ---
st.title("📂 월말 정산표 초안 작성 POC")
st.write("사용자는 AI가 생성한 초안을 검토하고, 틀린 부분을 직접 수정하여 정산표를 완성합니다.")

# 1. 데이터 입력
st.header("1. 데이터 입력")
col1, col2, col3 = st.columns(3)
with col1: exp_file = st.file_uploader("지출 내역 업로드", type=['csv', 'xlsx'])
with col2: rec_file = st.file_uploader("증빙 자료 목록 업로드", type=['csv', 'xlsx'])
with col3: rule_file = st.file_uploader("계정과목 기준표 (선택)", type=['csv', 'xlsx'])

if st.button("📁 '샘플데이터' 폴더 파일 로드"):
    if os.path.exists(FILE_PATHS["지출내역"]):
        st.session_state.exp_df = safe_read_csv(FILE_PATHS["지출내역"])
        st.session_state.rec_df = safe_read_csv(FILE_PATHS["증빙자료"])
        if os.path.exists(FILE_PATHS["계정과목"]):
            st.session_state.rule_df = safe_read_csv(FILE_PATHS["계정과목"])
        st.success("데이터 로드 완료")
    else: st.error("샘플 파일을 찾을 수 없습니다.")

# 업로드 시 데이터 저장
if exp_file: st.session_state.exp_df = pd.read_csv(exp_file) if exp_file.name.endswith('csv') else pd.read_excel(exp_file)
if rec_file: st.session_state.rec_df = pd.read_csv(rec_file) if rec_file.name.endswith('csv') else pd.read_excel(rec_file)
if rule_file: st.session_state.rule_df = pd.read_csv(rule_file) if rule_file.name.endswith('csv') else pd.read_excel(rule_file)

# 2. AI 분석 실행
if st.session_state.exp_df is not None:
    if st.button("🤖 AI 초안 생성 시작", type="primary"):
        res, p_time = run_ai_analysis(st.session_state.exp_df, st.session_state.rec_df, st.session_state.rule_df)
        st.session_state.processed_data = res
        st.session_state.process_time = p_time
        st.session_state.analysis_done = True

# 3. AI 초안 검토 및 수정 (핵심 영역)
if st.session_state.analysis_done:
    st.divider()
    st.header("2. AI 초안 검토 및 수정")
    st.info("💡 **수정 방법:** 아래 표에서 '최종_비용항목'이나 '최종_계정과목' 셀을 **더블 클릭**하여 내용을 직접 수정하세요.")

    # 편집 가능한 컬럼 정의
    # 사용자는 AI가 추천한 값을 보고 '최종' 컬럼만 수정하면 됨
    display_df = st.session_state.processed_data[[
        '거래일자', '거래처명', '금액', '매칭상태', 
        'AI비용항목', '최종_비용항목', 
        'AI계정과목', '최종_계정과목', '신뢰도'
    ]]

    # st.data_editor를 사용하여 수정 가능하게 구현
    edited_df = st.data_editor(
        display_df,
        use_container_width=True,
        column_config={
            "신뢰도": st.column_config.ProgressColumn("AI신뢰도", format="%.2f", min_value=0, max_value=1),
            "최종_비용항목": st.column_config.SelectboxColumn(
                "최종_비용항목", 
                options=["회의비", "접대비", "복리후생비", "여비교통비", "지급수수료", "소모품비", "도서인쇄비"],
                help="AI 제안이 틀렸다면 올바른 항목으로 변경하세요."
            ),
            "최종_계정과목": st.column_config.TextColumn("최종_계정과목")
        },
        disabled=["거래일자", "거래처명", "금액", "매칭상태", "AI비용항목", "AI계정과목", "신뢰도"], # 읽기 전용 컬럼
        key="main_editor"
    )

    # 수정된 데이터를 세션 상태에 즉시 동기화
    if st.session_state.processed_data is not None:
        st.session_state.processed_data.update(edited_df)

    # 4. 최종 정산표 미리보기 (수정 내용 반영됨)
    st.header("3. 최종 정산표 미리보기")
    
    # 미리보기용 데이터 정제
    final_view = st.session_state.processed_data[[
        '거래일자', '거래처명', '금액', '매칭상태', '최종_비용항목', '최종_계정과목'
    ]].copy()
    final_view.columns = ['거래일자', '거래처명', '금액', '증빙여부', '비용항목(확정)', '계정과목(확정)']
    
    st.dataframe(final_view, use_container_width=True)

    # 5. 성과 대시보드
    st.divider()
    st.header("4. POC 성과 분석")
    
    total = len(st.session_state.processed_data)
    # AI 초안(AI비용항목)과 사용자 수정(최종_비용항목)이 다른 건수 계산
    mod_count = (st.session_state.processed_data['AI비용항목'] != st.session_state.processed_data['최종_비용항목']).sum()
    mod_rate = (mod_count / total * 100)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("전체 항목", f"{total}건")
    m2.metric("AI 초안 수정 비율", f"{mod_rate:.1f}%", delta="30% 이하 목표")
    m3.metric("분석 소요 시간", f"{st.session_state.process_time}초")

    # 결과 판정
    st.subheader("🎯 최종 OKR 달성 판정")
    user_score = st.slider("담당자 업무 효율 체감 점수 (1~5)", 1, 5, 4)
    
    is_mod_ok = mod_rate <= 30
    is_sat_ok = user_score >= 4
    
    if is_mod_ok and is_sat_ok:
        st.success("✅ **POC 성공: 확산 검토 가능** (수정 비율 및 만족도 기준 충족)")
    else:
        st.warning("⚠️ **POC 개선 필요: 추가 실험 권장** (지표 미달성)")

    # 다운로드
    st.download_button(
        "📥 확정된 정산표 CSV 다운로드", 
        final_view.to_csv(index=False).encode('utf-8-sig'), 
        "final_settlement.csv", 
        "text/csv"
    )
