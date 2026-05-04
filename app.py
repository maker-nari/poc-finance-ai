import streamlit as st
import pandas as pd
import os
import time
from datetime import datetime

# --- 페이지 설정 ---
st.set_page_config(page_title="AI 월말 정산 도우미 POC", layout="wide")

# --- 경로 설정 ---
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
if 'mapping_dict' not in st.session_state: st.session_state.mapping_dict = {}

# --- 공통 함수 ---
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

def create_mapping_dict(rule_df):
    base_mapping = {
        "회의비": "81100", "접대비": "81300", "복리후생비": "81100",
        "여비교통비": "81400", "지급수수료": "84500", "소모품비": "82200",
        "도서인쇄비": "82600", "검토 필요": "미분류"
    }
    if rule_df is not None:
        for _, row in rule_df.iterrows():
            item = str(row.get('비용 항목', '')).strip()
            code = str(row.get('계정과목', '')).strip()
            if item and code: base_mapping[item] = code
    st.session_state.mapping_dict = base_mapping
    return base_mapping

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

# --- UI 레이아웃 시작 ---

# 제목 및 서비스 소개
st.title("📑 AI 월말 정산 도우미 (POC)")
st.markdown("""
**안녕하세요, 담당자님! 한 달간의 정산 업무를 돕기 위한 AI 프로토타입입니다.**  
지출 내역과 증빙 자료를 올리면 AI가 매칭 상태를 확인하고 계정과목을 제안합니다.  
최종 결정은 담당자님의 몫이니, AI의 초안을 자유롭게 검토하고 수정해 주세요! 😊
""")
st.warning("⚠️ **주의:** 본 시스템은 개인정보를 수집하지 않으며, AI 결과는 확정된 회계 전표가 아닙니다.")

# 1. 데이터 입력 영역
st.header("1단계: 데이터 준비하기")
st.markdown("정산에 필요한 **지출 내역**과 **증빙 목록** 파일을 업로드해 주세요. 파일이 없다면 샘플 데이터로 테스트가 가능합니다.")

col1, col2, col3 = st.columns(3)
with col1:
    exp_file = st.file_uploader("💳 지출 내역 (카드/계좌)", type=['csv', 'xlsx'])
    st.caption("거래일자, 거래처명, 금액이 포함되어야 합니다.")
with col2:
    rec_file = st.file_uploader("📄 증빙 자료 목록", type=['csv', 'xlsx'])
    st.caption("파일명과 거래 정보가 매칭되는 파일입니다.")
with col3:
    rule_file = st.file_uploader("📋 계정과목 기준표 (선택)", type=['csv', 'xlsx'])
    st.caption("우리 회사만의 분류 규칙이 있다면 올려주세요.")

if st.button("📁 샘플 데이터로 바로 시작해보기"):
    st.session_state.exp_df = safe_read_csv(FILE_PATHS["지출내역"])
    st.session_state.rec_df = safe_read_csv(FILE_PATHS["증빙자료"])
    st.session_state.rule_df = safe_read_csv(FILE_PATHS["계정과목"])
    st.success("샘플 데이터를 성공적으로 불러왔습니다! 아래에서 내용을 확인하고 분석을 시작하세요.")

# 데이터 업로드 반영
if exp_file: st.session_state.exp_df = preprocess_df(pd.read_csv(exp_file) if exp_file.name.endswith('csv') else pd.read_excel(exp_file))
if rec_file: st.session_state.rec_df = preprocess_df(pd.read_csv(rec_file) if rec_file.name.endswith('csv') else pd.read_excel(rec_file))
if rule_file: st.session_state.rule_df = preprocess_df(pd.read_csv(rule_file) if rule_file.name.endswith('csv') else pd.read_excel(rule_file))

# 데이터 미리보기 및 AI 분석 실행
if st.session_state.exp_df is not None:
    with st.expander("👀 로드된 데이터 미리보기"):
        st.write("데이터가 올바른지 확인해 주세요.")
        t1, t2 = st.tabs(["지출 내역", "증빙 자료"])
        with t1: st.dataframe(st.session_state.exp_df.head(10), use_container_width=True)
        with t2: st.dataframe(st.session_state.rec_df.head(10), use_container_width=True)

    st.markdown("---")
    st.header("2단계: AI 분석 및 초안 생성")
    st.markdown("AI가 지출 내역과 증빙을 대조하고, 적절한 계정과목 코드를 찾아드립니다.")
    
    if st.button("🤖 AI 초안 생성 시작", type="primary"):
        with st.spinner("데이터를 꼼꼼하게 분석하고 있습니다. 잠시만 기다려 주세요..."):
            res, p_time = run_ai_analysis(st.session_state.exp_df, st.session_state.rec_df, st.session_state.rule_df)
            st.session_state.processed_data = res
            st.session_state.process_time = p_time
            st.session_state.analysis_done = True
        st.balloons()
        st.success(f"분석이 완료되었습니다! (소요시간: {p_time}초)")

# 3. 사용자 검토 영역
if st.session_state.analysis_done:
    st.divider()
    st.header("3단계: AI 초안 검토 및 수정")
    st.info("""
    **💡 검토 팁:**
    1. **최종_비용항목** 셀을 더블 클릭하여 드롭다운에서 올바른 항목을 골라보세요.
    2. 항목을 바꾸면 **최종_계정과목(코드)**이 자동으로 따라옵니다.
    3. **신뢰도**가 낮은 항목(붉은색)은 한 번 더 확인해 주시는 것이 좋습니다.
    """)

    # 편집 데이터 준비 및 동기화
    df_to_edit = st.session_state.processed_data.copy()
    
    edited_df = st.data_editor(
        df_to_edit[['거래일자', '거래처명', '금액', '매칭상태', 'AI비용항목', '최종_비용항목', '최종_계정과목', '신뢰도']],
        use_container_width=True,
        column_config={
            "최종_비용항목": st.column_config.SelectboxColumn("최종_비용항목 (수정가능)", options=list(st.session_state.mapping_dict.keys())),
            "최종_계정과목": st.column_config.TextColumn("최종_계정과목 (자동)", disabled=True),
            "신뢰도": st.column_config.ProgressColumn("AI 신뢰도", format="%.2f", min_value=0, max_value=1),
        },
        disabled=['거래일자', '거래처명', '금액', '매칭상태', 'AI비용항목', '신뢰도'],
        key="editor"
    )

    # 수정 사항 실시간 반영 (계정과목 코드 매핑 포함)
    edited_df['최종_계정과목'] = edited_df['최종_비용항목'].map(st.session_state.mapping_dict)
    st.session_state.processed_data.update(edited_df)

    # 4. 최종 정산표 및 다운로드
    st.header("4단계: 최종 정산표 확인 및 저장")
    st.markdown("수정이 완료되었습니다! 확정된 데이터를 확인하고 파일로 저장하여 정산업무를 마무리하세요.")
    
    final_view = st.session_state.processed_data[['거래일자', '거래처명', '금액', '매칭상태', '최종_비용항목', '최종_계정과목']].copy()
    final_view.columns = ['거래일자', '거래처명', '금액', '증빙여부', '비용항목(확정)', '계정과목(확정)']
    st.dataframe(final_view, use_container_width=True)

    c1, c2 = st.columns([1, 4])
    with c1:
        st.download_button(
            "📥 최종 정산표 CSV 다운로드", 
            final_view.to_csv(index=False).encode('utf-8-sig'), 
            f"정산결과_{datetime.now().strftime('%m%d')}.csv", 
            "text/csv"
        )

    # 5. 성과 대시보드
    st.divider()
    st.header("📊 POC 성과 리포트")
    st.markdown("AI 초안 도입으로 정산 업무가 얼마나 단축되었는지 확인하는 지표입니다.")
    
    total = len(final_view)
    mod_count = (st.session_state.processed_data['AI비용항목'] != st.session_state.processed_data['최종_비용항목']).sum()
    mod_rate = (mod_count / total * 100)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("총 처리 건수", f"{total}건")
    m2.metric("AI 초안 수정 비율", f"{mod_rate:.1f}%", help="수정 비율이 30% 이하라면 AI 성능이 우수함을 의미합니다.")
    m3.metric("AI 분석 소요 시간", f"{st.session_state.process_time}초", help="기존 수동 분류 대비 절감된 시간의 핵심 지표입니다.")

    st.markdown("---")
    st.subheader("🏁 POC 목표 달성 판정")
    st.write("이번 정산 작업에 대한 담당자님의 만족도를 알려주세요.")
    sat_score = st.slider("이번 AI 초안 생성이 업무 시간을 줄이는 데 도움이 되었나요? (5점: 매우 만족)", 1, 5, 4)
    
    # 판정 로직
    is_mod_ok = mod_rate <= 30
    is_sat_ok = sat_score >= 4
    
    if is_mod_ok and is_sat_ok:
        st.success(f"### 🎉 판정 결과: [확산 검토 권장]\n수정 비율({mod_rate:.1f}%)과 만족도({sat_score}점)가 목표를 달성했습니다! 정산 업무를 본 시스템으로 전환 시 높은 효율이 기대됩니다.")
    elif is_mod_ok or is_sat_ok:
        st.warning(f"### ⚖️ 판정 결과: [개선 후 재실험]\n일부 지표는 달성했으나 보완이 필요합니다. AI의 정확도를 높이거나 사용자 가이드를 강화해 주세요.")
    else:
        st.error(f"### 🛑 판정 결과: [현행 유지 또는 축소]\n현재로서는 AI 초안의 효용성이 낮습니다. 데이터 품질 확인 혹은 프로세스 재설계가 필요합니다.")
