import os
import json
import requests
from urllib.parse import unquote
from dotenv import load_dotenv

# 프로젝트 루트의 .env 파일 불러오기
load_dotenv()

API_KEY = os.getenv("DATA_GO_KR_API_KEY")

BASE_URL = (
    "http://ws.bus.go.kr/api/rest/"
    "stationinfo/getStationByName"
)


def search_bus_station(keyword):
    if not API_KEY:
        print("오류: 버스 API 인증키가 없어.")
        return

    params = {
        "serviceKey": unquote(API_KEY),
        "stSrch": keyword,
        "resultType": "json"
    }

    try:
        response = requests.get(
            BASE_URL,
            params=params,
            timeout=10
        )
        response.raise_for_status()

        data = response.json()

        header = data.get("msgHeader", {})
        code = str(header.get("headerCd", ""))

        if code != "0":
            print("API 응답 오류:", header)
            return

        body = data.get("msgBody") or {}
        stations = body.get("itemList") or []

        if isinstance(stations, dict):
            stations = [stations]

        results = []

        for station in stations:
            results.append({
                "name": station.get("stNm"),
                "stId": station.get("stId"),
                "arsId": station.get("arsId"),
                "longitude": station.get("tmX"),
                "latitude": station.get("tmY")
            })

        print(f"\n검색어: {keyword}")
        print(f"조회된 정류장: {len(results)}개\n")

        print(json.dumps(
            results[:10],
            ensure_ascii=False,
            indent=2
        ))

    except requests.RequestException as e:
        print("HTTP 요청 실패:", e)

    except ValueError:
        print("JSON 응답 해석 실패")
        print(response.text[:500])


if __name__ == "__main__":
    keyword = input("검색할 버스정류장 이름: ").strip()

    if keyword:
        search_bus_station(keyword)
    else:
        print("검색어를 입력해 줘.")