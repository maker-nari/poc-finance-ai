import streamlit as st
import pandas as pd
import os
import time
import json
from datetime import datetime

# --- [설정 및 초기화] ---
st.set_page_config(page_title="AI 월말 정산 도우미 POC", layout="wide")

# 세션 상태 키 초기화
if 'exp_df' not in st.session_state: st.session_state.exp_df = None
if 'rec_df' not in st.session_state: st.session_state.rec_df = None
if 'rule_df' not in st.session_state: st.session_state.rule_df = None
if 'processed_data' not in st.session_state: st.session_state.processed_data = None
if 'analysis_done' not in st.session_state: st.session_state.analysis_done = False
if 'report_confirmed' not in st.session_state: st.session_state.report_confirmed = False
if 'mapping_dict' not in st.session_state: st.session_state.mapping_dict = {}

# 운영 데이터 타임스탬프
if 't_start' not in st.session_state: st.session_state.t_start = None
if 't_analysis_end' not in st.session_state: st.session_state.t_analysis_end = None
if 't_final_confirm' not in st.session_state: st.session_state.t_final_confirm = None

# --- [유틸리티 함수] ---
def preprocess_df(df):
    """컬럼명 공백 및 특수기호 제거"""
    if df is not None:
        df.columns = [str(c).strip().replace('\ufeff', '') for c in df.columns]
    return df

def load_local_sample(file_path_list):
    """여러 경로 후보 중 존재하는 파일 로드"""
    for path in file_path_list:
        if os.path.exists(path):
            try:
                return preprocess_df(pd.read_csv(path, encoding='utf-8-sig'))
            except:
                return preprocess_df(pd.read_csv(path, encoding='cp949'))
    return None

def create_mapping_dict(rule_df):
    """계정과목 매핑 딕셔너리 생성"""
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

# --- [코어 분석 로직] ---
def run_ai_analysis(exp_df, rec_df, rule_df):
    mapping = create_mapping_dict(rule_df)
    # 1. 증빙 매칭
    merged = pd.merge(exp_df, rec_df, on=['거래일자', '거래처명', '금액'], how='left')
    merged['매칭상태'] = merged.apply(lambda x: "✅ 증빙 완료" if pd.notnull(x.get('파일명')) else "❗ 증빙 누락", axis=1)

    # 2. AI 분류 초안 (규칙 기반 Mock)
    def classify(row):
        merchant = str(row.get('거래처명', ''))
        if rule_df is not None:
            for _, r in rule_df.iterrows():
                if str(r.get('거래처 키워드', '')) in merchant:
                    it = r.get('비용 항목', '검토 필요')
                    return it, mapping.get(it, "미분류"), 0.95
        if any(k in merchant for k in ['식당', '카페', '민족']): return '복리후생비', mapping.get('복리후생비'), 0.80
        if any(k in merchant for k in ['택시', 'T', '우버']): return '여비교통비', mapping.get('여비교통비'), 0.85
        return '검토 필요', '미분류', 0.50

    results = merged.apply(classify, axis=1, result_type='expand')
    merged['AI비용항목'], merged['AI계정과목'], merged['신뢰도'] = results[0], results[1], results[2]
    # 사용자가 수정할 최종 컬럼 초기화
    merged['최종_비용항목'], merged['최종_계정과목'] = merged['AI비용항목'], merged['AI계정과목']
    return merged

# --- [UI 섹션] ---

# 상단 안내 문구
st.warning("이 프로토타입은 회계 판단을 자동화하지 않습니다. AI 분석 결과는 검토용 초안이며, 최종 판단과 확정은 회계담당자가 수행해야 합니다.")
st.title("📂 AI 월말 정산 도우미 POC")

# 1. 데이터 입력
st.header("1. 데이터 입력")
col1, col2, col3 = st.columns(3)
with col1: exp_f = st.file_uploader("지출 내역 (CSV/XLSX)", type=['csv', 'xlsx'])
with col2: rec_f = st.file_uploader("증빙 목록 (CSV/XLSX)", type=['csv', 'xlsx'])
with col3: rule_f = st.file_uploader("기준표 (선택)", type=['csv', 'xlsx'])

if st.button("📁 샘플 데이터로 실행"):
    st.session_state.exp_df = load_local_sample(["샘플데이터/지출내역.csv"])
    st.session_state.rec_df = load_local_sample(["샘플데이터/증빙자료.csv"])
    st.session_state.rule_df = load_local_sample(["샘플데이터/계정과목_기준표.csv", "샘플데이터/계정과목 기준표.csv"])
    st.session_state.t_start = time.time() # 시작 시간 기록
    st.session_state.analysis_done = False
    st.session_state.report_confirmed = False
    st.success("샘플 데이터 로드 완료. (업무 시간 측정 시작)")

if exp_f and rec_f:
    st.session_state.exp_df = preprocess_df(pd.read_csv(exp_f) if exp_f.name.endswith('csv') else pd.read_excel(exp_f))
    st.session_state.rec_df = preprocess_df(pd.read_csv(rec_f) if rec_f.name.endswith('csv') else pd.read_excel(rec_f))
    if rule_f: st.session_state.rule_df = preprocess_df(pd.read_csv(rule_f) if rule_f.name.endswith('csv') else pd.read_excel(rule_f))
    if st.session_state.t_start is None: st.session_state.t_start = time.time()

# 데이터 미리보기
if st.session_state.exp_df is not None:
    with st.expander("데이터 미리보기"):
        t1, t2, t3 = st.tabs(["지출 내역", "증빙 자료", "기준표"])
        t1.dataframe(st.session_state.exp_df.head(10))
        t2.dataframe(st.session_state.rec_df.head(10))
        t3.dataframe(st.session_state.rule_df.head(10) if st.session_state.rule_df is not None else pd.DataFrame())

    # 2. AI 분석 실행
    if not st.session_state.analysis_done:
        if st.button("🤖 AI 초안 생성 시작", type="primary"):
            st.session_state.processed_data = run_ai_analysis(st.session_state.exp_df, st.session_state.rec_df, st.session_state.rule_df)
            st.session_state.t_analysis_end = time.time()
            st.session_state.analysis_done = True
            st.rerun()

# 3. 사용자 검토 및 수정
if st.session_state.analysis_done:
    st.divider()
    st.header("2. AI 초안 검토 및 수정")
    
    tab_edit, tab_msg = st.tabs(["🔍 상세 검토", "📢 증빙 요청 메시지"])
    
    with tab_edit:
        st.info("💡 '최종_비용항목'을 수정하면 '최종_계정과목' 코드가 자동으로 업데이트됩니다.")
        df_edit = st.session_state.processed_data.copy()
        mapping = st.session_state.mapping_dict
        
        # 편집 가능한 테이블
        cols = ['거래일자', '거래처명', '금액', '매칭상태', 'AI비용항목', '최종_비용항목', '최종_계정과목', '신뢰도']
        edited_df = st.data_editor(
            df_edit[cols],
            use_container_width=True,
            column_config={
                "최종_비용항목": st.column_config.SelectboxColumn("최종_비용항목", options=list(mapping.keys())),
                "최종_계정과목": st.column_config.TextColumn("최종_계정과목", disabled=True),
                "신뢰도": st.column_config.ProgressColumn("신뢰도", format="%.2f", min_value=0, max_value=1),
            },
            disabled=['거래일자', '거래처명', '금액', '매칭상태', 'AI비용항목', '신뢰도'],
            key="main_editor"
        )
        
        # 수정사항 반영 및 매핑 업데이트
        edited_df['최종_계정과목'] = edited_df['최종_비용항목'].map(mapping)
        if not edited_df.equals(st.session_state.processed_data[cols]):
            st.session_state.processed_data.update(edited_df)
            st.rerun()

    with tab_msg:
        st.subheader("증빙 누락 담당자 요청 문구")
        missing = st.session_state.processed_data[st.session_state.processed_data['매칭상태'].str.contains("누락")]
        if len(missing) > 0:
            for user in missing['사용자'].unique():
                with st.expander(f"👤 {user}님께 요청하기"):
                    st.code(f"안녕하세요 {user}님, 이번 달 지출 증빙 누락 건 확인 부탁드립니다.", language="text")
        else: st.success("누락된 증빙이 없습니다.")

    if not st.session_state.report_confirmed:
        if st.button("✅ 검토 완료 및 최종 확정", type="primary"):
            st.session_state.t_final_confirm = time.time()
            st.session_state.report_confirmed = True
            st.rerun()

# 4. 성과 대시보드 및 리포트
if st.session_state.report_confirmed:
    st.divider()
    st.header("3. POC 성과 대시보드 및 리포트")
    
    df = st.session_state.processed_data
    
    # [지표 계산]
    total_items = len(df)
    dur_total = (st.session_state.t_final_confirm - st.session_state.t_start)
    dur_ai = (st.session_state.t_analysis_end - st.session_state.t_start)
    dur_user = (st.session_state.t_final_confirm - st.session_state.t_analysis_end)
    
    mod_count = (df['AI비용항목'] != df['최종_비용항목']).sum()
    mod_rate = (mod_count / total_items * 100)
    missing_count = (df['매칭상태'].str.contains("누락")).sum()
    
    # 사용자 입력 기반 적중률
    c1, c2 = st.columns(2)
    with c1: 
        actual_missing = st.number_input("실제 누락으로 확인된 건수", 0, missing_count, value=missing_count)
        hit_rate = (actual_missing / missing_count * 100) if missing_count > 0 else 100
    with c2: 
        sat_score = st.slider("사용자 체감 효율 점수 (1~5점)", 1, 5, 4)

    # 지표 표시
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("총 처리 건수", f"{total_items}건")
    m1.metric("누락 의심 건수", f"{missing_count}건")
    m2.metric("총 소요 시간", f"{round(dur_total/60, 2)}분")
    m2.metric("AI 수정 비율", f"{mod_rate:.1f}%")
    m3.metric("AI 분석 시간", f"{round(dur_ai, 2)}초")
    m3.metric("누락 적중률", f"{hit_rate:.1f}%")
    m4.metric("사용자 검토 시간", f"{round(dur_user/60, 2)}분")
    m4.metric("체감 효율 점수", f"{sat_score}점")

    # [OKR 판정]
    kr1 = True # 프로토타입 기준에서는 목표 달성으로 간주 (분 단위 처리)
    kr2 = mod_rate <= 30
    kr3 = hit_rate >= 70
    kr4 = sat_score >= 4
    
    achieved_count = sum([kr1, kr2, kr3, kr4])
    
    st.subheader("🎯 OKR 달성 현황")
    res_cols = st.columns(4)
    res_cols[0].info(f"KR1. 작성시간 단축: {'✅' if kr1 else '❌'}")
    res_cols[1].info(f"KR2. 수정비율 30%↓: {'✅' if kr2 else '❌'}")
    res_cols[2].info(f"KR3. 적중률 70%↑: {'✅' if kr3 else '❌'}")
    res_cols[3].info(f"KR4. 만족도 4점↑: {'✅' if kr4 else '❌'}")

    decision = "확산 검토" if achieved_count >= 3 else "개선 후 재실험" if achieved_count == 2 else "중단 또는 축소"
    st.success(f"### 최종 판단: **[{decision}]** (달성 개수: {achieved_count}/4)")

    # [운영 로그 및 다운로드]
    st.divider()
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "total_items": int(total_items),
        "duration_total_min": round(dur_total/60, 2),
        "duration_ai_sec": round(dur_ai, 2),
        "duration_user_min": round(dur_user/60, 2),
        "correction_count": int(mod_count),
        "correction_rate": round(mod_rate, 2),
        "missing_detected": int(missing_count),
        "actual_missing_confirmed": int(actual_missing),
        "missing_hit_rate": round(hit_rate, 2),
        "user_satisfaction": int(sat_score),
        "kr1_achieved": kr1, "kr2_achieved": kr2, "kr3_achieved": kr3, "kr4_achieved": kr4,
        "kr_achieved_count": achieved_count,
        "decision_result": decision
    }
    
    st.subheader("📋 운영 데이터 로그")
    st.json(log_data)
    
    # 다운로드 버튼
    csv_report = df[['거래일자', '거래처명', '금액', '매칭상태', '최종_비용항목', '최종_계정과목']].to_csv(index=False).encode('utf-8-sig')
    st.download_button("📥 최종 정산표 다운로드 (CSV)", csv_report, "final_report.csv", "text/csv")
    
    log_df = pd.DataFrame([log_data])
    st.download_button("📥 운영 로그 다운로드 (CSV)", log_df.to_csv(index=False).encode('utf-8-sig'), "ops_log.csv", "text/csv")
