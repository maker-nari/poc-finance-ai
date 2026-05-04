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

# --- 데이터 전처리 함수 (KeyError 방지 핵심) ---
def preprocess_df(df):
    if df is not None:
        # 1. 컬럼명의 앞뒤 공백 제거
        df.columns = [str(c).strip() for c in df.columns]
        # 2. 첫 번째 컬럼의 BOM 문자 제거 (인코딩 문제 해결)
        df.columns = [c.replace('\ufeff', '') for c in df.columns]
    return df

# --- CSV 읽기 함수 (강력한 인코딩 처리) ---
def safe_read_csv(path):
    try:
        # utf-8-sig는 파일 맨 앞의 BOM(결깨짐 원인)을 자동으로 제거함
        df = pd.read_csv(path, encoding='utf-8-sig')
    except:
        try:
            df = pd.read_csv(path, encoding='cp949')
        except:
            df = pd.read_csv(path, encoding='euc-kr')
    return preprocess_df(df)

# --- AI 분석 로직 ---
def run_ai_analysis(exp_df, rec_df, rule_df):
    start_time = time.time()
    
    # 지출내역과 증빙자료 병합
    # KeyError 방지를 위해 컬럼명이 확실히 존재하는지 확인 후 병합
    try:
        merged = pd.merge(exp_df, rec_df, on=['거래일자', '거래처명', '금액'], how='left')
    except KeyError as e:
        st.error(f"데이터 병합 중 오류 발생: {e} 컬럼을 찾을 수 없습니다. CSV 파일의 헤더를 확인해주세요.")
        return None, 0
        
    merged['매칭상태'] = merged.apply(lambda x: "증빙 완료" if pd.notnull(x.get('파일명')) else "증빙 누락", axis=1)

    # AI 분류 (Mock)
    def classify(row):
        merchant = str(row.get('거래처명', ''))
        if rule_df is not None:
            # 기준표 컬럼명도 strip 처리되었으므로 안심하고 사용
            for _, r in rule_df.iterrows():
                if str(r.get('거래처 키워드', '')) in merchant:
                    return r.get('비용 항목', '미분류'), r.get('계정과목', '00000'), 0.95
        
        if any(k in merchant for k in ['식당', '민족', '바게뜨']): return '복리후생비', '81100', 0.80
        if any(k in merchant for k in ['택시', 'T', '우버']): return '여비교통비', '81400', 0.85
        return '검토 필요', '미분류', 0.50

    results = merged.apply(classify, axis=1, result_type='expand')
    merged['AI비용항목'] = results[0]
    merged['AI계정과목'] = results[1]
    merged['신뢰도'] = results[2]
    
    merged['최종_비용항목'] = merged['AI비용항목']
    merged['최종_계정과목'] = merged['AI계정과목']
    
    return merged, round(time.time() - start_time, 2)

# --- 메인 UI ---
st.title("📂 월말 정산표 초안 작성 POC")

# 1. 데이터 입력
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
        st.error("샘플 폴더를 찾을 수 없습니다.")

# 파일 업로드 시 처리
if exp_file: st.session_state.exp_df = preprocess_df(pd.read_csv(exp_file) if exp_file.name.endswith('csv') else pd.read_excel(exp_file))
if rec_file: st.session_state.rec_df = preprocess_df(pd.read_csv(rec_file) if rec_file.name.endswith('csv') else pd.read_excel(rec_file))
if rule_file: st.session_state.rule_df = preprocess_df(pd.read_csv(rule_file) if rule_file.name.endswith('csv') else pd.read_excel(rule_file))

# 2. AI 분석 실행
if st.session_state.exp_df is not None and st.session_state.rec_df is not None:
    if st.button("🤖 AI 초안 생성 시작", type="primary"):
        res, p_time = run_ai_analysis(st.session_state.exp_df, st.session_state.rec_df, st.session_state.rule_df)
        if res is not None:
            st.session_state.processed_data = res
            st.session_state.process_time = p_time
            st.session_state.analysis_done = True

# 3. AI 초안 검토 및 수정
if st.session_state.analysis_done and st.session_state.processed_data is not None:
    st.divider()
    st.header("2. AI 초안 검토 및 수정")
    
    # 현재 데이터프레임의 컬럼명을 안전하게 가져오기
    cols = st.session_state.processed_data.columns.tolist()
    # 화면에 보여줄 컬럼만 필터링 (존재하는 컬럼만)
    target_cols = [c for c in ['거래일자', '거래처명', '금액', '매칭상태', 'AI비용항목', '최종_비용항목', 'AI계정과목', '최종_계정과목', '신뢰도'] if c in cols]

    edited_df = st.data_editor(
        st.session_state.processed_data[target_cols],
        use_container_width=True,
        column_config={
            "신뢰도": st.column_config.ProgressColumn("AI신뢰도", format="%.2f", min_value=0, max_value=1),
            "최종_비용항목": st.column_config.SelectboxColumn("최종_비용항목", options=["회의비", "접대비", "복리후생비", "여비교통비", "지급수수료", "소모품비", "도서인쇄비"])
        },
        disabled=[c for c in target_cols if "최종" not in c],
        key="editor"
    )

    if st.button("✅ 수정 사항 저장 및 확정"):
        st.session_state.processed_data.update(edited_df)
        st.success("데이터가 업데이트되었습니다.")

    # 4. 최종 미리보기
    st.header("3. 최종 정산표 미리보기")
    final_cols = [c for c in ['거래일자', '거래처명', '금액', '매칭상태', '최종_비용항목', '최종_계정과목'] if c in st.session_state.processed_data.columns]
    st.dataframe(st.session_state.processed_data[final_cols], use_container_width=True)

    # 5. 성과 지표
    st.divider()
    st.header("4. POC 성과 분석")
    total = len(st.session_state.processed_data)
    mod_count = (st.session_state.processed_data['AI비용항목'] != st.session_state.processed_data['최종_비용항목']).sum()
    mod_rate = (mod_count / total * 100)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("전체 건수", f"{total}건")
    m2.metric("수정 비율", f"{mod_rate:.1f}%")
    m3.metric("처리 시간", f"{st.session_state.process_time}초")

    st.download_button("📥 CSV 다운로드", st.session_state.processed_data[final_cols].to_csv(index=False).encode('utf-8-sig'), "settlement.csv", "text/csv")
