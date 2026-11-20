"""
공공 API 서킷 브레이커 (Circuit Breaker) 및 장애 대비 복원력 계층
"""

import logging
import time

logger = logging.getLogger("weather_transit_api.circuit_breaker")


class CircuitBreaker:
    """
    공공 API 장애 및 지연 전파 차단용 3상 서킷 브레이커 (CLOSED -> OPEN -> HALF_OPEN)
    - failure_threshold: 연속 실패 횟수 임계치 (초과 시 OPEN 전환)
    - recovery_timeout: OPEN 상태 지속 시간(초) 후 HALF_OPEN 프로빙 시도
    """

    def __init__(self, name: str, failure_threshold: int = 3, recovery_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = 0.0
        self.last_state_change = time.time()
        self.success_count = 0
        self.fallback_count = 0

    def can_execute(self) -> bool:
        now = time.time()
        if self.state == "OPEN":
            if now - self.last_failure_time >= self.recovery_timeout:
                self.state = "HALF_OPEN"
                self.last_state_change = now
                logger.info(
                    f"[CircuitBreaker:{self.name}] 쿨다운 만료 -> HALF_OPEN (프로빙 시험 요청 허용)"
                )
                return True
            return False
        return True

    def record_success(self) -> None:
        if self.state in ("OPEN", "HALF_OPEN"):
            logger.info(f"[CircuitBreaker:{self.name}] 원격 API 정상 복구 확인 -> CLOSED 전환")
        self.failure_count = 0
        self.state = "CLOSED"
        self.success_count += 1
        self.last_state_change = time.time()

    def record_failure(self, error_msg: str = "") -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.fallback_count += 1
        reason = (error_msg or "").strip() or "원인 미상"
        if self.state == "HALF_OPEN" or self.failure_count >= self.failure_threshold:
            if self.state != "OPEN":
                logger.warning(
                    f"[CircuitBreaker:{self.name}] 연속 실패 {self.failure_count}회 발생! "
                    f"서킷을 OPEN 상태로 차단합니다 (쿨다운: {self.recovery_timeout}초). 원인: {reason}"
                )
            self.state = "OPEN"
            self.last_state_change = time.time()

    def get_status(self) -> dict:
        now = time.time()
        remaining_cooldown = (
            max(0.0, self.recovery_timeout - (now - self.last_failure_time))
            if self.state == "OPEN"
            else 0.0
        )
        return {
            "name": self.name,
            "state": self.state,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_sec": self.recovery_timeout,
            "remaining_cooldown_sec": round(remaining_cooldown, 1),
            "total_success": self.success_count,
            "total_fallback": self.fallback_count,
        }
