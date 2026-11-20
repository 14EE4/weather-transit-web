import os
import tempfile
import unittest
from datetime import datetime

from fastapi.testclient import TestClient

import admin_dashboard
import main
import point_share_inference
from kma_forecast import DISTRICT_GRID_MAP
from scripts import export_point_share_serving_bundle
from timeseries_cache import TimeseriesCacheManager


class TestSolidPhase1(unittest.TestCase):
    def test_timeseries_cache_stats_and_clear_with_temp_db(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
            db_path = os.path.join(tmpdir, "test_ts.db")
            mgr = TimeseriesCacheManager(db_path=db_path)
            now = datetime.now()
            mgr.record_weather("강남구", 20.0, 0.0, 50.0, 2.0, dt=now)
            mgr.record_demand("강남구", 100.0, 200.0, 300.0, dt=now)
            mgr._db_queue.join()

            stats = mgr.get_cache_stats()
            self.assertTrue(stats["exists"])
            self.assertNotIn("error", stats)
            self.assertEqual(stats["weather_count"], 1)
            self.assertEqual(stats["transit_count"], 1)
            self.assertEqual(stats["count"], 2)

            cleared = mgr.clear_cache()
            self.assertTrue(cleared["cleared_sqlite"])
            self.assertEqual(cleared["weather_deleted"], 1)
            self.assertEqual(cleared["transit_deleted"], 1)

            stats_after = mgr.get_cache_stats()
            self.assertEqual(stats_after["count"], 0)

    def test_admin_dashboard_and_status_delegation(self):
        stats = admin_dashboard.get_cache_stats()
        self.assertNotIn("error", stats)

        client = TestClient(main.app)
        resp = client.get("/api/v1/admin/status")
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("cache_stats", body)
        self.assertNotIn("error", body["cache_stats"])

    def test_kma_grid_ssot_in_main(self):
        self.assertFalse(hasattr(main, "DISTRICT_KMA_GRID"))
        dist, nx, ny = main.resolve_weather_target("강남구")
        self.assertEqual(dist, "강남구")
        self.assertEqual((nx, ny), DISTRICT_GRID_MAP["강남구"])

        dist_sn, sn_nx, sn_ny = main.resolve_weather_target("성남시")
        self.assertEqual(dist_sn, "성남시")
        self.assertEqual((sn_nx, sn_ny), DISTRICT_GRID_MAP["성남시"])

        dist_ca, ca_nx, ca_ny = main.resolve_weather_target("천안시 두정·천안역·쌍용")
        self.assertEqual(dist_ca, "천안시")
        self.assertEqual((ca_nx, ca_ny), DISTRICT_GRID_MAP["천안시"])

        dist_yc, yc_nx, yc_ny = main.resolve_weather_target("연천군 연천·전곡")
        self.assertEqual(dist_yc, "연천군")
        self.assertEqual((yc_nx, yc_ny), DISTRICT_GRID_MAP["연천군"])

    def test_normalization_ssot_with_export_script(self):
        self.assertIs(
            export_point_share_serving_bundle.normalize_subway_name,
            point_share_inference.normalize_subway_name,
        )
        self.assertIs(
            export_point_share_serving_bundle.normalize_bike_name,
            point_share_inference.normalize_bike_name,
        )


if __name__ == "__main__":
    unittest.main()
