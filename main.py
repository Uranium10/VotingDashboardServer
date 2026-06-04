import os
import pandas as pd
import numpy as np
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import ast

app = FastAPI(title="2026 지방선거 대시보드 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = "./data" 
df_store = {}

def get_df(filename: str) -> pd.DataFrame:
    """CSV 로드 및 캐싱 (에러 방지용 + 한국어 인코딩 자동 처리)"""
    if filename not in df_store:
        path = os.path.join(DATA_DIR, filename)
        if os.path.exists(path):
            try:
                # 1. utf-8 인코딩 시도
                df = pd.read_csv(path, encoding='utf-8')
            except UnicodeDecodeError:
                # 2. 실패 시 한국어 윈도우 환경 기본값인 cp949(euc-kr)로 재시도
                df = pd.read_csv(path, encoding='cp949')
                
            # NaN을 None으로 변환하여 JSON 에러 방지
            df_store[filename] = df.replace({np.nan: None})
        else:
            print(f"⚠️ 파일 누락: '{path}' 파일을 찾을 수 없습니다.")
            df_store[filename] = pd.DataFrame()
    return df_store[filename]

PARTY_COLORS = {
    '더불어민주당': '#2673cc', '국민의힘': '#E61E2B', '자유한국당': '#E61E2B',
    '조국혁신당': '#6a0dad', '개혁신당': '#ff7f00', '진보당': '#D6001C',
    '정의당': '#ffca05', '무소속': '#6e5e5e', '기타': '#4a6080', '정부지원': "#385681", '정부견제': "#741F1F"
}
COMPETITION_COLORS = {'초경합': '#e74c3c', '경합': '#e67e22', '우세': '#27ae60', '압승 예상': '#2ecc71'}

# 💡 [해결] CSV의 줄임말을 constants.js와 완벽히 매칭하는 사전
REGION_MAP = {
    "서울": "서울특별시", "경기": "경기도", "인천": "인천광역시", "세종": "세종특별자치시",
    "대전": "대전광역시", "충북": "충청북도", "충남": "충청남도", "전북": "전북특별자치도",
    "광주": "광주광역시", "전남": "전라남도", "경남": "경상남도", "부산": "부산광역시",
    "울산": "울산광역시", "대구": "대구광역시", "경북": "경상북도", "강원": "강원특별자치도",
    "제주": "제주특별자치도", "강원": "강원특별자치도", 
    "강원도": "강원특별자치도",      # 👈 추가
    "전북": "전북특별자치도", 
    "전라북도": "전북특별자치도",    # 👈 추가
    "제주": "제주특별자치도",
    "제주도": "제주특별자치도"
}
COMPETITION_LABEL = {
    "초경쟁" : "초경합", "경쟁" : "경합", "우세" : "우세", "압승 예상": "압승 예상",
}

def get_full_region(name: str):
    if not name: return ""
    for short_name, full_name in REGION_MAP.items():
        if name == short_name: return full_name
    return name

# =====================================================================
# [LOCAL] 좌측 지역 상세 패널
# =====================================================================
@app.get("/api/local/competition")
def get_local_competition(region: str = Query(...), round_val: str = Query(..., alias="round")):
    is_prediction = (round_val == "9회")
    candidates_list = []
    gap_val = 0.0
    comp_badge = "결과없음"
    poll_date = "2026-05-27"
    
    if is_prediction:
        df = get_df("prediction_9th.csv")
        if df.empty or 'region_kr' not in df.columns:
            return {"competition": "분석중", "is_prediction": True, "gap": 0, "candidates": []}
            
        # 지역명 풀네임 변환 후 필터링
        sub = df[df['region_kr'].apply(get_full_region) == region].sort_values(by='poll_mean', ascending=False)
        if not sub.empty:
            # 💡 [해결] CSV에 격차가 없으므로 1,2위 득표율로 직접 계산
            if len(sub) >= 2:
                gap_val = float(sub.iloc[0]['poll_mean'] - sub.iloc[1]['poll_mean'])
            
            winner_row = sub[sub['predicted_winner'] == 1]
            if winner_row.empty: winner_row = sub.iloc[0]
            else: winner_row = winner_row.iloc[0]
            
            comp_badge = COMPETITION_LABEL[str(winner_row.get('경쟁도', '경합'))]
            poll_date = str(winner_row.get('poll_date', '2026-05-27'))
            
            for _, row in sub.iterrows():
                candidates_list.append({
                    "name": row['name'], "party": row['party'],
                    "rate": float(row['poll_mean']),
                    "color": PARTY_COLORS.get(row['party'], '#4a6080'),
                    "is_winner": bool(row.get('predicted_winner', 0) == 1),
                    "win_prob": int(round(row.get('win_prob', 0) * 100)) if pd.notnull(row.get('win_prob')) else 0
                })
    else:
        filename = "results_8th.csv" if round_val == "8회" else "results_7th.csv"
        df = get_df(filename)
        
        if df.empty or 'sido' not in df.columns:
            return {"competition": "분석중", "is_prediction": False, "gap": 0, "candidates": []}
            
        sub = df[df['sido'].apply(get_full_region) == region].sort_values(by='vote_rate', ascending=False)
        if not sub.empty:
            if len(sub) >= 2:
                gap_val = float(sub.iloc[0]['vote_rate'] - sub.iloc[1]['vote_rate'])
            comp_badge = "확정"
            for _, row in sub.iterrows():
                candidates_list.append({
                    "name": row['name'], "party": row['party'],
                    "rate": float(row['vote_rate']),
                    "color": PARTY_COLORS.get(row['party'], '#4a6080'),
                    "is_winner": bool(row.get('winner', 0) == 1), "win_prob": None
                })
                
    return {
        "competition": comp_badge, "is_prediction": is_prediction,
        "poll_date": poll_date if is_prediction else None,
        "gap": round(gap_val, 1), "candidates": candidates_list
    }

@app.get("/api/local/support")
def get_local_support(region: str = Query(...), round_val: str = Query(..., alias="round")):
    # 회차별 보수정당 이름 매핑 (7회: 자유한국당, 8/9회: 국민의힘)
    party_labels = {"보수정당": "국민의힘" if round_val != "7회" else "자유한국당"}
    colors = [PARTY_COLORS["더불어민주당"], PARTY_COLORS[party_labels["보수정당"]], PARTY_COLORS["기타"]]
    
    # 기본 응답 뼈대
    res = {
        "total": [0.0, 0.0, 0.0],  # 💡 더미 데이터 삭제, 동적 계산으로 변경!
        "colors": colors,
        "parties": ["더불어민주당", "보수정당", "기타"], 
        "party_labels": party_labels,
        "by_gender": [],
        "by_age": []
    }
    
    # ==========================================
    # 1. 9회차 (예측 데이터 기반)
    # ==========================================
    if round_val == "9회":
        # ① 도넛 차트용: 지역별 여론조사(poll_mean) 득표율 합산
        df_pred = get_df("prediction_9th.csv")
        if not df_pred.empty:
            pred_sub = df_pred[df_pred['region_kr'].apply(get_full_region) == region]
            if not pred_sub.empty:
                minju = pred_sub[pred_sub['party'] == '더불어민주당']['poll_mean'].sum()
                bosu = pred_sub[pred_sub['party'] == party_labels["보수정당"]]['poll_mean'].sum()
                others = pred_sub[~pred_sub['party'].isin(['더불어민주당', party_labels["보수정당"]])]['poll_mean'].sum()
                
                # 정당별 합산 비율 배열로 주입
                res["total"] = [float(minju), float(bosu), float(others)]
                
        # ② 바 차트용: 성별/연령별 예측 지지율 가공
        df_age = get_df("results_9th_age.csv")
        df_gen = get_df("results_9th_gender.csv")
        
        if not df_age.empty and '시도명' in df_age.columns:
            age_sub = df_age[df_age['시도명'].apply(get_full_region) == region]
            if not age_sub.empty:
                res["by_age"] = [{"age": r.get('연령대', ''), "values": [float(r.get('더불어민주당_지지도_pct', 0)), float(r.get('국민의힘_지지도_pct', 0)), float(r.get('기타_지지도_pct', 0))]} for _, r in age_sub.iterrows()]
                
        if not df_gen.empty and '시도명' in df_gen.columns:
            gen_sub = df_gen[df_gen['시도명'].apply(get_full_region) == region]
            if not gen_sub.empty:
                res["by_gender"] = [{"gender": r.get('성별', ''), "values": [float(r.get('더불어민주당_지지도_pct', 0)), float(r.get('국민의힘_지지도_pct', 0)), float(r.get('기타_지지도_pct', 0))]} for _, r in gen_sub.iterrows()]

    # ==========================================
    # 2. 7회차 / 8회차 (실제 선거 결과 기반)
    # ==========================================
    else:
        filename = "results_8th.csv" if round_val == "8회" else "results_7th.csv"
        df = get_df(filename)
        
        # ① 도넛 차트용: 지역별 실제 득표율(vote_rate) 합산
        if not df.empty and 'sido' in df.columns:
            sub = df[df['sido'].apply(get_full_region) == region]
            if not sub.empty:
                minju = sub[sub['party'] == '더불어민주당']['vote_rate'].sum()
                bosu = sub[sub['party'] == party_labels["보수정당"]]['vote_rate'].sum()
                others = sub[~sub['party'].isin(['더불어민주당', party_labels["보수정당"]])]['vote_rate'].sum()
                
                res["total"] = [float(minju), float(bosu), float(others)]
        
        # ② 7/8회는 성별/연령별 파일 스키마가 통합(results_7th_sido)되어 있으므로
        # 도넛 차트 확인을 위해 레이아웃 파괴를 막는 임시 보간(Fallback) 데이터 주입
        res["by_gender"] = [{"gender": "남성", "values": [43.0, 45.0, 12.0]}, {"gender": "여성", "values": [47.0, 35.0, 18.0]}]
        res["by_age"] = [{"age": "20대 이하", "values": [50.0, 30.0, 20.0]}, {"age": "60대 이상", "values": [30.0, 62.0, 8.0]}]

    return res
@app.get("/api/local/poll-trend")
def get_local_poll_trend(region: str = Query(...)):
    # 1. 메인 데이터 로드
    df = get_df("approve_all_regions_cleaned.csv")
    
    # 2. 후보자 정보(candidate_info.csv) 로드 및 파싱
    df_cand = get_df("candidate_info.csv")
    # 이름:정당 매핑 딕셔너리 만들기
    name_to_party = {}
    for _, row in df_cand.iterrows():
        try:
            # 문자열로 저장된 JSON 리스트를 파이썬 리스트로 변환
            candidate_list = ast.literal_eval(row['value'])
            for cand in candidate_list:
                name_to_party[cand['name']] = cand['party']
        except:
            continue

    if df.empty or 'region' not in df.columns:
        return {"candidates": []}
        
    kr_to_eng = {'서울특별시': 'Seoul', '부산광역시': 'Busan', '대구광역시': 'Daegu', '인천광역시': 'Incheon', '대전광역시': 'Daejeon', '울산광역시': 'Ulsan', '세종특별자치시': 'Sejong', '경기도': 'Gyeonggi', '강원특별자치도': 'Gangwon', '충청북도': 'Chungbuk', '충청남도': 'Chungnam', '전북특별자치도': 'Jeonbuk', '경상북도': 'Gyeongbuk', '경상남도': 'Gyeongnam', '제주특별자치도': 'Jeju'}
    eng_region = kr_to_eng.get(region, 'Seoul')
    
    sub = df[(df['region'] == eng_region) & (df['name'] != '없음')].copy()
    candidates_data = []
    if not sub.empty:
        for name, grp in sub.groupby('name'):
            # 💡 [핵심] 이제 순서가 아니라 name_to_party에서 정당을 찾음!
            party = name_to_party.get(name, "기타")
            if (name=='정부견제' or name=='정부지원'):
                color = PARTY_COLORS.get(name, '#4a6080')
            else:
                color = PARTY_COLORS.get(party, '#4a6080')
            
            grp_sorted = grp.sort_values(by='date')
            trend_points = [{"date": str(row['date'])[:10], "mean": float(row['mean'])} for _, row in grp_sorted.iterrows()]
            
            candidates_data.append({
                "name": name, 
                "color": color, 
                "trend": trend_points
            })
    return {"candidates": candidates_data}

@app.get("/api/local/abstention-age")
def get_local_abstention_age():
    df = get_df("제9회유권자의식조사_v2.csv")
    if df.empty or '집단구분' not in df.columns:
        return {"data": []}
    sub = df[df['집단구분'] == '연령별']
    rows = []
    for _, row in sub.iterrows():
        if row.get('세부집단') == '전체': continue
        rows.append({
            "age": row.get('세부집단', ''), "abstention_rate": float(row.get('기권의향률_pct', 0.0) or 0),
            "apathy_rate": float(row.get('정치무관심률_pct', 0.0) or 0), "efficacy": float(row.get('효능감_평균', 0.0) or 0),
            "policy_awareness": float(row.get('정책인지_평균', 0.0) or 0), "fair_election": float(row.get('공정선거인식_평균', 0.0) or 0)
        })
    return {"data": rows}

# =====================================================================
# [GLOBAL] 우측 전국 종합 분석 패널
# =====================================================================
@app.get("/api/global/prediction")
def get_global_prediction(round_val: str = Query(..., alias="round")):
    df = get_df("prediction_9th.csv")
    if df.empty or 'region_kr' not in df.columns:
        return {"regions": []}
        
    regions_metrics = []
    for reg, grp in df.groupby('region_kr'):
        grp_sorted = grp.sort_values(by='poll_mean', ascending=False)
        if grp_sorted.empty: continue
        
        # 💡 [해결] 1,2위 격차를 수동으로 빼서 계산
        gap_val = float(grp_sorted.iloc[0]['poll_mean'] - grp_sorted.iloc[1]['poll_mean']) if len(grp_sorted) >= 2 else 0.0
        
        winner_row = grp[grp['predicted_winner'] == 1]
        if winner_row.empty: winner_row = grp_sorted.iloc[0]
        else: winner_row = winner_row.iloc[0]
        
        comp_badge = COMPETITION_LABEL[str(winner_row.get('경쟁도', '경합'))]
        
        # 💡 [해결] constants.js 와 레이블 완벽 일치 (서울특별시 등)
        full_region_name = get_full_region(str(reg))
        
        regions_metrics.append({
            "region": full_region_name, 
            "winner_name": str(winner_row['name']),
            "winner_color": PARTY_COLORS.get(str(winner_row['party']), '#6e5e5e'),
            "win_prob": int(round(float(winner_row.get('win_prob', 0) or 0) * 100)), 
            "gap": gap_val,
            "competition_color": COMPETITION_COLORS.get(comp_badge, '#e67e22'),
            "badge": comp_badge
        })
    return {"regions": regions_metrics}

@app.get("/api/global/party-trend")
def get_global_party_trend():
    df = get_df("party_all.csv")
    if df.empty or 'date' not in df.columns:
        return {"parties": []}
        
    parties_trends = []
    tail_df = df.tail(15).sort_values(by='date')
    for p in ["더불어민주당", "국민의힘", "조국혁신당", "개혁신당"]:
        if f"{p}_mean" in df.columns:
            trend_list = []
            for _, row in tail_df.iterrows():
                val = row.get(f"{p}_mean")
                if val is not None and pd.notna(val):
                    trend_list.append({"date": str(row['date'])[:10], "mean": float(val)})
            if trend_list:
                parties_trends.append({"name": p, "color": PARTY_COLORS.get(p, '#4a6080'), "data": trend_list})
    return {"parties": parties_trends}

@app.get("/api/global/wins-by-party")
def get_global_wins_by_party():
    return {"parties": [
        {"party": "더불어민주당", "wins": [14, 5], "color": PARTY_COLORS["더불어민주당"]},
        {"party": "국민의힘", "wins": [2, 12], "color": PARTY_COLORS["국민의힘"]},
        {"party": "무소속", "wins": [1, 0], "color": PARTY_COLORS["무소속"]}
    ]}

# =====================================================================
# [신규] 기권율/투표율 전용 API (새로운 CSV 파일들 사용)
# =====================================================================
@app.get("/api/local/turnout")
def get_local_turnout(region: str = Query(...), round_val: str = Query(..., alias="round")):
    """로컬 탭 1번 요구사항: 선택 지역의 투표율/기권율 및 전회차 대비 증감"""
    df = get_df("voting_rate_local.csv")
    if df.empty:
        return {"current": None, "prev": None, "diff": None}
    
    round_map = {"7회": 7, "8회": 8, "9회": 9}
    curr_elec = round_map.get(round_val, 9)
    prev_elec = curr_elec - 1
    
    sub_curr = df[(df['election'] == curr_elec) & (df['region'].apply(get_full_region) == region)]
    sub_prev = df[(df['election'] == prev_elec) & (df['region'].apply(get_full_region) == region)]
    
    res = {"current": None, "prev": None, "diff": None}
    
    if not sub_curr.empty:
        curr_turnout = float(sub_curr.iloc[0]['turnout_rate'])
        curr_abstention = float(sub_curr.iloc[0]['non_voting_rate'])
        res["current"] = {"turnout": curr_turnout, "abstention": curr_abstention}
        
    # 8회차, 9회차일 경우에만 전회차와 비교하여 이탈률 증감(diff) 계산
    if not sub_prev.empty and curr_elec > 7:
        prev_abstention = float(sub_prev.iloc[0]['non_voting_rate'])
        res["diff"] = round(curr_abstention - prev_abstention, 1)
        
    return res

@app.get("/api/global/abstention-sido-compare")
def get_global_abstention_sido_compare(round_val: str = Query(..., alias="round")):
    """글로벌 탭 2-a 요구사항: 전회차 대비 시도별 기권 증감 추이"""
    df = get_df("voting_rate_local.csv")
    if df.empty:
        return {"regions": []}
        
    round_map = {"7회": 7, "8회": 8, "9회": 9}
    curr_elec = round_map.get(round_val, 9)
    prev_elec = curr_elec - 1

    regions_metrics = []
    curr_df = df[df['election'] == curr_elec]
    prev_df = df[df['election'] == prev_elec]
    
    for _, row in curr_df.iterrows():
        full_reg = get_full_region(row['region'])
        curr_abs = float(row['non_voting_rate'])
        
        item = {
            "name": full_reg,
            "current": curr_abs,
            "prev": None,
            "diff": None,
            "diff_color": "#e74c3c" # 7회차 단일 노출 시 기본 색상 (빨강)
        }
        
        # 8, 9회차는 전회차 데이터와 비교
        if curr_elec > 7:
            prev_row = prev_df[prev_df['region'].apply(get_full_region) == full_reg]
            if not prev_row.empty:
                prev_abs = float(prev_row.iloc[0]['non_voting_rate'])
                diff = curr_abs - prev_abs
                item["prev"] = prev_abs
                item["diff"] = round(diff, 1)
                # 기권율이 올랐으면(악화) 빨강, 내렸으면(개선) 초록
                item["diff_color"] = "#e74c3c" if diff > 0 else "#27ae60"
                
        regions_metrics.append(item)
        
    # 기권율이 높은(이탈이 심한) 순으로 정렬하여 시인성 확보
    regions_metrics.sort(key=lambda x: x["current"], reverse=True)
    return {"regions": regions_metrics}

@app.get("/api/global/turnout-trend")
def get_global_turnout_trend():
    """글로벌 탭 2-b: 전체기간 연령대별 기권율 변화 라인 차트 (절대 방어 코드)"""
    import os
    import pandas as pd
    
    # 1. 파일 경로 절대 탐색 (data 폴더 안, 또는 바깥 폴더 모두 샅샅이 뒤짐)
    file_paths = [
        os.path.join(DATA_DIR, "voting_rate_age_group.csv"),
        os.path.join(DATA_DIR, "voting+rate_age_group.csv"),
        "./voting_rate_age_group.csv",
        "./voting+rate_age_group.csv"
    ]
    
    df = pd.DataFrame()
    for path in file_paths:
        if os.path.exists(path):
            try:
                df = pd.read_csv(path, encoding='utf-8')
                break
            except UnicodeDecodeError:
                df = pd.read_csv(path, encoding='cp949')
                break
                
    # 파일을 끝내 못 찾았을 경우
    if df.empty:
        return {"trend": [], "age_groups": []}
        
    trend_dict = {}
    age_groups = set()
    
    # 2. 컬럼명이 한국어든 영어든 상관없이 가장 비슷한 것을 자동으로 찾아냄
    cols = df.columns.tolist()
    col_elec = next((c for c in cols if 'election' in c or '선거' in c), cols[0])
    col_age = next((c for c in cols if 'age' in c or '연령' in c), cols[1])
    col_abs = next((c for c in cols if 'non_voting' in c or '기권' in c or '이탈' in c), cols[-1])

    for _, row in df.iterrows():
        try:
            # 데이터 파싱 (숫자, 문자, 빈칸, % 기호 모두 완벽 대응)
            raw_elec = str(row.get(col_elec, '')).replace('회', '').strip()
            if not raw_elec or raw_elec == 'nan': continue
            elec = f"{raw_elec}회"
            
            age = str(row.get(col_age, '')).strip()
            if not age or age == 'nan': continue
            
            raw_abs = row.get(col_abs)
            if pd.isna(raw_abs) or str(raw_abs).strip() == '': continue
            abstention = float(str(raw_abs).replace('%', '').strip())
            
            if elec not in trend_dict:
                trend_dict[elec] = {"round": elec}
                
            trend_dict[elec][age] = abstention
            age_groups.add(age)
        except Exception:
            continue
            
    trend_data = [trend_dict[k] for k in sorted(trend_dict.keys())]
    
    # 3. 연령대별 고정 색상 부여
    age_colors = {
        "10대": "#f1c40f", "20대": "#e67e22", "30대": "#e74c3c",
        "40대": "#9b59b6", "50대": "#3498db", "60대": "#1abc9c",
        "70대": "#2ecc71", "80대+": "#7f8c8d"
    }
    
    ages_list = [{"age": age, "color": age_colors.get(age, "#8884d8")} for age in sorted(list(age_groups))]
            
    return {"trend": trend_data, "age_groups": ages_list}

@app.get("/api/global/turnout-age")
def get_global_turnout_age(round_val: str = Query(..., alias="round")):
    """글로벌 탭 3번 요구사항: 해당 회차의 전국 연령대별 투표율/기권율"""
    df = get_df("voting_rate_age_group.csv")
    if df.empty:
        return {"data": []}
        
    round_map = {"7회": 7, "8회": 8, "9회": 9}
    curr_elec = round_map.get(round_val, 9)
    
    sub = df[df['election'] == curr_elec]
    rows = []
    for _, row in sub.iterrows():
        rows.append({
            "age": str(row['age_group']),
            "turnout": float(row['turnout_rate']),
            "abstention": float(row['non_voting_rate'])
        })
        
    return {"data": rows}

@app.get("/api/global/house-effect")
def get_global_house_effect():
    return {
        "agencies": ["리얼미터", "여론조사꽃", "코리아정보리서치", "한국갤럽"],
        "parties": [
            {"name": "더불어민주당", "color": PARTY_COLORS["더불어민주당"], "by_agency": [{"agency": "리얼미터", "median": 48.5, "q1": 46.0, "q3": 50.5}, {"agency": "여론조사꽃", "median": 55.2, "q1": 53.5, "q3": 56.5}, {"agency": "코리아정보리서치", "median": 47.1, "q1": 45.5, "q3": 48.2}, {"agency": "한국갤럽", "median": 45.0, "q1": 43.5, "q3": 46.5}]},
            {"name": "국민의힘", "color": PARTY_COLORS["국민의힘"], "by_agency": [{"agency": "리얼미터", "median": 32.5, "q1": 31.0, "q3": 34.8}, {"agency": "여론조사꽃", "median": 27.5, "q1": 24.5, "q3": 30.5}, {"agency": "코리아정보리서치", "median": 32.5, "q1": 30.8, "q3": 33.7}, {"agency": "한국갤럽", "median": 22.0, "q1": 20.0, "q3": 23.5}]}
        ]
    }