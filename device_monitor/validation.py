from __future__ import annotations

import math
from .errors import ConfigError, DataError

def number(value, minimum=None, maximum=None):
    try:
        result = float(value)
    except (ValueError, TypeError, OverflowError):
        raise DataError("Dữ liệu không phải số") from None
    if not math.isfinite(result) or (minimum is not None and result < minimum) or (
        maximum is not None and result > maximum
    ):
        raise DataError("Giá trị nằm ngoài phạm vi hợp lệ")
    return result


def env_number(env, name, default, minimum, maximum):
    try:
        return number(env.get(name, default), minimum, maximum)
    except DataError:
        raise ConfigError(f"{name}: cần số trong khoảng {minimum}–{maximum}") from None


def env_bool(env, name, default=True):
    value = str(env.get(name, str(default))).lower()
    if value not in {"true", "false"}:
        raise ConfigError(f"{name}: chỉ nhận true hoặc false")
    return value == "true"
