import unittest
from fastapi.testclient import TestClient

import main
from multimodal_router import format_duration_kr, multimodal_routing_engine


class TestMultimodalRoutingEngine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        main.registry.load_models()
        cls.client = TestClient(main.app)

    def test_clear_weather_enables_bike_first_mile(self):
        """맑은 날(rain=0.0) 호출 시 Weather Gate가 CLEAR_MULTIMODAL로 분기하고 따릉이 복합 후보 생성 및 합리적 효용 정렬을 수행해야 함"""
        res = multimodal_routing_engine.run_multimodal_search(
            from_query="강남역",
            to_query="서울역",
            district="강남구",
            hour=14,
            weather_context={"temp": 18.5, "rain": 0.0, "humidity": 50.0, "wind": 2.0},
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["weather_gate"], "CLEAR_MULTIMODAL")
        self.assertTrue(res["weather_context"]["bike_enabled"])
        self.assertGreaterEqual(len(res["routes"]), 3)
        top_route = res["routes"][0]
        self.assertTrue(top_route["is_ai_recommended"])
        self.assertTrue(any("bike" in r["modes_used"] for r in res["routes"]))
        self.assertEqual(len(res["langgraph_trace"]), 4)

        # 서울역 -> 홍대입구역처럼 공항철도 무환승 직통(7분, 1,550원)이 따릉이 복합(19분, 2,550원)보다 압도적으로 유리한 경우 직통 지하철이 1순위로 선정되어야 함
        seoul_hongdae = multimodal_routing_engine.run_multimodal_search(
            from_query="서울역",
            to_query="홍대입구역",
            district="용산구",
            hour=15,
            weather_context={"temp": 5.7, "rain": 0.0, "humidity": 40.0, "wind": 2.0},
        )
        self.assertEqual(seoul_hongdae["routes"][0]["id"], "route-subway-optimal")
        self.assertTrue(seoul_hongdae["routes"][0]["is_ai_recommended"])

        # 단거리(강남역 -> 역삼역) 맑은 날에는 따릉이 논스톱 에코 라이딩이 1순위로 선정되어야 함
        short_trip = multimodal_routing_engine.run_multimodal_search(
            from_query="강남역",
            to_query="역삼역",
            district="강남구",
            hour=14,
            weather_context={"temp": 18.5, "rain": 0.0, "humidity": 50.0, "wind": 2.0},
        )
        self.assertEqual(short_trip["routes"][0]["id"], "route-ai-bike-direct")
        self.assertTrue(short_trip["routes"][0]["is_ai_recommended"])

    def test_rainy_weather_blocks_bike_via_weather_gate(self):
        """우천 시(rain=10.5mm) Weather Gate가 RAIN_SAFE_ONLY로 분기하여 따릉이(PM) 후보를 자동 배제해야 함"""
        res = multimodal_routing_engine.run_multimodal_search(
            from_query="강남역",
            to_query="서울역",
            district="강남구",
            hour=18,
            weather_context={"temp": 13.0, "rain": 10.5, "humidity": 85.0, "wind": 4.5},
        )
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["weather_gate"], "RAIN_SAFE_ONLY")
        self.assertFalse(res["weather_context"]["bike_enabled"])
        for route in res["routes"]:
            self.assertNotIn("bike", route["modes_used"])
        summary = res["ai_briefing"]["summary"]
        self.assertTrue(
            any(kw in summary for kw in ("강수", "비", "우천", "따릉이", "지하철")),
            f"Unexpected briefing summary: {summary}",
        )

    def test_fastapi_post_and_get_multimodal_endpoints(self):
        """FastAPI POST 및 GET /api/v1/routes/multimodal-search 엔드포인트 스키마 및 32D ONNX 연동 검증"""
        post_resp = self.client.post(
            "/api/v1/routes/multimodal-search",
            json={
                "from_station": "홍대입구역",
                "to_station": "여의도역",
                "district": "마포구",
                "hour": 9,
                "weather": {"temp": 17.0, "rain": 0.0, "humidity": 55.0, "wind": 2.0},
            },
        )
        self.assertEqual(post_resp.status_code, 200)
        data = post_resp.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["origin"]["name"], "홍대입구역")
        self.assertEqual(data["destination"]["name"], "여의도역")
        self.assertIn("ai_briefing", data)
        self.assertIn("routes", data)
        self.assertGreater(len(data["routes"]), 0)

        get_resp = self.client.get(
            "/api/v1/routes/multimodal-search?from_station=잠실역&to_station=건대입구역&district=송파구&hour=19&rain=8.0&temp=14.0"
        )
        self.assertEqual(get_resp.status_code, 200)
        g_data = get_resp.json()
        self.assertEqual(g_data["weather_gate"], "RAIN_SAFE_ONLY")
        self.assertFalse(g_data["weather_context"]["bike_enabled"])

    def test_no_origin_backtracking_in_first_mile(self):
        """서울역 등 환승 거점에서 출발 시 따릉이 First-Mile 이후 지하철이 다시 출발역(서울역)으로 되돌아오는 제자리걸음이 없어야 함"""
        for dest in ["강남역", "홍대입구역", "여의도역", "구로역"]:
            res = multimodal_routing_engine.run_multimodal_search(
                from_query="서울역",
                to_query=dest,
                district="용산구",
                hour=9,
                weather_context={"temp": 18.0, "rain": 0.0, "humidity": 50.0, "wind": 1.5},
            )
            for route in res["routes"]:
                if "bike" in route["modes_used"] and "subway" in route["modes_used"]:
                    subway_segs = [s for s in route["segments"] if s["mode"] == "subway"]
                    for seg in subway_segs:
                        self.assertNotEqual(
                            seg["to_name"],
                            "서울역",
                            f"Backtracking to 서울역 detected in {route['title']} -> {seg}",
                        )
                        self.assertNotEqual(
                            seg["from_name"],
                            "서울역",
                            f"Circular return to 서울역 detected in {route['title']} -> {seg}",
                        )

    def test_non_seoul_origin_excludes_bike_and_no_distant_jump(self):
        """서울 외 지역(예: 송내역, 부평역, 수원역) 출발 시 따릉이(서울시 전용)가 자동 배제되고 원거리 점프 직선이 없어야 함"""
        for origin_q, dest_q in [("송내역", "중동역"), ("부평역", "홍대입구역"), ("수원역", "강남역")]:
            res = multimodal_routing_engine.run_multimodal_search(
                from_query=origin_q,
                to_query=dest_q,
                district="구로구",
                hour=15,
                weather_context={"temp": 18.0, "rain": 0.0, "humidity": 45.0, "wind": 1.8},
            )
            self.assertEqual(res["status"], "success")
            self.assertFalse(res["weather_context"]["origin_in_seoul"])
            self.assertFalse(res["weather_context"]["bike_enabled"])
            for r in res["routes"]:
                self.assertNotIn("bike", r["modes_used"])
                for seg in r["segments"]:
                    self.assertNotIn("서울식물원", seg.get("to_name", ""))
                    self.assertNotIn("서울식물원", seg.get("from_name", ""))

    def test_verified_travel_times_and_headway_consistency(self):
        """역간 실거리·노선별 주행속도 기반 이동시간, 실시간/시간대별 배차간격, 총 소요시간=구간 합계 정합성 검증"""
        # 1) 송내역 -> 중동역 (1호선 1개 역 이동: 약 2분)
        songnae_res = multimodal_routing_engine.run_multimodal_search(
            from_query="송내역",
            to_query="중동역",
            district="구로구",
            hour=14,
            weather_context={"temp": 18.0, "rain": 0.0, "humidity": 45.0, "wind": 1.8},
        )
        sub_opt = next(r for r in songnae_res["routes"] if r["id"] == "route-subway-optimal")
        self.assertEqual(sub_opt["stationCount"], 1)
        self.assertIn(sub_opt["total_minutes"], (2, 3))
        self.assertEqual(sub_opt["total_minutes"], sum(int(s["minutes"]) for s in sub_opt["segments"]))

        # 2) 서울역 -> 홍대입구역 (공항철도 2개 역 이동: 약 7분 + 실시간 도착정보 주입 검증)
        live_arrs = [
            {
                "line": "공항철도",
                "destination": "인천공항2터미널행 - 공덕방면",
                "message": "3분 후 (서울출발)",
                "remaining_minutes": 3,
                "remaining_seconds": 180,
            }
        ]
        seoul_hongdae = multimodal_routing_engine.run_multimodal_search(
            from_query="서울역",
            to_query="홍대입구역",
            district="용산구",
            hour=8,
            weather_context={"temp": 15.0, "rain": 0.0, "humidity": 50.0, "wind": 2.0},
            live_subway_arrivals=live_arrs,
        )
        sh_top = seoul_hongdae["routes"][0]
        self.assertEqual(sh_top["id"], "route-subway-optimal")
        self.assertEqual(sh_top["stationCount"], 2)
        self.assertIn(sh_top["total_minutes"], (6, 7, 8))
        self.assertTrue(sh_top["departureTrain"]["isLive"])
        self.assertEqual(sh_top["departureTrain"]["remainingMinutes"], 3)
        self.assertIn("실시간 3분 후 도착", sh_top["segments"][0]["live_badge"])
        for r in seoul_hongdae["routes"]:
            self.assertEqual(r["total_minutes"], sum(int(s["minutes"]) for s in r["segments"]))

    def test_station_verified_transfer_times(self):
        """서울교통공사 마스터 데이터 연동 주요 환승역 실측 도보시간 및 환승 세그먼트 정밀 계산 검증 (Issue #27)"""
        # 1) 개별 환승역 조회 확인
        seoul_info = multimodal_routing_engine.get_station_transfer_info("서울역", "1호선", "공항철도")
        self.assertEqual(seoul_info["walk_minutes"], 4.3)
        self.assertEqual(seoul_info["distance_m"], 309)

        nowon_info = multimodal_routing_engine.get_station_transfer_info("노원역", "4호선", "7호선")
        self.assertEqual(nowon_info["walk_minutes"], 3.9)
        self.assertEqual(nowon_info["distance_m"], 278)

        geumjeong_info = multimodal_routing_engine.get_station_transfer_info("금정역", "1호선", "4호선")
        self.assertEqual(geumjeong_info["walk_minutes"], 0.5)
        self.assertEqual(geumjeong_info["distance_m"], 30)

        # 2) 환승 경로 생성 시 실측 도보시간이 세그먼트에 반영되는지 검증 (상계역 -> 마들역: 노원역 4호선 ➔ 7호선 환승)
        res = multimodal_routing_engine.search_subway_route("상계역", "마들역", mode="min_transfer", hour=14)
        self.assertIsNotNone(res)
        self.assertEqual(res["transferCount"], 1)
        self.assertIn("노원역", res["transferStations"])
        walk_segs = [s for s in res["lineSegments"] if s["mode"] == "walk"]
        self.assertTrue(len(walk_segs) > 0)
        tr_walk_seg = walk_segs[0]
        self.assertEqual(tr_walk_seg["walk_minutes"], 3.9)
        self.assertEqual(tr_walk_seg["transfer_distance_m"], 278)
        self.assertIn("3.9분", tr_walk_seg["detail"])

    def test_subway_express_train_detection(self):
        """9호선 급행 등 수도권 급행열차 정차역 스킵 및 소요시간 단축 모델링 검증 (Issue #27)"""
        # 김포공항역 -> 신논현역 (9호선 급행 주요 구간: 다수의 일반역 통과)
        res = multimodal_routing_engine.search_subway_route("김포공항역", "신논현역", mode="min_transfer", hour=14)
        self.assertIsNotNone(res)
        sub_segs = [s for s in res["lineSegments"] if s["mode"] == "subway"]
        self.assertTrue(len(sub_segs) > 0)
        express_seg = sub_segs[0]
        self.assertTrue(express_seg.get("is_express"))
        self.assertIn("(급행)", express_seg["label"])
        self.assertGreaterEqual(express_seg["skipped_stops"], 5)
        self.assertGreater(express_seg["time_saved_minutes"], 5)
        self.assertIn("단축", express_seg["detail"])

    def test_live_bus_arrivals_injection_in_multimodal(self):
        """실시간 버스 도착 API 데이터 주입 시 버스-지하철 하이브리드 경로에 실시간 뱃지 연동 검증 (Issue #27)"""
        live_buses = [
            {
                "route_name": "143",
                "station_name": "강남역환승정류소",
                "arrival_msg1": "3분후[1번째 전]",
                "arrival_msg2": "8분후[4번째 전]",
                "bus_route_id": "100100022",
            }
        ]
        res = multimodal_routing_engine.run_multimodal_search(
            from_query="강남역",
            to_query="시청역",
            district="강남구",
            hour=14,
            weather_context={"temp": 18.0, "rain": 0.0, "humidity": 50.0, "wind": 2.0},
            live_bus_arrivals=live_buses,
        )
        hybrid_route = next((r for r in res["routes"] if r["id"] == "route-bus-subway-hybrid"), None)
        self.assertIsNotNone(hybrid_route)
        bus_segs = [s for s in hybrid_route["segments"] if s["mode"] == "bus"]
        self.assertTrue(len(bus_segs) > 0)
        bus_seg = bus_segs[0]
        self.assertIn("실시간", bus_seg["live_badge"])
        self.assertIn("3분후", bus_seg["live_badge"])

    def test_duration_formatting_and_candidate_payload(self):
        """소요시간 포맷팅(60분 미만 -> X분, 60분 이상 -> X시간 Y분) 및 경로 후보 formatted_duration 필드 검증 (Issue #27)"""
        # 단위 포맷팅 함수 검증
        self.assertEqual(format_duration_kr(0), "0분")
        self.assertEqual(format_duration_kr(45), "45분")
        self.assertEqual(format_duration_kr(59), "59분")
        self.assertEqual(format_duration_kr(60), "1시간")
        self.assertEqual(format_duration_kr(75), "1시간 15분")
        self.assertEqual(format_duration_kr(120), "2시간")
        self.assertEqual(format_duration_kr(135), "2시간 15분")

        # 멀티모달 검색 시 각 후보 경로의 summary 및 formatted_duration 필드 검증
        res = multimodal_routing_engine.run_multimodal_search(
            from_query="강남역",
            to_query="서울역",
            district="강남구",
            hour=14,
            weather_context={"temp": 18.0, "rain": 0.0, "humidity": 50.0, "wind": 2.0},
        )
        self.assertGreaterEqual(len(res["routes"]), 1)
        for r in res["routes"]:
            self.assertIn("formatted_duration", r)
            self.assertIn("분", r["formatted_duration"])
            self.assertIn(r["formatted_duration"], r["summary"])

    def test_guro_branch_and_line1_branch_topology(self):
        """구로역 분기(경인선↔경부선), 1호선 지선(광명셔틀·서동탄지선) 및 2/5/경의중앙선 분기역 환승 규칙 검증"""
        # 1. 구로역 토폴로지: 가산디지털단지역, 구일역, 신도림역 3방향 모두 연결되어야 함
        guro_nbrs = multimodal_routing_engine.subway_graph.get("구로역", [])
        self.assertEqual(sorted(guro_nbrs), ["가산디지털단지역", "구일역", "신도림역"])

        # 2. 구로역 -> 가산디지털단지역 (1호선 경부선 직통 1정거장, 무환승)
        guro_gasan = multimodal_routing_engine.search_subway_route("구로역", "가산디지털단지역")
        self.assertIsNotNone(guro_gasan)
        self.assertEqual(guro_gasan["transferCount"], 0)
        self.assertEqual(guro_gasan["stationCount"], 1)

        # 3. 구일역(경인선) -> 가산디지털단지역(경부선): 구로역 1회 필수 환승 (1호선(경인) ➔ 1호선(경부))
        guil_gasan = multimodal_routing_engine.search_subway_route("구일역", "가산디지털단지역")
        self.assertIsNotNone(guil_gasan)
        self.assertEqual(guil_gasan["transferCount"], 1)
        self.assertEqual(guil_gasan["transferStations"], ["구로역"])
        seg_labels = [s["label"] for s in guil_gasan["lineSegments"]]
        self.assertIn("🚇 1호선(경인)", seg_labels)
        self.assertIn("🚇 1호선(경부)", seg_labels)

        # 4. 1호선 광명셔틀 지선: 광명역은 금천구청역에만 연결되어야 하며, 광명역 -> 석수역은 금천구청역 1회 환승
        self.assertEqual(multimodal_routing_engine.subway_graph.get("광명역"), ["금천구청역"])
        gm_seoksu = multimodal_routing_engine.search_subway_route("광명역", "석수역")
        self.assertIsNotNone(gm_seoksu)
        self.assertEqual(gm_seoksu["transferCount"], 1)
        self.assertEqual(gm_seoksu["transferStations"], ["금천구청역"])

        # 5. 1호선 서동탄지선: 서동탄역은 병점역에만 연결되어야 하며, 서동탄역 -> 세마역은 병점역 1회 환승
        self.assertEqual(multimodal_routing_engine.subway_graph.get("서동탄역"), ["병점역"])
        sdt_sema = multimodal_routing_engine.search_subway_route("서동탄역", "세마역")
        self.assertIsNotNone(sdt_sema)
        self.assertEqual(sdt_sema["transferCount"], 1)
        self.assertEqual(sdt_sema["transferStations"], ["병점역"])

        # 6. 5호선 강동역 분기(길동역 <-> 둔촌동역) 및 2호선 성수지선/신정지선 분기 환승 검증
        gd_dunchon = multimodal_routing_engine.search_subway_route("길동역", "둔촌동역")
        self.assertEqual(gd_dunchon["transferCount"], 1)
        self.assertEqual(gd_dunchon["transferStations"], ["강동역"])

        yd_ttukseom = multimodal_routing_engine.search_subway_route("용답역", "뚝섬역")
        self.assertEqual(yd_ttukseom["transferCount"], 1)
        self.assertEqual(yd_ttukseom["transferStations"], ["성수역"])

        drc_mullae = multimodal_routing_engine.search_subway_route("도림천역", "문래역")
        self.assertEqual(drc_mullae["transferCount"], 1)
        self.assertEqual(drc_mullae["transferStations"], ["신도림역"])



    def test_hybrid_bus_subway_route_and_bus_polyline_corridor(self):
        """이슈 #34: 버스+지하철 복합 환승 경로의 compat_path 정합성 및 버스 도로 복도 폴리라인 검증"""
        res = multimodal_routing_engine.run_multimodal_search(
            from_query="송내역",
            to_query="두정역",
            district="강남구",
            hour=23,
            weather_context={"temp": 4.5, "rain": 0.0},
        )
        hybrid_routes = [r for r in res.get("routes", []) if r.get("id") == "route-bus-subway-hybrid"]
        self.assertTrue(len(hybrid_routes) > 0, "route-bus-subway-hybrid 경로가 생성되어야 함")
        hybrid = hybrid_routes[0]

        # 1. 환승역 검증: 지하철 직결 경로의 구로역 환승이 제거되고 금천구청역 환승만 존재해야 함
        self.assertEqual(hybrid.get("transferStations"), ["금천구청역"])
        self.assertNotIn("구로역", hybrid.get("transferStations", []))

        # 2. 환승 열차 정보 검증: 구로역이 아닌 금천구청역 출발 열차가 바인딩되어야 함
        tr_trains = hybrid.get("transferTrains") or []
        self.assertTrue(len(tr_trains) > 0)
        self.assertEqual(tr_trains[0].get("station"), "금천구청역")

        # 3. compat_path 정합성 검증: 1호선 북부 중복 역들(중동, 부천, 온수, 구로 등)이 제거되어야 함
        path_names = [p["name"] for p in hybrid.get("path", [])]
        self.assertIn("송내역", path_names)
        self.assertIn("금천구청역", path_names)
        self.assertIn("두정역", path_names)
        self.assertNotIn("중동역", path_names)
        self.assertNotIn("부천역", path_names)
        self.assertNotIn("구로역", path_names)
        self.assertNotIn("가산디지털단지역", path_names)

        # 4. 버스 세그먼트 좌표 검증: 단순 2점 직선이 아닌 15개 이상의 도로 복도(Corridor) 좌표열이어야 함
        bus_segs = [s for s in hybrid.get("segments", []) if s.get("mode") == "bus"]
        self.assertTrue(len(bus_segs) > 0)
        bus_coords = bus_segs[0].get("coords", [])
        self.assertGreaterEqual(len(bus_coords), 15, "버스 경로는 도로형 복도 좌표열(15개 이상)로 생성되어야 함")

        # 5. 전체 지오메트리 연결성 검증
        geom = hybrid.get("geometry", [])
        self.assertGreaterEqual(len(geom), 30)
        self.assertEqual(geom[0], hybrid["path"][0]["coords"])
        self.assertEqual(geom[-1], hybrid["path"][-1]["coords"])

    def test_bus_subway_transfer_api_endpoint(self):
        """서울시 실시간 대중교통환승경로 API 연동 엔드포인트(/api/v1/transit/bus/transfer-path) 검증 (Issue #50)"""
        # 1) 유효 좌표 조회 (홍대입구역 ➔ 강남역)
        resp = self.client.get(
            "/api/v1/transit/bus/transfer-path?startX=126.9240&startY=37.5568&endX=127.0276&endY=37.4979"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "success")
        self.assertIn("routes", data)
        self.assertGreater(data["count"], 0)
        first_rt = data["routes"][0]
        self.assertIn("total_minutes", first_rt)
        self.assertIn("legs", first_rt)
        self.assertGreater(len(first_rt["legs"]), 0)

        # 2) 잘못된 좌표 유효성 검증 (범위 밖 좌표)
        err_resp = self.client.get(
            "/api/v1/transit/bus/transfer-path?startX=10.0&startY=37.5&endX=127.0&endY=37.5"
        )
        self.assertEqual(err_resp.status_code, 400)

if __name__ == "__main__":
    unittest.main()

