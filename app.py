import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime

# --- 페이지 설정 ---
st.set_page_config(page_title="AI 월말 정산 도우미 POC", layout="wide")

# --- 경로 및 파일명 설정 (파일명을 정확히 맞춥니다) ---
SAMPLE_DIR = "샘플데이터"
FILE_PATHS = {
    "지출내역": os.path.join(SAMPLE_DIR, "지출내역.csv"),
    "증빙자료": os.path.join(SAMPLE_DIR, "증빙자료.csv"),
    "계정과목": os.path.join(SAMPLE_DIR, "계정과목 기준표.csv") # 파일명 띄어쓰기 주의
}

# --- 세션 상태 초기화 ---
if 'exp_df' not in st.session_state: st.session_state.exp_df = None
if 'rec_df' not in st.session_state: st.session_state.rec_df = None
if 'rule_df' not in st.session_state: st.session_state.rule_df = None
if 'processed_data' not in st.session_state: st.session_state.processed_data = None
if 'analysis_done' not in st.session_state: st.session_state.analysis_done = False
if 'mapping_dict' not in st.session_state: st.session_state.mapping_dict = {}

# --- 데이터 처리 함수 ---
def preprocess_df(df):
    if df is not None:
        df.columns = [str(c).strip().replace('\ufeff', '') for c in df.columns]
    return df

def safe_read_csv(path):
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, encoding='utf-8-sig')
    except:
        df = pd.read_csv(path, encoding='cp949')
    return preprocess_df(df)

def create_mapping_dict(rule_df):
    # 기본 매핑 규칙
    base_mapping = {
        "회의비": "81100", "접대비": "81300", "복리후생비": "81100",
        "여비교통비": "81400", "지급수수료": "84500", "소모품비": "82200",
        "도서인쇄비": "82600", "검토 필요": "미분류"
    }
    # 기준표가 로드되었다면 해당 내용으로 업데이트
    if rule_df is not None:
        for _, row in rule_df.iterrows():
            item = str(row.get('비용 항목', '')).strip()
            code = str(row.get('계정과목', '')).strip()
            if item and code:
                base_mapping[item] = code
    st.session_state.mapping_dict = base_mapping
    return base_mapping

def run_ai_analysis(exp_df, rec_df, rule_df):
    start_time = time.time()
    mapping = create_mapping_dict(rule_df)
    
    # 1. 증빙 매칭
    merged = pd.merge(exp_df, rec_df, on=['거래일자', '거래처명', '금액'], how='left')
    merged['매칭상태'] = merged.apply(lambda x: "✅ 증빙 완료" if pd.notnull(x.get('파일명')) else "❗ 증빙 누락", axis=1)

    # 2. AI 분류 (기준표 기반 우선 순위)
    def classify(row):
        merchant = str(row.get('거래처명', ''))
        if rule_df is not None:
            for _, r in rule_df.iterrows():
                keyword = str(r.get('거래처 키워드', ''))
                if keyword in merchant:
                    item = r.get('비용 항목', '검토 필요')
                    return item, mapping.get(item, "미분류"), 0.95
        
        # 기본 규칙 (Fallback)
        if any(k in merchant for k in ['식당', '민족', '바게뜨']): return '복리후생비', mapping.get('복리후생비'), 0.80
        if any(k in merchant for k in ['택시', 'T', '우버']): return '여비교통비', mapping.get('여비교통비'), 0.85
        return '검토 필요', '미분류', 0.50

    results = merged.apply(classify, axis=1, result_type='expand')
    merged['AI비용항목'] = results[0]
    merged['AI계정과목'] = results[1]
    merged['신뢰도'] = results[2]
    merged['최종_비용항목'] = merged['AI비용항목']
    merged['최종_계정과목'] = merged['AI계정과목']
    
    return merged, round(time.time() - start_time, 2)

# --- UI 시작 ---
st.title("📑 AI 월말 정산 도우미 (POC)")

# 1단계: 데이터 입력
st.header("1단계: 데이터 준비하기")
col1, col2, col3 = st.columns(3)
with col1: exp_file = st.file_uploader("💳 지출 내역", type=['csv', 'xlsx'])
with col2: rec_file = st.file_uploader("📄 증빙 자료 목록", type=['csv', 'xlsx'])
with col3: rule_file = st.file_uploader("📋 계정과목 기준표 (선택)", type=['csv', 'xlsx'])

if st.button("📁 샘플 데이터로 바로 시작해보기"):
    st.session_state.exp_df = safe_read_csv(FILE_PATHS["지출내역"])
    st.session_state.rec_df = safe_read_csv(FILE_PATHS["증빙자료"])
    st.session_state.rule_df = safe_read_csv(FILE_PATHS["계정과목"])
    
    if st.session_state.exp_df is not None:
        st.success("샘플 데이터를 성공적으로 불러왔습니다!")
        if st.session_state.rule_df is None:
            st.warning("⚠️ '계정과목 기준표.csv' 파일을 찾을 수 없습니다. 기본 규칙으로 진행합니다.")
    else:
        st.error("샘플 파일을 찾을 수 없습니다. '샘플데이터' 폴더에 CSV 파일들이 있는지 확인해 주세요.")

# 업로드 파일 세션 반영
if exp_file: st.session_state.exp_df = preprocess_df(pd.read_csv(exp_file) if exp_file.name.endswith('csv') else pd.read_excel(exp_file))
if rec_file: st.session_state.rec_df = preprocess_df(pd.read_csv(rec_file) if rec_file.name.endswith('csv') else pd.read_excel(rec_file))
if rule_file: st.session_state.rule_df = preprocess_df(pd.read_csv(rule_file) if rule_file.name.endswith('csv') else pd.read_excel(rule_file))

# [중요] 미리보기 탭에 계정과목 기준표 추가
if st.session_state.exp_df is not None:
    with st.expander("👀 로드된 데이터 미리보기", expanded=True):
        t1, t2, t3 = st.tabs(["지출 내역", "증빙 자료", "계정과목 기준표"])
        with t1:
            st.dataframe(st.session_state.exp_df.head(10), use_container_width=True)
        with t2:
            st.dataframe(st.session_state.rec_df.head(10), use_container_width=True)
        with t3:
            if st.session_state.rule_df is not None:
                st.dataframe(st.session_state.rule_df, use_container_width=True)
            else:
                st.info("💡 현재 로드된 사용자 정의 기준표가 없습니다. 업로드하거나 샘플 파일을 확인해 주세요.")

    # 2단계: AI 분석
    st.header("2단계: AI 분석 및 초안 생성")
    if st.button("🤖 AI 초안 생성 시작", type="primary"):
        with st.spinner("분석 중..."):
            res, p_time = run_ai_analysis(st.session_state.exp_df, st.session_state.rec_df, st.session_state.rule_df)
            st.session_state.processed_data = res
            st.session_state.process_time = p_time
            st.session_state.analysis_done = True
        st.success("분석 완료!")

# 3단계: 사용자 검토 (자동 매핑 포함)
if st.session_state.analysis_done:
    st.divider()
    st.header("3단계: AI 초안 검토 및 수정")
    st.info("💡 **최종_비용항목**을 변경하면 **최종_계정과목**이 자동으로 업데이트됩니다.")

    df_to_edit = st.session_state.processed_data.copy()
    
    # 계정과목 매핑 딕셔너리가 비어있을 수 있으므로 다시 한번 체크/생성
    mapping = create_mapping_dict(st.session_state.rule_df)
    
    edited_df = st.data_editor(
        df_to_edit[['거래일자', '거래처명', '금액', '매칭상태', 'AI비용항목', '최종_비용항목', '최종_계정과목', '신뢰도']],
        use_container_width=True,
        column_config={
            "최종_비용항목": st.column_config.SelectboxColumn("최종_비용항목 (수정)", options=list(mapping.keys())),
            "최종_계정과목": st.column_config.TextColumn("최종_계정과목 (자동)", disabled=True),
            "신뢰도": st.column_config.ProgressColumn("신뢰도", format="%.2f", min_value=0, max_value=1),
        },
        disabled=['거래일자', '거래처명', '금액', '매칭상태', 'AI비용항목', '신뢰도'],
        key="main_editor"
    )

    # 수정 사항 실시간 반영
    edited_df['최종_계정과목'] = edited_df['최종_비용항목'].map(mapping)
    st.session_state.processed_data.update(edited_df)

    # 4단계: 최종 결과 및 성과
    st.header("4단계: 결과 확인 및 리포트")
    final_df = st.session_state.processed_data[['거래일자', '거래처명', '금액', '매칭상태', '최종_비용항목', '최종_계정과목']]
    st.dataframe(final_df, use_container_width=True)
    
    st.download_button("📥 최종 정산표 다운로드", final_df.to_csv(index=False).encode('utf-8-sig'), "final_settlement.csv", "text/csv")

    # 성과 리포트
    st.divider()
    total = len(final_df)
    mod_count = (st.session_state.processed_data['AI비용항목'] != st.session_state.processed_data['최종_비용항목']).sum()
    mod_rate = (mod_count / total * 100)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("총 처리 건수", f"{total}건")
    m2.metric("수정 비율", f"{mod_rate:.1f}%")
    m3.metric("분석 소요 시간", f"{st.session_state.process_time}초")
