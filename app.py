import streamlit as st
import pandas as pd
import os
import time
import json
from datetime import datetime

# --- 1. 페이지 설정 및 스타일 ---
st.set_page_config(page_title="AI 월말 정산 도우미 POC", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
    .stAlert { margin-top: 10px; }
    div.stButton > button:first-child { width: 100%; }
    </style>
""", unsafe_allow_html=True)

# --- 2. 세션 상태 초기화 (데이터 및 시간 측정용) ---
initial_states = {
    'exp_df': None, 'rec_df': None, 'rule_df': None, 
    'processed_data': None, 'analysis_done': False, 
    'report_confirmed': False, 'mapping_dict': {},
    't_start': None, 't_analysis_end': None, 't_final_confirm': None,
    'process_time': 0
}
for key, value in initial_states.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- 3. 유틸리티 함수 ---
def preprocess_df(df):
    """컬럼명 공백 제거 및 인코딩 클리닝"""
    if df is not None:
        df.columns = [str(c).strip().replace('\ufeff', '') for c in df.columns]
    return df

def safe_read_file(uploaded_file):
    """업로드된 CSV/Excel 읽기"""
    try:
        if uploaded_file.name.endswith('csv'):
            try: return preprocess_df(pd.read_csv(uploaded_file, encoding='utf-8-sig'))
            except: return preprocess_df(pd.read_csv(uploaded_file, encoding='cp949'))
        else: return preprocess_df(pd.read_excel(uploaded_file))
    except Exception as e:
        st.error(f"파일 읽기 오류: {e}"); return None

def create_mapping_dict(rule_df):
    """비용항목-계정과목 코드 매핑 사전 생성"""
    mapping = {
        "회의비": "81100", "접대비": "81300", "복리후생비": "81100",
        "여비교통비": "81400", "지급수수료": "84500", "소모품비": "82200",
        "도서인쇄비": "82600", "검토 필요": "미분류"
    }
    if rule_df is not None:
        for _, row in rule_df.iterrows():
            item, code = str(row.get('비용 항목', '')).strip(), str(row.get('계정과목', '')).strip()
            if item and code: mapping[item] = code
    st.session_state.mapping_dict = mapping
    return mapping

def run_ai_analysis(exp_df, rec_df, rule_df):
    """AI 분석 로직: 증빙 매칭 + 계정과목 분류"""
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
                    it = r.get('비용 항목', '검토 필요'); return it, mapping.get(it, "미분류"), 0.95
        if any(k in merchant for k in ['식당', '카페', '민족']): return '복리후생비', mapping.get('복리후생비'), 0.80
        if any(k in merchant for k in ['택시', 'T', '우버']): return '여비교통비', mapping.get('여비교통비'), 0.85
        return '검토 필요', '미분류', 0.50

    res = merged.apply(classify, axis=1, result_type='expand')
    merged['AI비용항목'], merged['AI계정과목'], merged['신뢰도'] = res[0], res[1], res[2]
    merged['최종_비용항목'], merged['최종_계정과목'] = merged['AI비용항목'], merged['AI계정과목']
    return merged

# --- 4. 메인 UI 화면 구성 ---

st.title("📑 AI 월말 정산 도우미 POC (전체 통합본)")
st.markdown("""
**회계 담당자님, 환영합니다!** 이 도구는 AI를 활용해 증빙 대조와 계정과목 분류를 자동화합니다. 
분석 시간 측정과 AI 정확도 데이터를 통해 실무 도입 효과를 검증합니다.
""")
st.info("💡 **안내:** 이 프로토타입은 회계 판단을 자동화하지 않습니다. 최종 확정은 반드시 담당자가 수행해야 합니다.")

# --- Step 1: 데이터 준비 ---
st.header("1단계: 데이터 업로드 및 확인")
st.markdown("정산에 필요한 파일을 업로드하거나 샘플 데이터를 사용해 보세요. 업로드 시점부터 **업무 소요 시간이 측정**됩니다.")

c1, c2, c3 = st.columns(3)
with c1: exp_f = st.file_uploader("💳 지출 내역 (카드/계좌)", type=['csv', 'xlsx'])
with c2: rec_f = st.file_uploader("📄 증빙 자료 목록", type=['csv', 'xlsx'])
with c3: rule_f = st.file_uploader("📋 계정과목 기준표 (선택)", type=['csv', 'xlsx'])

if st.button("📁 샘플 데이터로 즉시 시작"):
    # 샘플 데이터 생성 로직 (파일이 없을 경우를 대비한 가상 데이터)
    st.session_state.exp_df = pd.DataFrame({
        '거래일자': ['2024-04-01', '2024-04-02', '2024-04-03'],
        '거래처명': ['스타벅스', '김밥천국', '카카오T'],
        '금액': [5400, 8500, 12000], '사용자': ['김철수', '이영희', '박지성'], '사용부서': ['영업', '인사', '개발']
    })
    st.session_state.rec_df = pd.DataFrame({
        '파일명': ['rec_01.jpg', 'rec_02.jpg'], '거래일자': ['2024-04-01', '2024-04-02'], 
        '거래처명': ['스타벅스', '김밥천국'], '금액': [5400, 8500]
    })
    st.session_state.t_start = time.time()
    st.success("샘플 로드 완료! 분석을 시작할 수 있습니다.")

# 파일 업로드 시 세션 저장 및 시간 기록
if exp_f and rec_f:
    st.session_state.exp_df = safe_read_file(exp_f)
    st.session_state.rec_df = safe_read_file(rec_f)
    if rule_f: st.session_state.rule_df = safe_read_file(rule_f)
    if st.session_state.t_start is None: st.session_state.t_start = time.time()

# 데이터 미리보기
if st.session_state.exp_df is not None:
    with st.expander("👀 로드된 데이터 미리보기 (탭별 확인)", expanded=False):
        t1, t2, t3 = st.tabs(["지출 내역", "증빙 자료", "기준표"])
        with t1: st.dataframe(st.session_state.exp_df, use_container_width=True)
        with t2: st.dataframe(st.session_state.rec_df, use_container_width=True)
        with t3: 
            if st.session_state.rule_df is not None: st.dataframe(st.session_state.rule_df, use_container_width=True)
            else: st.info("기본 규칙이 적용됩니다.")

    # --- Step 2: AI 분석 ---
    st.header("2단계: AI 분석 실행")
    if not st.session_state.analysis_done:
        if st.button("🤖 AI 초안 생성 시작", type="primary"):
            with st.spinner("AI가 증빙을 매칭하고 계정과목을 분류하고 있습니다..."):
                st.session_state.processed_data = run_ai_analysis(st.session_state.exp_df, st.session_state.rec_df, st.session_state.rule_df)
                st.session_state.t_analysis_end = time.time()
                st.session_state.process_time = round(st.session_state.t_analysis_end - st.session_state.t_start, 2)
                st.session_state.analysis_done = True
                st.rerun()

# --- Step 3: 검토 및 관리 ---
if st.session_state.analysis_done:
    st.divider()
    st.header("3단계: 상세 검토 및 증빙 누락 관리")
    
    tab_edit, tab_missing = st.tabs(["🔍 초안 검토 및 수정", "📢 증빙 누락 관리"])
    
    with tab_edit:
        st.info("💡 **실시간 매핑:** '최종_비용항목'을 수정하면 '최종_계정과목'도 즉시 업데이트됩니다.")
        df_edit = st.session_state.processed_data.copy()
        mapping = st.session_state.mapping_dict
        edit_cols = ['거래일자', '거래처명', '금액', '매칭상태', 'AI비용항목', '최종_비용항목', '최종_계정과목', '신뢰도']
        
        edited = st.data_editor(
            df_edit[edit_cols], use_container_width=True,
            column_config={
                "최종_비용항목": st.column_config.SelectboxColumn("최종_비용항목", options=list(mapping.keys())),
                "최종_계정과목": st.column_config.TextColumn("최종_계정과목", disabled=True),
                "신뢰도": st.column_config.ProgressColumn("AI 신뢰도", format="%.2f", min_value=0, max_value=1),
            },
            disabled=['거래일자', '거래처명', '금액', '매칭상태', 'AI비용항목', '신뢰도'],
            key="main_editor"
        )
        
        # 실시간 세션 반영 로직
        edited['최종_계정과목'] = edited['최종_비용항목'].map(mapping)
        if not edited.equals(st.session_state.processed_data[edit_cols]):
            for c in ['최종_비용항목', '최종_계정과목']: st.session_state.processed_data[c] = edited[c]
            st.rerun()

    with tab_missing:
        st.subheader("증빙 미제출 담당자 요청")
        missing = st.session_state.processed_data[st.session_state.processed_data['매칭상태'].str.contains("누락")]
        if len(missing) > 0:
            for user in missing['사용자'].unique():
                user_missing = missing[missing['사용자'] == user]
                with st.expander(f"👤 {user}님께 보내는 메시지 ({len(user_missing)}건)"):
                    msg = f"안녕하세요 {user}님, 이번 달 지출 증빙({len(user_missing)}건) 누락이 확인되었습니다. 확인 부탁드립니다."
                    st.code(msg, language="text")
        else: st.success("모든 증빙이 완료되었습니다.")

    st.markdown("---")
    if st.button("✅ 검토 완료 및 최종 결과 확정", type="primary"):
        st.session_state.t_final_confirm = time.time()
        st.session_state.report_confirmed = True
        st.rerun()

# --- Step 4: 성과 분석 및 리포트 ---
if st.session_state.report_confirmed:
    st.divider()
    st.header("4단계: POC 운영 성과 및 최종 리포트")
    
    # 1. 지표 계산
    df = st.session_state.processed_data
    total_duration_min = round((st.session_state.t_final_confirm - st.session_state.t_start) / 60, 2)
    mod_count = (df['AI비용항목'] != df['최종_비용항목']).sum()
    mod_rate = (mod_count / len(df)) * 100
    missing_items = df[df['매칭상태'].str.contains("누락")]

    # 2. 대시보드 표시
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("총 처리 건수", f"{len(df)}건")
    m2.metric("총 소요 시간", f"{total_duration_min}분")
    m3.metric("AI 수정 비율", f"{mod_rate:.1f}%")
    m4.metric("증빙 누락", f"{len(missing_items)}건")

    # 3. 운영 데이터 추가 수집 (사용자 입력)
    with st.container():
        st.write("##### 📊 실제 운영 적중률 측정")
        c_a, c_b = st.columns(2)
        with c_a: actual_missing = st.number_input("실제 누락 확정 건수", 0, len(missing_items), value=len(missing_items))
        with c_b: sat_score = st.slider("사용자 체감 효율 점수 (1~5점)", 1, 5, 4)
    
    hit_rate = (actual_missing / len(missing_items) * 100) if len(missing_items) > 0 else 100

    # 4. OKR 판정
    st.subheader("🎯 POC 목표 달성 리포트")
    is_success = mod_rate <= 30 and sat_score >= 4 and hit_rate >= 70
    if is_success: st.success("✅ **성공: 확산 검토** (모든 KPI 달성)")
    else: st.warning("⚖️ **미달: 보완 및 재실험** (일부 지표 목표 미달)")

    # 5. 운영 로그 (JSON)
    with st.expander("📜 운영 분석 데이터 로그 (복사 가능)"):
        log = {
            "session_date": datetime.now().strftime("%Y-%m-%d"),
            "total_items": len(df),
            "total_min": total_duration_min,
            "correction_rate": mod_rate,
            "missing_hit_rate": hit_rate,
            "satisfaction": sat_score
        }
        st.json(log)

    # 6. 다운로드
    final_df = df[['거래일자', '거래처명', '금액', '매칭상태', '최종_비용항목', '최종_계정과목']]
    st.download_button("📥 최종 정산표 다운로드", final_df.to_csv(index=False).encode('utf-8-sig'), "final_report.csv")
