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

# 모든 상태를 관리하기 위한 세션 초기화
for key in ['exp_df', 'rec_df', 'rule_df', 'processed_data', 'analysis_done', 'report_confirmed', 'process_time', 'mapping_dict']:
    if key not in st.session_state:
        st.session_state[key] = None if key != 'analysis_done' and key != 'report_confirmed' else False
        if key == 'mapping_dict': st.session_state[key] = {}
        if key == 'process_time': st.session_state[key] = 0

# --- 유틸리티 함수 ---
def preprocess_df(df):
    """컬럼명 공백 제거 및 인코딩 방어"""
    if df is not None:
        df.columns = [str(c).strip().replace('\ufeff', '') for c in df.columns]
    return df

def safe_read_file(uploaded_file):
    """업로드된 CSV 또는 Excel 읽기"""
    try:
        if uploaded_file.name.endswith('csv'):
            try: return preprocess_df(pd.read_csv(uploaded_file, encoding='utf-8-sig'))
            except: return preprocess_df(pd.read_csv(uploaded_file, encoding='cp949'))
        else:
            return preprocess_df(pd.read_excel(uploaded_file))
    except Exception as e:
        st.error(f"파일을 읽는 중 오류가 발생했습니다: {e}")
        return None

def safe_read_csv_path(path):
    """로컬 경로의 CSV 읽기 (샘플용)"""
    if not os.path.exists(path): return None
    try:
        df = pd.read_csv(path, encoding='utf-8-sig')
    except:
        df = pd.read_csv(path, encoding='cp949')
    return preprocess_df(df)

def create_mapping_dict(rule_df):
    """비용항목-계정과목 매핑 딕셔너리 생성"""
    mapping = {
        "회의비": "81100", "접대비": "81300", "복리후생비": "81100",
        "여비교통비": "81400", "지급수수료": "84500", "소모품비": "82200",
        "도서인쇄비": "82600", "검토 필요": "미분류"
    }
    if rule_df is not None:
        for _, row in rule_df.iterrows():
            item = str(row.get('비용 항목', '')).strip()
            code = str(row.get('계정과목', '')).strip()
            if item and code: mapping[item] = code
    st.session_state.mapping_dict = mapping
    return mapping

# --- 핵심 로직: AI 분석 ---
def run_ai_analysis(exp_df, rec_df, rule_df):
    start_time = time.time()
    mapping = create_mapping_dict(rule_df)
    
    # 1. 증빙 매칭
    merged = pd.merge(exp_df, rec_df, on=['거래일자', '거래처명', '금액'], how='left')
    merged['매칭상태'] = merged.apply(lambda x: "✅ 증빙 완료" if pd.notnull(x.get('파일명')) else "❗ 증빙 누락", axis=1)

    # 2. AI 분류 (Mock 로직)
    def classify(row):
        merchant = str(row.get('거래처명', ''))
        if rule_df is not None:
            for _, r in rule_df.iterrows():
                if str(r.get('거래처 키워드', '')) in merchant:
                    it = r.get('비용 항목', '검토 필요')
                    return it, mapping.get(it, "미분류"), 0.95
        if any(k in merchant for k in ['식당', '카페', '민족', '푸드']): return '복리후생비', mapping.get('복리후생비'), 0.80
        if any(k in merchant for k in ['택시', 'T', '우버', '철도']): return '여비교통비', mapping.get('여비교통비'), 0.85
        if any(k in merchant for k in ['AWS', '슬랙', '클라우드']): return '지급수수료', mapping.get('지급수수료'), 0.90
        return '검토 필요', '미분류', 0.50

    res = merged.apply(classify, axis=1, result_type='expand')
    merged['AI비용항목'], merged['AI계정과목'], merged['신뢰도'] = res[0], res[1], res[2]
    merged['최종_비용항목'], merged['최종_계정과목'] = merged['AI비용항목'], merged['AI계정과목']
    
    return merged, round(time.time() - start_time, 2)

# --- UI 레이아웃 시작 ---

# 서비스 소개
st.title("📑 AI 월말 정산 도우미 (POC)")
st.markdown("""
**안녕하세요, 담당자님! 복잡한 월말 정산 업무를 AI와 함께 해결해 보세요.**  
이 앱은 지출 내역과 증빙 자료를 자동으로 대조하고, 계정과목 초안을 작성해 줍니다. 
모든 분석 결과는 담당자님의 검토를 거쳐 최종 확정됩니다. 😊
""")
st.info("💡 **알림:** 이 프로토타입은 회계 판단을 자동화하지 않습니다. AI 결과는 검토용 초안이며, 최종 확정은 담당자가 수행해야 합니다.")

# 1단계: 데이터 입력 및 확인
st.header("1단계: 데이터 준비 및 업로드")
st.markdown("정산에 필요한 파일을 업로드하거나, 샘플 데이터를 불러와서 흐름을 테스트해 보세요.")

c1, c2, c3 = st.columns(3)
with c1:
    exp_file = st.file_uploader("💳 지출 내역 업로드 (CSV/XLSX)", type=['csv', 'xlsx'])
with c2:
    rec_file = st.file_uploader("📄 증빙 자료 목록 업로드 (CSV/XLSX)", type=['csv', 'xlsx'])
with c3:
    rule_file = st.file_uploader("📋 계정과목 기준표 (선택사항)", type=['csv', 'xlsx'])

st.write("또는")
if st.button("📁 '샘플데이터' 폴더 파일로 로드하기"):
    st.session_state.exp_df = safe_read_csv_path(FILE_PATHS["지출내역"])
    st.session_state.rec_df = safe_read_csv_path(FILE_PATHS["증빙자료"])
    st.session_state.rule_df = safe_read_csv_path(FILE_PATHS["계정과목"])
    st.session_state.analysis_done = False
    st.session_state.report_confirmed = False
    st.success("샘플 데이터를 성공적으로 불러왔습니다.")

# 업로드 파일 처리
if exp_file: st.session_state.exp_df = safe_read_file(exp_file)
if rec_file: st.session_state.rec_df = safe_read_file(rec_file)
if rule_file: st.session_state.rule_df = safe_read_file(rule_file)

# 업로드된 데이터 확인 (미리보기)
if st.session_state.exp_df is not None:
    with st.expander("👀 업로드된 데이터 미리보기 및 필드 확인", expanded=False):
        t1, t2, t3 = st.tabs(["지출 내역", "증빙 자료 목록", "계정과목 기준표"])
        with t1: st.dataframe(st.session_state.exp_df, use_container_width=True)
        with t2: st.dataframe(st.session_state.rec_df, use_container_width=True)
        with t3: 
            if st.session_state.rule_df is not None: st.dataframe(st.session_state.rule_df, use_container_width=True)
            else: st.info("로드된 기준표가 없습니다. 시스템 기본 규칙을 사용합니다.")

    # 2단계: AI 분석 실행
    st.header("2단계: AI 초안 생성")
    st.markdown("데이터가 준비되었다면 AI에게 초안 작성을 요청하세요.")
    if st.button("🤖 AI 초안 생성 시작", type="primary"):
        with st.spinner("AI가 증빙 매칭 및 계정과목 분류를 진행 중입니다..."):
            res, p_time = run_ai_analysis(st.session_state.exp_df, st.session_state.rec_df, st.session_state.rule_df)
            st.session_state.processed_data = res
            st.session_state.process_time = p_time
            st.session_state.analysis_done = True
            st.session_state.report_confirmed = False # 분석 새로 하면 확정 취소
        st.balloons()
        st.success(f"분석 완료! (처리 시간: {p_time}초)")

# 3단계: 사용자 검토 및 증빙 관리
if st.session_state.analysis_done:
    st.divider()
    st.header("3단계: AI 초안 검토 및 증빙 누락 관리")
    
    tab_edit, tab_missing = st.tabs(["🔍 항목 검토 및 수정", "📢 증빙 누락 관리 및 요청"])
    
    with tab_edit:
        st.info("💡 **수정 가이드:** '최종_비용항목'을 더블 클릭해 변경하면 '최종_계정과목'도 실시간으로 바뀝니다.")
        df_to_edit = st.session_state.processed_data.copy()
        mapping = st.session_state.mapping_dict
        
        # 편집 컬럼
        edit_cols = ['거래일자', '거래처명', '금액', '매칭상태', 'AI비용항목', '최종_비용항목', '최종_계정과목', '신뢰도']
        
        edited_df = st.data_editor(
            df_to_edit[edit_cols],
            use_container_width=True,
            column_config={
                "최종_비용항목": st.column_config.SelectboxColumn("최종_비용항목", options=list(mapping.keys())),
                "최종_계정과목": st.column_config.TextColumn("최종_계정과목", disabled=True),
                "신뢰도": st.column_config.ProgressColumn("신뢰도", format="%.2f", min_value=0, max_value=1),
            },
            disabled=['거래일자', '거래처명', '금액', '매칭상태', 'AI비용항목', '신뢰도'],
            key="main_editor"
        )
        
        # 실시간 매핑 반영 및 화면 갱신
        edited_df['최종_계정과목'] = edited_df['최종_비용항목'].map(mapping)
        if not edited_df.equals(st.session_state.processed_data[edit_cols]):
            for col in ['최종_비용항목', '최종_계정과목']:
                st.session_state.processed_data[col] = edited_df[col]
            st.rerun()

    with tab_missing:
        st.subheader("증빙 요청 자동화")
        missing_df = st.session_state.processed_data[st.session_state.processed_data['매칭상태'].str.contains("누락")]
        if len(missing_df) > 0:
            st.warning(f"현재 {len(missing_df)}건의 증빙이 누락되었습니다. 담당자별 요청 문구를 활용하세요.")
            for user in missing_df['사용자'].unique():
                user_items = missing_df[missing_df['사용자'] == user]
                total_amt = user_items['금액'].sum()
                with st.expander(f"👤 {user}님께 보내는 요청 메시지 ({len(user_items)}건)"):
                    msg = f"안녕하세요 {user}님, 이번 달 정산 증빙 누락건({len(user_items)}건, 총 {total_amt:,}원) 확인 및 제출 부탁드립니다."
                    st.code(msg, language="text")
        else:
            st.success("🎉 모든 증빙이 완벽하게 갖춰졌습니다!")

    # 결과 확정 버튼
    st.markdown("---")
    st.subheader("🏁 검토 마무리")
    if st.button("✅ 모든 검토 완료 및 최종 리포트 생성", type="primary"):
        st.session_state.report_confirmed = True
        st.rerun()

# 4단계: 최종 리포트 및 성과 지표
if st.session_state.report_confirmed:
    st.divider()
    st.header("4단계: 최종 정산표 및 성과 대시보드")
    
    # 최종 결과물 미리보기
    final_df = st.session_state.processed_data[['거래일자', '거래처명', '금액', '사용자', '매칭상태', '최종_비용항목', '최종_계정과목']].copy()
    final_df.columns = ['거래일자', '거래처명', '금액', '담당자', '증빙여부', '비용항목(확정)', '계정과목(확정)']
    
    st.dataframe(final_df, use_container_width=True)
    
    # 리포트 다운로드
    st.download_button(
        "📥 최종 정산 리포트(CSV) 다운로드",
        final_df.to_csv(index=False).encode('utf-8-sig'),
        f"정산결과_{datetime.now().strftime('%Y%m%d')}.csv",
        "text/csv"
    )

    # 성과 지표 분석
    st.subheader("📊 POC 성과 측정 (KPI)")
    total = len(final_df)
    mod_count = (st.session_state.processed_data['AI비용항목'] != st.session_state.processed_data['최종_비용항목']).sum()
    mod_rate = (mod_count / total * 100)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("전체 정산 건수", f"{total}건")
    col2.metric("AI 초안 수정 비율", f"{mod_rate:.1f}%", help="30% 이하라면 AI 성능 우수")
    col3.metric("AI 분석 시간", f"{st.session_state.process_time}초", help="기존 수동 작업 대비 90% 이상 절감")

    # 최종 만족도 및 OKR 판정
    st.markdown("---")
    sat = st.slider("담당자님, 본 AI 초안 기능이 업무 시간을 줄이는 데 기여했나요? (5점 만점)", 1, 5, 4)
    
    if mod_rate <= 30 and sat >= 4:
        st.success("🎯 **POC 목표 달성:** 수정률 및 업무 만족도 지표를 충족했습니다. 정식 도입 검토를 권장합니다.")
    else:
        st.warning("⚖️ **추가 개선 필요:** 일부 성능 지표가 목표에 도달하지 못했습니다. 분류 로직 보완이 필요합니다.")
