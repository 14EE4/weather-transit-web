"""
in_memory_log_handler.py - 서버 실시간 로그를 인메모리 링 버퍼에 안전하게 캡처하는 로깅 핸들러
관리자 모니터링 대시보드(/health/dashboard)에서 실시간으로 스트리밍 조회할 수 있도록 지원합니다.
"""

import logging
import threading
from collections import deque
from datetime import datetime
from typing import Any, Dict, List, Optional


class InMemoryLogHandler(logging.Handler):
    """
    최신 로그를 최대 maxlen건까지 메모리에 보관하는 스레드 안전 링 버퍼 로그 핸들러
    (주의: logging.Handler 기본 self.lock과의 충돌 데드락을 방지하기 위해 RLock 사용)
    """
    def __init__(self, maxlen: int = 2000):
        super().__init__()
        self.buffer: deque = deque(maxlen=maxlen)
        self._buf_lock = threading.RLock()
        self._seq = 0
        self._last_entry_signature: Optional[tuple] = None

    def emit(self, record: logging.LogRecord):
        try:
            msg = self.format(record)
            now = datetime.fromtimestamp(record.created)
            time_str = now.strftime("%H:%M:%S")
            timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")

            # 도메인 태그 자동 감지
            domain = self._detect_domain(record.name, msg)

            with self._buf_lock:
                # 동일 타임스탬프, 동일 로거, 동일 메시지 중복 emit 방지
                sig = (timestamp_str, record.name, msg)
                if self._last_entry_signature == sig:
                    return
                self._last_entry_signature = sig

                self._seq += 1
                entry = {
                    "id": self._seq,
                    "timestamp": timestamp_str,
                    "time": time_str,
                    "level": record.levelname,
                    "logger": record.name,
                    "message": msg,
                    "domain": domain,
                }
                self.buffer.append(entry)
        except Exception:
            self.handleError(record)

    def _detect_domain(self, logger_name: str, msg: str) -> str:
        """메시지 및 로거 이름 기반 도메인 태그 분류"""
        if "기상청" in msg or "weather" in msg.lower() or "kma" in msg.lower():
            return "기상청"
        elif "지하철" in msg or "subway" in msg.lower() or "열차" in msg:
            return "지하철"
        elif "버스" in msg or "bus" in msg.lower() or "정류" in msg:
            return "버스"
        elif "따릉이" in msg or "bike" in msg.lower() or "대여소" in msg:
            return "따릉이"
        elif "LangGraph" in msg or "멀티모달" in msg or "multimodal" in msg.lower():
            return "LangGraph"
        elif "ONNX" in msg or "머신러닝" in msg or "AI" in msg or "추론" in msg:
            return "AI추론"
        elif "CircuitBreaker" in msg or "서킷" in msg:
            return "서킷브레이커"
        elif "cache" in msg.lower() or "캐시" in msg:
            return "캐시"
        elif "uvicorn" in logger_name.lower():
            return "HTTP"
        return "시스템"

    def get_logs(
        self,
        since_id: Optional[int] = None,
        level: Optional[str] = None,
        domain: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """메모리에 저장된 최근 로그 목록 필터링 조회"""
        with self._buf_lock:
            items = list(self.buffer)

        # since_id 필터 (이후 발생한 새 로그만 조회할 때)
        if since_id is not None:
            items = [item for item in items if item["id"] > since_id]

        # 레벨 필터 (INFO, WARNING, ERROR 등)
        if level and level.upper() != "ALL":
            target_level = level.upper()
            if target_level == "WARN":
                target_level = "WARNING"
            items = [item for item in items if item["level"] == target_level]

        # 도메인 필터
        if domain and domain != "전체":
            items = [item for item in items if item["domain"] == domain]

        # 키워드 검색
        if query:
            q_lower = query.lower()
            items = [item for item in items if q_lower in item["message"].lower() or q_lower in item["logger"].lower()]

        # 최신 순이거나 limit 개수만큼 반환
        if len(items) > limit:
            items = items[-limit:]

        return items

    def clear(self):
        """버퍼 초기화"""
        with self._buf_lock:
            self.buffer.clear()
            self._last_entry_signature = None

    def get_stats(self) -> Dict[str, Any]:
        """로그 통계 집계"""
        with self._buf_lock:
            total = len(self.buffer)
            counts = {"INFO": 0, "WARNING": 0, "ERROR": 0, "DEBUG": 0}
            domains: Dict[str, int] = {}
            for item in self.buffer:
                lvl = item["level"]
                counts[lvl] = counts.get(lvl, 0) + 1
                dom = item["domain"]
                domains[dom] = domains.get(dom, 0) + 1

        return {
            "total_logs": total,
            "counts": counts,
            "domains": domains,
            "latest_seq": self._seq,
        }


# 전역 싱글톤 인스턴스
in_memory_log_handler = InMemoryLogHandler(maxlen=2000)
_formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%H:%M:%S")
in_memory_log_handler.setFormatter(_formatter)
in_memory_log_handler.setLevel(logging.INFO)


def attach_in_memory_log_handler():
    """
    애플리케이션 로거들에 인메모리 핸들러 연결.
    루트 로거에만 핸들러를 등록하고 자식 로거는 propagate=True로 전파시켜
    동일 로그가 중복 수집되는 것을 방지합니다.
    """
    root_logger = logging.getLogger()
    if in_memory_log_handler not in root_logger.handlers:
        root_logger.addHandler(in_memory_log_handler)

    # uvicorn 로거들은 프레임워크 설정상 propagate가 꺼져있을 수 있으므로
    # 루트 로거로 로그가 자연스럽게 올라오도록 propagate=True를 보장합니다.
    for name in ["uvicorn", "uvicorn.access", "uvicorn.error", "weather_transit_api", "multimodal_router", "timeseries_cache"]:
        lg = logging.getLogger(name)
        lg.propagate = True
        # 혹시 기존에 개별 로거에 핸들러가 등록되어 있다면 제거하여 중복 차단
        if in_memory_log_handler in lg.handlers:
            lg.removeHandler(in_memory_log_handler)
