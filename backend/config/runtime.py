"""运行时设备偏好持久化（设置页可改、改完立即生效、无需重启的配置）。

目前仅一项：force_cpu —— 反推（ONNX tagger）是否强制走 CPU。
持久化到 data/device_pref.json；文件缺失/损坏/无该键均默认 False
（= 维持自动探测 GPU 的现状）。
"""
from __future__ import annotations

import json

from backend.config import settings

_DEVICE_PREF_PATH = settings.DATA_DIR / "device_pref.json"


def get_force_cpu() -> bool:
    """读取 force_cpu 偏好。文件缺失/损坏/无键 → False（自动探测 GPU）。"""
    try:
        data = json.loads(_DEVICE_PREF_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    return bool(data.get("force_cpu", False))


def set_force_cpu(value: bool) -> None:
    """写入 force_cpu 偏好。"""
    _DEVICE_PREF_PATH.parent.mkdir(parents=True, exist_ok=True)
    _DEVICE_PREF_PATH.write_text(
        json.dumps({"force_cpu": bool(value)}), encoding="utf-8"
    )
