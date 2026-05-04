import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime

# --- 페이지 설정 ---
st.set_page_config(page_title="월말 정산표 AI POC", layout="wide")

# --- 경로 설정 ---
SAMPLE_DIR = "샘플데이터"
FILE_PATHS = {
    "지출내역": os.path.join(SAMPLE_DIR, "지출내역.csv"),
    "증빙자료": os.path.join(SAMPLE_DIR, "증빙자료.csv"),
    "계정과목": os.path.join(SAMPLE_DIR, "계정과목 기준표.csv")
}

# --- 세션 상태 초기화 ---
if 'processed_data' not in st.session_state: st.session_state.processed_data = None
if 'analysis_done' not in st.session_state: st.session_state.analysis_done = False
if 'mapping_dict' not in st.session_state: st.session_state.mapping_dict = {}

# --- 데이터 전처리 및 읽기 ---
def preprocess_df(df):
    if df is not None:
        df.columns = [str(c).strip().replace('\ufeff', '') for c in df.columns]
    return df

def safe_read_csv(path):
    try:
        df = pd.read_csv(path, encoding='utf-8-sig')
    except:
        df = pd.read_csv(path, encoding='cp949')
    return preprocess_df(df)

# --- 자동 매핑 사전 생성 함수 ---
def create_mapping_dict(rule_df):
    # 기본 매핑 (기준표가 없을 때 사용)
    base_mapping = {
        "회의비": "81100",
        "접대비": "81300",
        "복리후생비": "81100",
        "여비교통비": "81400",
        "지급수수료": "84500",
        "소모품비": "82200",
        "도서인쇄비": "82600",
        "검토 필요": "미분류"
    }
    
    # 기준표가 있다면 업데이트
    if rule_df is not None:
        for _, row in rule_df.iterrows():
            item = str(row.get('비용 항목')).strip()
            code = str(row.get('계정과목')).strip()
            if item and code:
                base_mapping[item] = code
                
    st.session_state.mapping_dict = base_mapping
    return base_mapping

# --- AI 분석 로직 ---
def run_ai_analysis(exp_df, rec_df, rule_df):
    start_time = time.time()
    
    # 1. 매핑 사전 생성
    mapping = create_mapping_dict(rule_df)
    
    # 2. 증빙 매칭
    merged = pd.merge(exp_df, rec_df, on=['거래일자', '거래처명', '금액'], how='left')
    merged['매칭상태'] = merged.apply(lambda x: "증빙 완료" if pd.notnull(x.get('파일명')) else "증빙 누락", axis=1)

    # 3. AI 분류 (Mock)
    def classify(row):
        merchant = str(row.get('거래처명', ''))
        if rule_df is not None:
            for _, r in rule_df.iterrows():
                if str(r.get('거래처 키워드', '')) in merchant:
                    item = r.get('비용 항목', '검토 필요')
                    return item, mapping.get(item, "00000"), 0.95
        
        if any(k in merchant for k in ['식당', '민족', '바게뜨']): return '복리후생비', mapping.get('복리후생비'), 0.80
        if any(k in merchant for k in ['택시', 'T', '우버']): return '여비교통비', mapping.get('여비교통비'), 0.85
        return '검토 필요', '미분류', 0.50

    results = merged.apply(classify, axis=1, result_type='expand')
    merged['AI비용항목'] = results[0]
    merged['AI계정과목'] = results[1]
    merged['신뢰도'] = results[2]
    
    # 최종 수정 컬럼 초기화
    merged['최종_비용항목'] = merged['AI비용항목']
    merged['최종_계정과목'] = merged['AI계정과목']
    
    return merged, round(time.time() - start_time, 2)

# --- 메인 UI ---
st.title("📂 월말 정산표 초안 작성 POC")

# 1. 데이터 입력
st.header("1. 데이터 입력")
col1, col2, col3 = st.columns(3)
with col1: exp_file = st.file_uploader("지출 내역", type=['csv', 'xlsx'])
with col2: rec_file = st.file_uploader("증빙 자료", type=['csv', 'xlsx'])
with col3: rule_file = st.file_uploader("계정과목 기준표", type=['csv', 'xlsx'])

if st.button("📁 샘플 데이터 로드"):
    st.session_state.exp_df = safe_read_csv(FILE_PATHS["지출내역"])
    st.session_state.rec_df = safe_read_csv(FILE_PATHS["증빙자료"])
    st.session_state.rule_df = safe_read_csv(FILE_PATHS["계정과목"])
    st.success("데이터 로드 완료")

# 파일 업로드 시 세션 저장
if exp_file: st.session_state.exp_df = preprocess_df(pd.read_csv(exp_file) if exp_file.name.endswith('csv') else pd.read_excel(exp_file))
if rec_file: st.session_state.rec_df = preprocess_df(pd.read_csv(rec_file) if rec_file.name.endswith('csv') else pd.read_excel(rec_file))
if rule_file: st.session_state.rule_df = preprocess_df(pd.read_csv(rule_file) if rule_file.name.endswith('csv') else pd.read_excel(rule_file))

# 2. 분석 실행
if 'exp_df' in st.session_state and st.session_state.exp_df is not None:
    if st.button("🤖 AI 초안 생성 시작", type="primary"):
        res, p_time = run_ai_analysis(st.session_state.exp_df, st.session_state.rec_df, st.session_state.rule_df)
        st.session_state.processed_data = res
        st.session_state.process_time = p_time
        st.session_state.analysis_done = True

# 3. 초안 검토 및 수정
if st.session_state.analysis_done:
    st.divider()
    st.header("2. AI 초안 검토 및 수정")
    st.info("💡 '최종_비용항목'을 변경하면 '최종_계정과목'이 자동으로 업데이트됩니다.")

    # 편집 데이터 준비
    df_to_edit = st.session_state.processed_data.copy()
    
    # st.data_editor 실행
    edited_df = st.data_editor(
        df_to_edit[['거래일자', '거래처명', '금액', '매칭상태', 'AI비용항목', '최종_비용항목', '최종_계정과목', '신뢰도']],
        use_container_width=True,
        column_config={
            "최종_비용항목": st.column_config.SelectboxColumn(
                "최종_비용항목", 
                options=list(st.session_state.mapping_dict.keys())
            ),
            "최종_계정과목": st.column_config.TextColumn("최종_계정과목 (자동)", disabled=True),
            "신뢰도": st.column_config.ProgressColumn("AI신뢰도", format="%.2f", min_value=0, max_value=1),
        },
        disabled=['거래일자', '거래처명', '금액', '매칭상태', 'AI비용항목', '신뢰도'],
        key="editor"
    )

    # [핵심] 비용 항목 변경에 따른 계정과목 자동 업데이트 로직
    # 편집된 데이터에서 '최종_비용항목'을 기준으로 '최종_계정과목'을 다시 매핑
    edited_df['최종_계정과목'] = edited_df['최종_비용항목'].map(st.session_state.mapping_dict)
    
    # 세션 상태에 반영
    st.session_state.processed_data.update(edited_df)

    # 4. 최종 결과 및 다운로드
    st.header("3. 최종 정산표 미리보기")
    final_df = st.session_state.processed_data[['거래일자', '거래처명', '금액', '매칭상태', '최종_비용항목', '최종_계정과목']]
    st.dataframe(final_df, use_container_width=True)

    # 5. 성과 분석 지표
    st.divider()
    st.header("4. POC 성과 분석")
    total = len(final_df)
    mod_count = (st.session_state.processed_data['AI비용항목'] != st.session_state.processed_data['최종_비용항목']).sum()
    mod_rate = (mod_count / total * 100)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("전체 건수", f"{total}건")
    c2.metric("수정 비율", f"{mod_rate:.1f}%", help="AI 초안에서 사용자가 수정한 비율")
    c3.metric("분석 소요 시간", f"{st.session_state.process_time}초")

    st.download_button("📥 최종 정산표 다운로드", final_df.to_csv(index=False).encode('utf-8-sig'), "final_settlement.csv", "text/csv")
