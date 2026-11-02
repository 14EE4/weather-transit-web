"""
logging_utils.py - 전역 로깅 정책(LOGGING_POLICY.md) 준수를 위한 공통 유틸리티
- 민감정보(공공 API 키, 토큰, 인증 헤더) 자동 마스킹
- 안전한 예외 메시지 정제 및 표준 포맷팅
"""

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
    return s


def sanitize_exception(exc: Exception) -> str:
    """
    예외 객체의 문자열 표현에서 민감정보(URL 쿼리스트링 API 키 등)를 마스킹한 안전한 텍스트 반환
    """
    return mask_sensitive_text(str(exc))
