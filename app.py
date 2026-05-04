import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime

# --- 페이지 설정 ---
st.set_page_config(page_title="AI 월말 정산 도우미 POC", layout="wide")

# --- 경로 및 세션 상태 초기화 ---
SAMPLE_DIR = "샘플데이터"
FILE_PATHS = {
    "지출내역": os.path.join(SAMPLE_DIR, "지출내역.csv"),
    "증빙자료": os.path.join(SAMPLE_DIR, "증빙자료.csv"),
    "계정과목": os.path.join(SAMPLE_DIR, "계정과목 기준표.csv")
}

if 'processed_data' not in st.session_state: st.session_state.processed_data = None
if 'analysis_done' not in st.session_state: st.session_state.analysis_done = False
if 'mapping_dict' not in st.session_state: st.session_state.mapping_dict = {}

# --- 데이터 처리 함수 ---
def preprocess_df(df):
    if df is not None:
        df.columns = [str(c).strip().replace('\ufeff', '') for c in df.columns]
    return df

def safe_read_csv(path):
    if not os.path.exists(path): return None
    try:
        df = pd.read_csv(path, encoding='utf-8-sig')
    except:
        df = pd.read_csv(path, encoding='cp949')
    return preprocess_df(df)

def create_mapping_dict(rule_df):
    # 기본 매핑 규칙 정의
    mapping = {
        "회의비": "81100", "접대비": "81300", "복리후생비": "81100",
        "여비교통비": "81400", "지급수수료": "84500", "소모품비": "82200",
        "도서인쇄비": "82600", "검토 필요": "미분류"
    }
    if rule_df is not None:
        for _, row in rule_df.iterrows():
            mapping[str(row.get('비용 항목', '')).strip()] = str(row.get('계정과목', '')).strip()
    st.session_state.mapping_dict = mapping
    return mapping

def run_ai_analysis(exp_df, rec_df, rule_df):
    start_time = time.time()
    mapping = create_mapping_dict(rule_df)
    
    # 1. 증빙 매칭
    merged = pd.merge(exp_df, rec_df, on=['거래일자', '거래처명', '금액'], how='left')
    merged['매칭상태'] = merged.apply(lambda x: "✅ 증빙 완료" if pd.notnull(x.get('파일명')) else "❗ 증빙 누락", axis=1)

    # 2. AI 분류 (Mock)
    def classify(row):
        merchant = str(row.get('거래처명', ''))
        if rule_df is not None:
            for _, r in rule_df.iterrows():
                if str(r.get('거래처 키워드', '')) in merchant:
                    item = r.get('비용 항목', '검토 필요')
                    return item, mapping.get(item, "미분류"), 0.95
        if any(k in merchant for k in ['식당', '카페', '민족']): return '복리후생비', mapping.get('복리후생비'), 0.80
        if any(k in merchant for k in ['택시', 'T', '우버']): return '여비교통비', mapping.get('여비교통비'), 0.85
        return '검토 필요', '미분류', 0.50

    res = merged.apply(classify, axis=1, result_type='expand')
    merged['AI비용항목'], merged['AI계정과목'], merged['신뢰도'] = res[0], res[1], res[2]
    merged['최종_비용항목'], merged['최종_계정과목'] = merged['AI비용항목'], merged['AI계정과목']
    
    return merged, round(time.time() - start_time, 2)

# --- UI 레이아웃 ---
st.title("📑 AI 월말 정산 도우미 (POC)")
st.markdown("정산 업무 시간을 줄여주는 AI 초안 생성 및 관리 도구입니다.")

# 1. 데이터 입력
st.header("1단계: 데이터 준비")
if st.button("📁 샘플 데이터 로드"):
    st.session_state.exp_df = safe_read_csv(FILE_PATHS["지출내역"])
    st.session_state.rec_df = safe_read_csv(FILE_PATHS["증빙자료"])
    st.session_state.rule_df = safe_read_csv(FILE_PATHS["계정과목"])
    st.success("데이터 로드 완료")

# 2. AI 분석 실행
if st.session_state.get('exp_df') is not None:
    if st.button("🤖 AI 초안 생성 시작", type="primary"):
        res, p_time = run_ai_analysis(st.session_state.exp_df, st.session_state.rec_df, st.session_state.rule_df)
        st.session_state.processed_data = res
        st.session_state.process_time = p_time
        st.session_state.analysis_done = True

# 3. 분석 결과 및 검토
if st.session_state.analysis_done:
    st.divider()
    tab_edit, tab_missing = st.tabs(["🔍 초안 검토 및 수정", "📢 증빙 누락 관리"])

    with tab_edit:
        st.subheader("계정과목 및 내역 검토")
        st.info("💡 **팁:** '최종_비용항목'을 변경하면 옆의 **'최종_계정과목' 셀도 실시간으로 업데이트**됩니다.")

        # 현재 데이터 가져오기
        df_to_edit = st.session_state.processed_data.copy()
        mapping = st.session_state.mapping_dict

        # 컬럼 순서 조정 및 에디터 실행
        edit_cols = ['거래일자', '거래처명', '금액', '매칭상태', 'AI비용항목', '최종_비용항목', '최종_계정과목', '신뢰도']
        
        edited_df = st.data_editor(
            df_to_edit[edit_cols],
            use_container_width=True,
            column_config={
                "최종_비용항목": st.column_config.SelectboxColumn("최종_비용항목 (수정)", options=list(mapping.keys())),
                "최종_계정과목": st.column_config.TextColumn("최종_계정과목 (자동)", disabled=True),
                "신뢰도": st.column_config.ProgressColumn("신뢰도", format="%.2f", min_value=0, max_value=1),
            },
            disabled=['거래일자', '거래처명', '금액', '매칭상태', 'AI비용항목', '신뢰도'],
            key="main_editor"
        )

        # [핵심] 수정된 비용항목에 따라 계정과목 실시간 매핑 업데이트
        edited_df['최종_계정과목'] = edited_df['최종_비용항목'].map(mapping)

        # [중요] 세션 데이터와 편집 데이터 비교 후 다르면 업데이트 및 Rerun
        # 이렇게 하면 사용자가 수정한 즉시 3단계 표의 '최종_계정과목' 컬럼이 업데이트된 값으로 바뀝니다.
        if not edited_df.equals(st.session_state.processed_data[edit_cols]):
            # 수정한 내용을 원본 데이터프레임의 해당 컬럼에만 업데이트
            for col in ['최종_비용항목', '최종_계정과목']:
                st.session_state.processed_data[col] = edited_df[col]
            st.rerun()  # 화면을 새로고침하여 3단계 표에 반영

    with tab_missing:
        st.subheader("📢 증빙 요청 메시지 생성")
        missing_df = st.session_state.processed_data[st.session_state.processed_data['매칭상태'].str.contains("누락")]
        if len(missing_df) > 0:
            st.dataframe(missing_df[['거래일자', '거래처명', '금액', '사용자']], use_container_width=True)
            for user in missing_df['사용자'].unique():
                with st.expander(f"👤 {user}님께 요청하기"):
                    st.code(f"안녕하세요 {user}님, 증빙 누락건 확인 부탁드립니다...", language="text")
        else:
            st.success("누락된 증빙이 없습니다.")

    # 4. 최종 결과 리포트
    st.divider()
    st.header("4단계: 결과 확인 및 리포트")
    final_view = st.session_state.processed_data[['거래일자', '거래처명', '금액', '매칭상태', '최종_비용항목', '최종_계정과목']].copy()
    final_view.columns = ['거래일자', '거래처명', '금액', '증빙여부', '비용항목(확정)', '계정과목(확정)']
    st.dataframe(final_view, use_container_width=True)
    
    # 성과 지표
    total = len(final_view)
    mod_count = (st.session_state.processed_data['AI비용항목'] != st.session_state.processed_data['최종_비용항목']).sum()
    mod_rate = (mod_count / total * 100)
    
    c1, c2, c3 = st.columns(3)
    c1.metric("총 처리 건수", f"{total}건")
    m2_label = "AI 초안 수정 비율"
    c2.metric(m2_label, f"{mod_rate:.1f}%", help="30% 이하면 양호")
    c3.metric("AI 분석 소요 시간", f"{st.session_state.process_time}초")
