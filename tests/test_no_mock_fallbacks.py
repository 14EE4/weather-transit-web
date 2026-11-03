"""
[이슈 #97] 목업·폴백 데이터 재유입 방지 가드 테스트

프론트엔드 소스(`Weather-Transport Recommendation UI/src`)를 정적 검사하여
① 실시간 API 미수신 시 허위 수치(가짜 도착시간·운행 상태 문구)를 생성하는 패턴,
② 폴백 상수(`FALLBACK_*`, `DEFAULT_24H_DATA`)를 출처 표기 없이 렌더링하는 패턴
이 다시 유입되지 않도록 차단합니다.
"""

import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "Weather-Transport Recommendation UI" / "src"

# 실시간 데이터 미수신 시 사용자에게 허위 수치를 노출하던 과거 패턴 (이슈 #97에서 제거)
FORBIDDEN_PATTERNS = [
    # 지하철/버스 도착 정보를 임의로 조작하던 리터럴
    ("remaining_minutes: 2", "가짜 도착 시간(2분) 생성 금지"),
    ("message: '배차 간격 2~5분 정상 운행'", "가짜 운행 상태 메시지 생성 금지"),
    ("message: '정상 운행중'", "가짜 운행 상태 메시지 생성 금지"),
    ("arrival_msg1: '배차간격 유지 운행중'", "가짜 버스 도착 카드 생성 금지"),
    # 데이터 부재 시 하드코딩으로 정상 운행을 단정하던 문구
    ("배차 간격 2~5분 정상 운행중", "하드코딩 운행 상태 표출 금지"),
    ("배차 간격 유지 정상 운행중", "하드코딩 운행 상태 표출 금지"),
    # 데모·시연용으로 고정된 정류소/노선 ID (실제 선택 거점 기준 조회로 대체)
    ("stId=111000299", "데모 정류소 ID 하드코딩 금지"),
    ("'100100118'", "데모 버스 노선 ID 하드코딩 금지"),
]


def iter_source_files():
    """프론트엔드 소스(.ts/.tsx) 파일 목록 (중복 제거)"""
    return sorted({p for pattern in ("*.ts", "*.tsx", "**/*.ts", "**/*.tsx") for p in SRC_DIR.glob(pattern)})


def read_source(name: str) -> str:
    return (SRC_DIR / name).read_text(encoding="utf-8")


class TestNoMockFallbacks(unittest.TestCase):
    def test_source_dir_exists(self):
        self.assertTrue(SRC_DIR.is_dir(), f"프론트엔드 소스 디렉터리를 찾을 수 없습니다: {SRC_DIR}")

    def test_no_fabricated_arrival_or_status_literals(self):
        """허위 도착시간·운행 상태 문구가 코드에 재유입되지 않아야 한다."""
        violations = []
        for path in iter_source_files():
            text = path.read_text(encoding="utf-8")
            for pattern, reason in FORBIDDEN_PATTERNS:
                if pattern in text:
                    violations.append(f"{path.name}: '{pattern}' ({reason})")
        self.assertEqual(
            violations,
            [],
            "실시간 데이터 미수신 시 허위 수치를 생성하는 패턴이 발견되었습니다:\n" + "\n".join(violations),
        )

    def test_empty_state_message_used_on_arrival_failure(self):
        """지하철·버스 도착 조회 실패 시 빈 상태 안내 문구를 사용해야 한다."""
        transit_map = read_source("TransitMap.tsx")
        self.assertIn(
            "실시간 열차 도착 정보를 불러오지 못했습니다",
            transit_map,
            "지하철 도착 조회 실패 시 빈 상태 안내가 필요합니다.",
        )
        self.assertIn(
            "실시간 버스 도착 정보를 불러오지 못했습니다",
            transit_map,
            "버스 도착 조회 실패 시 빈 상태 안내가 필요합니다.",
        )

    def test_client_no_data_source_is_used(self):
        """클라이언트 폴백은 '데이터 없음' 출처 코드로 구분되어야 한다."""
        transit_map = read_source("TransitMap.tsx")
        self.assertIn("CLIENT_NO_DATA", transit_map, "실시간 미수신 출처 코드(CLIENT_NO_DATA)가 필요합니다.")
        self.assertNotIn(
            "NO_STID_FALLBACK",
            transit_map,
            "정류소 ID 부재 시에도 CLIENT_NO_DATA로 통일해야 합니다.",
        )

    def test_fallback_sources_are_labeled_in_ui(self):
        """폴백·추정 데이터는 UI에서 출처(추정) 배지로 명시되어야 한다."""
        for name in ("App.tsx", "AppM.tsx"):
            text = read_source(name)
            self.assertIn("⚠️ 기본값(추정)", text, f"{name}: AI 추론 폴백 배지 누락")
            self.assertIn("⚠️ 추정", text, f"{name}: 혼잡도 추정 배지 누락")
            self.assertIn("⚠️ 시계열 기본값(추정)", text, f"{name}: 24시간 시계열 폴백 배지 누락")
        self.assertIn(
            "⚠️ 시간표 추정",
            read_source("TransitMap.tsx"),
            "TransitMap.tsx: 도착 정보 추정 배지 누락",
        )

    def test_no_placeholder_route_values(self):
        """[P2] 경로를 찾지 못했을 때 임의의 소요시간·요금 대체값을 표시하지 않아야 한다."""
        for name in ("App.tsx", "AppM.tsx"):
            text = read_source(name)
            self.assertNotIn(": '25분'", text, f"{name}: 임의 소요시간('25분') 대체값이 남아 있습니다.")
            self.assertNotIn(": '1,550원'", text, f"{name}: 임의 요금('1,550원') 대체값이 남아 있습니다.")

    def test_seed_coverage_is_disclosed(self):
        """[P2] 정적 시드 마커 커버리지(부분집합)를 UI에서 고지해야 한다."""
        for name in ("App.tsx", "AppM.tsx"):
            text = read_source(name)
            self.assertIn("BUS_STOPS.length", text, f"{name}: 버스 시드 개수 고지 누락")
            self.assertIn("BIKE_STATIONS.length", text, f"{name}: 따릉이 시드 개수 고지 누락")

    def test_fallback_module_is_documented(self):
        """폴백 상수 모듈은 폴백 전용임이 문서화되어 있어야 한다."""
        header = "\n".join(read_source("constants/fallbackData.ts").splitlines()[:8])
        self.assertIn("폴백", header, "fallbackData.ts 상단에 폴백 전용 설명이 필요합니다.")


if __name__ == "__main__":
    unittest.main()