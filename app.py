import streamlit as st
import pandas as pd
import numpy as np
import time
from datetime import datetime

# --- 페이지 설정 ---
st.set_page_config(page_title="월말 정산표 초안 작성 POC", layout="wide")

# --- CSS 스타일링 ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
    .stAlert { margin-top: 10px; }
    </style>
""", unsafe_allow_html=True)

# --- 세션 상태 초기화 (데이터 유지용) ---
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'start_time' not in st.session_state:
    st.session_state.start_time = None
if 'analysis_done' not in st.session_state:
    st.session_state.analysis_done = False

# --- 헬퍼 함수: 샘플 데이터 생성 ---
def generate_sample_data():
    # 1. 지출 내역
    expense_data = pd.DataFrame({
        '거래일자': pd.date_range(start='2024-04-01', periods=10).strftime('%Y-%m-%d'),
        '거래처명': ['스타벅스', '교보문고', '카카오T', 'AWS Cloud', '강남식당', '알파문구', '배달의민족', '우버', '슬랙', '파리바게뜨'],
        '금액': [5400, 25000, 12000, 450000, 55000, 15000, 32000, 18000, 85000, 12000],
        '사용부서': ['영업부', '인사팀', '개발팀', '개발팀', '영업부', '경영지원', '개발팀', '영업부', '개발팀', '인사팀'],
        '사용자': ['김철수', '이영희', '박지성', 'AI자동', '김철수', '최미나', '박지성', '김철수', 'AI자동', '이영희'],
        '카드승인번호': ['A101', 'A102', 'A103', 'A104', 'A105', 'A106', 'A107', 'A108', 'A109', 'A110'],
        '적요': ['커피미팅', '도서구입', '외근이동', '서버비용', '점심식사', '사무용품', '야근식대', '외근이동', '협업툴구독', '간식구입']
    })
    
    # 2. 증빙 자료 (일부 누락/일부 불일치 유도)
    receipt_data = pd.DataFrame({
        '파일명': ['rec_01.jpg', 'rec_02.pdf', 'rec_04.png', 'rec_05.jpg', 'rec_06.png', 'rec_08.jpg'],
        '거래일자': ['2024-04-01', '2024-04-02', '2024-04-04', '2024-04-05', '2024-04-06', '2024-04-08'],
        '거래처명': ['스타벅스', '교보문고', 'AWS Cloud', '강남식당', '알파문구', '우버'],
        '금액': [5400, 25000, 450000, 55000, 15000, 18000],
        '증빙종류': ['영수증', '영수증', '인보이스', '영수증', '영수증', '영수증'],
        '제출여부': ['Y', 'Y', 'Y', 'Y', 'Y', 'Y']
    })
    
    # 3. 계정과목 기준표
    account_rules = pd.DataFrame({
        '거래처 키워드': ['스타벅스', '식당', '카페', '문구', '오피스', 'T', '택시', '교통', 'AWS', '슬랙', 'SaaS', '구독'],
        '비용 항목': ['회의비', '접대비', '회의비', '소모품비', '소모품비', '여비교통비', '여비교통비', '여비교통비', '지급수수료', '지급수수료', '지급수수료', '지급수수료'],
        '계정과목': ['81100', '81300', '81100', '82200', '82200', '81400', '81400', '81400', '84500', '84500', '84500', '84500']
    })
    
    return expense_data, receipt_data, account_rules

# --- 핵심 로직: AI Mock 분석 함수 ---
def run_ai_analysis(exp_df, rec_df, rule_df):
    start_time = time.time()
    
    # 1. 취합 및 증빙 매칭
    # 거래일자, 거래처명, 금액이 모두 일치하는지 확인
    merged = pd.merge(exp_df, rec_df, on=['거래일자', '거래처명', '금액'], how='left')
    
    # 매칭 결과 상태 부여
    def check_status(row):
        if pd.notnull(row['파일명']):
            return "일치 (증빙확인)"
        else:
            return "누락 의심 (증빙없음)"
    
    merged['매칭상태'] = merged.apply(check_status, axis=1)
    merged['누락판단근거'] = merged['매칭상태'].apply(lambda x: "증빙 파일 매칭 실패" if "누락" in x else "정상 매칭")

    # 2. 계정과목 분류 (AI Mock 로직)
    def classify_account(row):
        merchant = row['거래처명']
        # 1순위: 기준표 매칭
        if rule_df is not None:
            for idx, r in rule_df.iterrows():
                if r['거래처 키워드'] in merchant:
                    return r['비용 항목'], r['계정과목'], 0.95
        
        # 2순위: 기본 규칙 (fallback)
        if any(k in merchant for k in ['카페', '식당', '민족', '바게뜨']):
            return '복리후생비/접대비', '81100/81300', 0.80
        elif any(k in merchant for k in ['T', '택시', '우버']):
            return '여비교통비', '81400', 0.85
        elif any(k in merchant for k in ['Cloud', '슬랙', 'SaaS']):
            return '지급수수료', '84500', 0.90
        
        return '검토 필요', '미분류', 0.50

    results = merged.apply(classify_account, axis=1, result_type='expand')
    merged['AI비용항목'] = results[0]
    merged['AI계정과목'] = results[1]
    merged['신뢰도'] = results[2]
    
    # 사용자 수정을 위한 컬럼 복사
    merged['수정_비용항목'] = merged['AI비용항목']
    merged['수정_계정과목'] = merged['AI계정과목']
    
    processing_time = round(time.time() - start_time, 2)
    return merged, processing_time

# --- UI 레이아웃 ---

st.title("📂 월말 정산표 초안 작성 POC 프로토타입")
st.info("💡 **안내:** 이 프로토타입은 회계 판단을 자동화하지 않습니다. AI 분석 결과는 검토용 초안이며, 최종 판단과 확정은 회계담당자가 수행해야 합니다.")

# 1. 데이터 입력 섹션
st.header("1. 데이터 입력")
col1, col2, col3 = st.columns(3)

with col1:
    exp_file = st.file_uploader("지출 내역 업로드 (CSV/XLSX)", type=['csv', 'xlsx'])
with col2:
    rec_file = st.file_uploader("증빙 자료 목록 업로드 (CSV/XLSX)", type=['csv', 'xlsx'])
with col3:
    rule_file = st.file_uploader("계정과목 기준표 (선택)", type=['csv', 'xlsx'])

use_sample = st.button("🚀 샘플 데이터로 실행")

# 데이터 로드 로직
exp_df, rec_df, rule_df = None, None, None

if use_sample:
    exp_df, rec_df, rule_df = generate_sample_data()
elif exp_file and rec_file:
    try:
        exp_df = pd.read_csv(exp_file) if exp_file.name.endswith('csv') else pd.read_excel(exp_file)
        rec_df = pd.read_csv(rec_file) if rec_file.name.endswith('csv') else pd.read_excel(rec_file)
        if rule_file:
            rule_df = pd.read_csv(rule_file) if rule_file.name.endswith('csv') else pd.read_excel(rule_file)
    except Exception as e:
        st.error(f"파일 로드 중 오류 발생: {e}")

# 2. 데이터 미리보기 및 유효성 검사
if exp_df is not None and rec_df is not None:
    with st.expander("데이터 미리보기 및 필드 확인"):
        # 필드 체크
        required_exp = ['거래일자', '거래처명', '금액']
        missing_exp = [f for f in required_exp if f not in exp_df.columns]
        if missing_exp:
            st.warning(f"지출 내역에 필수 필드가 누락되었습니다: {missing_exp}")
        
        st.subheader("지출 내역")
        st.dataframe(exp_df.head(5), use_container_width=True)
        st.subheader("증빙 자료")
        st.dataframe(rec_df.head(5), use_container_width=True)

    # 3. AI 분석 실행 버튼
    if st.button("🤖 AI 초안 생성 시작"):
        with st.spinner("데이터를 분석하여 초안을 생성 중입니다..."):
            processed_df, p_time = run_ai_analysis(exp_df, rec_df, rule_df)
            st.session_state.processed_data = processed_df
            st.session_state.process_time = p_time
            st.session_state.analysis_done = True
        st.success(f"분석 완료! (처리 시간: {p_time}초)")

# 4. 분석 결과 및 사용자 검토
if st.session_state.analysis_done:
    st.header("2. AI 분석 결과 및 사용자 검토")
    
    df = st.session_state.processed_data
    
    tab1, tab2, tab3 = st.tabs(["📋 전체 취합 목록", "⚠️ 누락 의심 항목", "🔍 분류 초안 검토"])
    
    with tab1:
        st.write("지출 내역과 증빙을 매칭한 전체 목록입니다.")
        st.dataframe(df[['거래일자', '거래처명', '금액', '사용자', '매칭상태', 'AI비용항목']], use_container_width=True)
        
    with tab2:
        missing_items = df[df['매칭상태'].str.contains("누락")]
        st.warning(f"총 {len(missing_items)}건의 증빙 누락이 의심됩니다.")
        st.table(missing_items[['거래일자', '거래처명', '금액', '사용자', '누락판단근거']])
        
    with tab3:
        st.markdown("##### 📝 항목 수정 (수정 후 Enter)")
        st.caption("AI가 제안한 비용항목과 계정과목을 확인하고 필요시 수정하세요.")
        
        # 편집 가능한 테이블 제공
        edit_cols = ['거래일자', '거래처명', '금액', 'AI비용항목', 'AI계정과목', '수정_비용항목', '수정_계정과목', '신뢰도']
        edited_df = st.data_editor(
            df[edit_cols],
            column_config={
                "신뢰도": st.column_config.ProgressColumn("AI 신뢰도", format="%.2f", min_value=0, max_value=1),
                "수정_비용항목": st.column_config.SelectboxColumn("최종 비용항목", options=["회의비", "접대비", "소모품비", "여비교통비", "지급수수료", "복리후생비"]),
            },
            use_container_width=True,
            key="editor"
        )
        
        # 수정 사항 반영
        if st.button("수정 사항 저장"):
            st.session_state.processed_data.update(edited_df)
            st.toast("수정 사항이 저장되었습니다.")

    # 5. 성과 대시보드 및 OKR
    st.divider()
    st.header("3. POC 성과 대시보드")
    
    # 지표 계산
    total_count = len(df)
    missing_count = len(df[df['매칭상태'].str.contains("누락")])
    review_needed_count = len(df[df['AI비용항목'] == '검토 필요'])
    
    # 수정 비율 계산 (AI 초안과 사용자 수정본 비교)
    modified_mask = (df['AI비용항목'] != df['수정_비용항목']) | (df['AI계정과목'] != df['수정_계정과목'])
    modified_count = modified_mask.sum()
    correction_rate = (modified_count / total_count) * 100 if total_count > 0 else 0
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("전체 항목 수", f"{total_count}건")
    m2.metric("누락 의심", f"{missing_count}건", delta_color="inverse")
    m3.metric("AI 초안 수정 비율", f"{correction_rate:.1f}%", delta="-30% 목표")
    m4.metric("분석 처리 시간", f"{st.session_state.process_time}초")

    st.subheader("🎯 OKR 달성 현황 판정")
    
    c1, c2 = st.columns(2)
    with c1:
        actual_missing_confirm = st.number_input("실제 누락으로 확인된 건수 (검증용 입력)", min_value=0, max_value=total_count, value=missing_count)
        user_sat_score = st.slider("업무 효율 체감 점수 (1~5점)", 1, 5, 4)
    
    # 누락 탐지 정확도
    precision = (actual_missing_confirm / missing_count * 100) if missing_count > 0 else 100
    
    # 판정 기준
    kr1 = st.session_state.process_time < 60  # 처리시간 (프로토타입 기준)
    kr2 = correction_rate <= 30
    kr3 = precision >= 70
    kr4 = user_sat_score >= 4
    
    success_count = sum([kr1, kr2, kr3, kr4])
    
    res_col1, res_col2, res_col3, res_col4 = st.columns(4)
    res_col1.info(f"작성 시간: {'✅ 달성' if kr1 else '❌ 미달'}")
    res_col2.info(f"수정 비율: {'✅ 달성' if kr2 else '❌ 미달'}")
    res_col3.info(f"탐지 정확도: {'✅ 달성' if kr3 else '❌ 미달'}")
    res_col4.info(f"체감 만족도: {'✅ 달성' if kr4 else '❌ 미달'}")
    
    if success_count >= 3:
        st.success(f"### 🚀 최종 판단: [확산 검토] (KR {success_count}개 달성)")
    elif success_count == 2:
        st.warning(f"### ⚖️ 최종 판단: [개선 후 재실험] (KR {success_count}개 달성)")
    else:
        st.error(f"### 🛑 최종 판단: [중단 또는 축소] (KR {success_count}개 달성)")

    # 6. 결과 다운로드
    st.divider()
    final_csv = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 최종 정산표 초안 다운로드 (CSV)",
        data=final_csv,
        file_name=f"settlement_draft_{datetime.now().strftime('%Y%m%d')}.csv",
        mime='text/csv'
    )
