import requests
import json
import urllib.parse
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET

import os
from dotenv import load_dotenv

# ==========================================
# 1. API 키 설정 (.env 파일에서 환경변수 로드)
# ==========================================
# 현재 폴더 또는 상위 폴더의 .env 파일을 자동으로 찾아 로드합니다.
load_dotenv()

KMA_AUTH_KEY = os.getenv("KMA_APIHUB_KEY")
SEOUL_API_KEY = os.getenv("SEOUL_OPEN_KEY")

# 키 로드 여부 검증 (누락 시 경고)
if not KMA_AUTH_KEY or not SEOUL_API_KEY:
    print("[경고] .env 파일에서 API 키를 찾을 수 없습니다. 키 설정을 확인해주세요.")



# ==========================================
# 2. 기상청 초단기실황 (현재 날씨) 테스트
# ==========================================
def test_kma_weather(nx=61, ny=125):
    """
    기상청 API허브 초단기실황 조회 (강남 기준 nx=61, ny=125)
    매시 40분 이전이면 1시간 전 정시 데이터로 자동 보정
    """
    print("\n" + "="*50)
    print("[1] 기상청 실시간 날씨 API 테스트")
    print("="*50)
    
    now = datetime.now()
    # 40분 이전이면 1시간 전 데이터 기준
    if now.minute < 40:
        target_time = now - timedelta(hours=1)
    else:
        target_time = now
        
    base_date = target_time.strftime("%Y%m%d")
    base_time = target_time.strftime("%H00")

    url = "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtNcst"
    params = {
        "authKey": KMA_AUTH_KEY,
        "pageNo": "1",
        "numOfRows": "100",
        "dataType": "JSON",
        "base_date": base_date,
        "base_time": base_time,
        "nx": nx,
        "ny": ny
    }

    try:
        res = requests.get(url, params=params, timeout=5)
        if res.status_code != 200:
            print(f"[실패] HTTP 상태 코드: {res.status_code}")
            return
        
        data = res.json()
        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        
        if not items:
            print("[응답 없음] 결과 데이터가 비어 있습니다. (결과 메시지:", data.get("response", {}).get("header", {}), ")")
            return

        result = {}
        for item in items:
            cat = item.get("category")
            val = item.get("obsrValue")
            result[cat] = val

        pty_desc = {"0": "없음(맑음/흐림)", "1": "비", "2": "비/눈", "3": "눈", "5": "빗방울", "6": "빗방울눈날림", "7": "눈날림"}
        
        print(f"기준 시각: {base_date} {base_time}")
        print(f"• 기온(T1H): {result.get('T1H')} ℃")
        print(f"• 1시간 강수량(RN1): {result.get('RN1')} mm")
        print(f"• 강수 형태(PTY): {pty_desc.get(result.get('PTY'), '알수없음')} ({result.get('PTY')})")
        print(f"• 습도(REH): {result.get('REH')} %")
        print(f"• 풍속(WSD): {result.get('WSD')} m/s")

    except Exception as e:
        print(f"[오류 발생] {e}")


# ==========================================
# 3. 서울시 버스 도착 정보 테스트
# ==========================================
def test_seoul_bus(ars_id="23288"):
    """
    서울시 정류소 버스 도착 정보 조회
    기본값 '23288' -> 강남역 정류소(가상/실제 ARS-ID)
    """
    print("\n" + "="*50)
    print(f"[2] 서울 버스 도착 정보 API 테스트 (정류소 번호: {ars_id})")
    print("="*50)

    url = f"http://ws.bus.go.kr/api/rest/arrive/getArrInfoByStnid?serviceKey={SEOUL_API_KEY}&arsId={ars_id}"

    try:
        res = requests.get(url, timeout=5)
        if res.status_code != 200:
            print(f"[실패] HTTP 상태 코드: {res.status_code}")
            return

        root = ET.fromstring(res.content)
        items = root.findall(".//itemList")
        
        if not items:
            print("[결과 없음] 해당 정류소에 운행 중인 버스가 없거나 정류소 번호 오류입니다.")
            return

        congestion_map = {"3": "여유", "4": "보통", "5": "혼잡", "0": "정보없음"}

        for item in items[:5]:  # 상위 5개 노선만 출력
            rt_nm = item.findtext("rtNm")           # 버스 번호
            arrmsg1 = item.findtext("arrmsg1")       # 첫 번째 도착 메시지
            reride_num1 = item.findtext("reride_Num1", default="0") # 혼잡도
            
            print(f"• [{rt_nm}번] 도착: {arrmsg1} | 첫 번째 차량 혼잡도: {congestion_map.get(reride_num1, reride_num1)}")

    except Exception as e:
        print(f"[오류 발생] {e}")


# ==========================================
# 4. 서울시 지하철 도착 정보 테스트
# ==========================================
def test_seoul_subway(station_name="강남"):
    """
    서울시 지하철 실시간 도착 정보 조회
    """
    print("\n" + "="*50)
    print(f"[3] 서울 지하철 도착 정보 API 테스트 (역명: {station_name})")
    print("="*50)

    encoded_station = urllib.parse.quote(station_name)
    url = f"http://swopenAPI.seoul.go.kr/api/subway/{SEOUL_API_KEY}/json/realtimeStationArrival/1/5/{encoded_station}"

    try:
        res = requests.get(url, timeout=5)
        if res.status_code != 200:
            print(f"[실패] HTTP 상태 코드: {res.status_code}")
            return

        data = res.json()
        arrivals = data.get("realtimeArrivalList", [])
        
        if not arrivals:
            print("[결과 없음] 운행 중인 열차가 없거나 역명을 확인해주세요.")
            return

        for arr in arrivals:
            train_line = arr.get("trainLineNm")  # 방면
            msg = arr.get("arvlMsg2")            # 전역 도착, 2분 후 등
            barvl_dt = arr.get("barvlDt")        # 남은 초
            print(f"• [{train_line}] 현황: {msg} (남은 시간: {barvl_dt}초)")

    except Exception as e:
        print(f"[오류 발생] {e}")


# ==========================================
# 실행
# ==========================================
if __name__ == "__main__":
    # 라이브러리 설치 필요 시 터미널에서: pip install requests
    test_kma_weather()
    test_seoul_bus()
    test_seoul_subway()