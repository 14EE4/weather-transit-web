"""
logging_utils.py - 전역 로깅 정책(LOGGING_POLICY.md) 준수를 위한 공통 유틸리티
- 민감정보(공공 API 키, 토큰, 인증 헤더) 자동 마스킹
- 안전한 예외 메시지 정제 및 표준 포맷팅
"""

import logging
import re
from typing import Any, Optional


# 민감 파라미터 키 패턴: serviceKey, authKey, apiKey, token, secret 등
_SENSITIVE_KEY_REGEX = re.compile(
    r'((?:serviceKey|auth_?key|api_?key|token|secret|access_?token|client_?secret)[=:\s]+["\']?)'
    r'([A-Za-z0-9%_\-\.\+=]{4})([A-Za-z0-9%_\-\.\+=]+)',
    re.IGNORECASE
)

# Bearer 토큰 패턴
_BEARER_REGEX = re.compile(
    r'(Bearer\s+)([A-Za-z0-9_\-\.]{4})([A-Za-z0-9_\-\.]+)',
    re.IGNORECASE
)

# 서울 열린데이터광장 지하철 URL 경로 내 API 키 패턴: /api/subway/{KEY}/
_SEOUL_SUBWAY_PATH_KEY_REGEX = re.compile(
    r'(swopenapi\.seoul\.go\.kr/api/subway/)([A-Za-z0-9%_\-]{4})([A-Za-z0-9%_\-]+)(/)',
    re.IGNORECASE
)

# 서울 열린데이터광장 따릉이 등 포트 8088 URL 경로 내 API 키 패턴: :8088/{KEY}/json|xml/
_SEOUL_OPENAPI_PATH_KEY_REGEX = re.compile(
    r'(openapi\.seoul\.go\.kr:\d+/)([A-Za-z0-9%_\-]{4})([A-Za-z0-9%_\-]+)(/(?:json|xml)/)',
    re.IGNORECASE
)


def mask_sensitive_text(text: Any) -> str:
    """
    문자열(URL, 예외 메시지, 페이로드) 내의 API 키나 토큰 등 민감정보를 마스킹합니다.
    앞 4자리는 디버깅 식별용으로 보존하고 나머지는 ****로 치환합니다.
    예:
        serviceKey=184d553816a7f8e4... -> serviceKey=184d****
        Bearer sk-1234abcd5678... -> Bearer sk-1****
    """
    if text is None:
        return ""
    s = str(text)
    # 1. 일반 쿼리스트링 및 키-값 파라미터 마스킹
    s = _SENSITIVE_KEY_REGEX.sub(r'\1\2****', s)
    # 2. Bearer 인증 토큰 마스킹
    s = _BEARER_REGEX.sub(r'\1\2****', s)
    # 3. 서울 열린데이터광장 URL 경로(Path) 내 API 키 마스킹
    s = _SEOUL_SUBWAY_PATH_KEY_REGEX.sub(r'\1\2****\4', s)
    s = _SEOUL_OPENAPI_PATH_KEY_REGEX.sub(r'\1\2****\4', s)
    return s


def sanitize_exception(exc: Optional[Exception]) -> str:
    """
    예외 객체의 문자열 표현에서 민감정보(URL 쿼리스트링 API 키 등)를 마스킹한 안전한 텍스트 반환.
    `httpx.ReadTimeout("")` 처럼 str(exc)가 빈 문자열인 경우에도 예외 클래스명(`ReadTimeout` 등)이 남도록 보강합니다.
    """
    if exc is None:
        return ""
    cls_name = type(exc).__name__
    raw_msg = str(exc).strip()
    if not raw_msg:
        return cls_name
    masked = mask_sensitive_text(raw_msg)
    return masked if cls_name in masked else f"{cls_name}: {masked}"


class SensitiveInfoMaskingFilter(logging.Filter):
    """콘솔/파일 등 핸들러 출력 직전에 로그 메시지 내 API 키·토큰을 마스킹합니다."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
            masked = mask_sensitive_text(rendered)
            if masked != rendered:
                record.msg = masked
                record.args = ()
        except Exception:
            pass
        return True


def install_root_log_masking() -> None:
    """루트 로거의 모든 핸들러(콘솔 StreamHandler 포함)에 민감정보 마스킹 필터를 1회 등록합니다."""
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if not any(isinstance(f, SensitiveInfoMaskingFilter) for f in handler.filters):
            handler.addFilter(SensitiveInfoMaskingFilter())
