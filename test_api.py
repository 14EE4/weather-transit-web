import sys
import os
import requests
import json
import urllib.parse
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from dotenv import load_dotenv

# 윈도우 콘솔 한글/유니코드 출력 인코딩 설정
if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ==========================================
# 1. API 키 설정 (.env 파일에서 환경변수 로드)
# ==========================================
# 현재 폴더 또는 상위 폴더의 .env 파일을 자동으로 찾아 로드합니다.
load_dotenv()

KMA_AUTH_KEY = os.getenv("KMA_APIHUB_KEY")
SEOUL_SUBWAY_KEY = os.getenv("SEOUL_SUBWAY_API_KEY")
DATA_GO_KR_BUS_KEY = os.getenv("DATA_GO_KR_API_KEY")

# 키 로드 여부 검증 (누락 시 경고)
missing_keys = []
if not KMA_AUTH_KEY: missing_keys.append("KMA_APIHUB_KEY")
if not SEOUL_SUBWAY_KEY: missing_keys.append("SEOUL_SUBWAY_API_KEY")
if not DATA_GO_KR_BUS_KEY: missing_keys.append("DATA_GO_KR_API_KEY")

if missing_keys:
    print(f"[경고] .env 파일에서 다음 API 키를 찾을 수 없습니다: {', '.join(missing_keys)}")




# ==========================================
# 2. 기상청 초단기실황 (현재 날씨) 테스트
#    (참조: api_example/단기예보조회서비스_API활용가이드_260623.docx)
# ==========================================
def test_kma_weather(nx=61, ny=125):
    """
    기상청 API허브 초단기실황(getUltraSrtNcst) 조회
    - 가이드 명세: 발표시각은 매시 정각(정시단위), 매시각 10분 이후 호출 가능
    - 매시 10분 이전이면 1시간 전 정시 데이터로 자동 보정
    """
    print("\n" + "="*50)
    print("[1] 기상청 실시간 날씨 API 테스트 (초단기실황)")
    print("="*50)
    
    now = datetime.now()
    # 가이드 기준: 매시 10분 이후 호출 가능 (안정적인 조회를 위해 10분 기준)
    if now.minute < 10:
        target_time = now - timedelta(hours=1)
    else:
        target_time = now
        
    base_date = target_time.strftime("%Y%m%d")
    base_time = target_time.strftime("%H00")

    url = "https://apihub.kma.go.kr/api/typ02/openApi/VilageFcstInfoService_2.0/getUltraSrtNcst"
    params = {
        "authKey": KMA_AUTH_KEY,
        "pageNo": "1",
        "numOfRows": "10",
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
            try:
                err_data = res.json()
                msg = err_data.get("result", {}).get("message") or err_data.get("message") or res.text
                print(f"[안내] API 응답 메시지: {msg}")
                if res.status_code == 403:
                    print(">> [해결 방법] 기상청 API허브(https://apihub.kma.go.kr)에서 '동네예보조회서비스' 활용신청을 완료해주세요.")
            except Exception:
                print(f"[안내] {res.text}")
            return
        
        data = res.json()
        header = data.get("response", {}).get("header", {})
        result_code = header.get("resultCode")
        if result_code not in ("0", "00"):
            print(f"[오류 응답] 코드: {result_code}, 메시지: {header.get('resultMsg')}")
            return

        items = data.get("response", {}).get("body", {}).get("items", {}).get("item", [])
        if not items:
            print(f"[응답 없음] 결과 데이터가 비어 있습니다. (헤더: {header})")
            return

        result = {}
        for item in items:
            cat = item.get("category")
            val = item.get("obsrValue")
            result[cat] = val

        pty_desc = {
            "0": "없음(맑음/흐림)", "1": "비", "2": "비/눈",
            "3": "눈", "5": "빗방울", "6": "빗방울눈날림", "7": "눈날림"
        }
        
        print(f"[성공] 기준 시각: {base_date} {base_time} (격자: nx={nx}, ny={ny})")
        print(f"- 기온(T1H): {result.get('T1H')} ℃")
        print(f"- 1시간 강수량(RN1): {result.get('RN1')} mm")
        print(f"- 강수 형태(PTY): {pty_desc.get(result.get('PTY'), '알수없음')} ({result.get('PTY')})")
        print(f"- 습도(REH): {result.get('REH')} %")
        print(f"- 풍속(WSD): {result.get('WSD')} m/s")

    except Exception as e:
        print(f"[오류 발생] {e}")


# ==========================================
# 3. 서울시 버스 도착 정보 테스트
# ==========================================
def test_seoul_bus(ars_id="23288"):
    """
    서울시 정류소 버스 도착 정보 조회
    (주의: ws.bus.go.kr은 공공데이터포털(data.go.kr) 인증키를 요구함)
    """
    print("\n" + "="*50)
    print(f"[2] 서울 버스 도착 정보 API 테스트 (정류소 번호: {ars_id})")
    print("="*50)

    url = f"http://ws.bus.go.kr/api/rest/arrive/getArrInfoByStnid?serviceKey={DATA_GO_KR_BUS_KEY}&arsId={ars_id}"

    try:
        res = requests.get(url, timeout=5)
        if res.status_code != 200:
            print(f"[실패] HTTP 상태 코드: {res.status_code}")
            try:
                err_data = res.json()
                msg = err_data.get("message") or err_data.get("error")
                if msg:
                    print(f"[안내] 버스 API 메시지: {msg}")
            except Exception:
                pass
            if res.status_code == 401:
                print(">> [참고] 공공데이터포털 API 키는 신청/발급 직후 게이트웨이 동기화에 1~2시간가량 소요될 수 있습니다.")
                print(">> [확인] 공공데이터포털(data.go.kr) 마이페이지에서 '서울특별시_버스도착정보조회' 서비스 활용신청 승인 여부를 확인해주세요.")
            return

        root = ET.fromstring(res.content)
        header_cd = root.findtext(".//headerCd")
        header_msg = root.findtext(".//headerMsg")
        if header_cd and header_cd != "0":
            print(f"[안내] 버스 API 메시지 ({header_cd}): {header_msg}")
            return

        items = root.findall(".//itemList")
        if not items:
            print("[결과 없음] 해당 정류소에 운행 중인 버스가 없거나 정류소 번호 오류입니다.")
            return

        congestion_map = {"3": "여유", "4": "보통", "5": "혼잡", "0": "정보없음"}
        for item in items[:5]:
            rt_nm = item.findtext("rtNm")
            arrmsg1 = item.findtext("arrmsg1")
            reride_num1 = item.findtext("reride_Num1", default="0")
            print(f"- [{rt_nm}번] 도착: {arrmsg1} | 첫 번째 차량 혼잡도: {congestion_map.get(reride_num1, reride_num1)}")

    except Exception as e:
        print(f"[오류 발생] {e}")


# ==========================================
# 4. 서울시 지하철 도착 정보 테스트
#    (참조: api_example/서울시+지하철+실시간+도착정보.xls)
# ==========================================
def test_seoul_subway(station_name="강남"):
    """
    서울시 지하철 실시간 도착 정보 조회
    - 가이드 명세:
      http://swopenAPI.seoul.go.kr/api/subway/{KEY}/{TYPE}/realtimeStationArrival/{START_INDEX}/{END_INDEX}/{statnNm}
      START_INDEX: 0, END_INDEX: 5
    - sample 키일 경우 '서울'역만 조회 가능
    """
    print("\n" + "="*50)
    print(f"[3] 서울 지하철 도착 정보 API 테스트 (역명: {station_name})")
    print("="*50)

    key = SEOUL_SUBWAY_KEY or "sample"
    encoded_station = urllib.parse.quote(station_name)
    url = f"http://swopenAPI.seoul.go.kr/api/subway/{key}/json/realtimeStationArrival/0/5/{encoded_station}"

    try:
        res = requests.get(url, timeout=5)
        if res.status_code != 200:
            print(f"[실패] HTTP 상태 코드: {res.status_code}")
            return

        data = res.json()
        err_meta = data.get("errorMessage") or data.get("RESULT") or {}
        code = str(data.get("code") or err_meta.get("code") or err_meta.get("CODE") or "")
        msg = data.get("message") or err_meta.get("message") or err_meta.get("MESSAGE")

        # 오류 응답 처리 (예: ERROR-338 해당 키로는 실시간 서비스를 이용할 수 없습니다)
        if code and code != "INFO-000":
            print(f"[API 응답] 코드: {code} | 내용: {msg}")
            if code == "ERROR-338":
                print(">> [원인] 서울 열린데이터광장(data.seoul.go.kr)에서 '서울시 지하철 실시간 도착정보' 서비스 활용신청이 필요합니다.")
            
            # 가이드에 안내된 sample 키('서울'역)로 자동 시연
            print("\n[가이드 예제 테스트] 'sample' 인증키로 '서울'역 데이터 조회를 시연합니다...")
            sample_url = f"http://swopenAPI.seoul.go.kr/api/subway/sample/json/realtimeStationArrival/0/5/{urllib.parse.quote('서울')}"
            s_res = requests.get(sample_url, timeout=5)
            if s_res.status_code == 200:
                s_data = s_res.json()
                s_arrivals = s_data.get("realtimeArrivalList", [])
                print(f"[성공] sample 키 조회 결과 (서울역 도착 예정 {len(s_arrivals)}건 중 상위 3건):")
                for arr in s_arrivals[:3]:
                    train_line = arr.get("trainLineNm")
                    msg2 = arr.get("arvlMsg2")
                    barvl_dt = arr.get("barvlDt", "0")
                    status = arr.get("btrainSttus") or "일반"
                    print(f"- [{train_line}] ({status}) 현황: {msg2} (예정: {barvl_dt}초)")
            return

        arrivals = data.get("realtimeArrivalList", [])
        if not arrivals:
            print(f"[결과 없음] 운행 중인 열차가 없거나 역명을 확인해주세요. (응답: {msg or '정상'})")
            return

        print(f"[성공] '{station_name}'역 실시간 도착 정보 ({len(arrivals)}건):")
        for arr in arrivals:
            train_line = arr.get("trainLineNm")
            msg2 = arr.get("arvlMsg2")
            barvl_dt = arr.get("barvlDt", "0")
            status = arr.get("btrainSttus") or "일반"
            print(f"- [{train_line}] ({status}) 현황: {msg2} (예정: {barvl_dt}초)")

    except Exception as e:
        print(f"[오류 발생] {e}")


# ==========================================
# 실행
# ==========================================
if __name__ == "__main__":
    test_kma_weather()
    test_seoul_bus()
    test_seoul_subway()