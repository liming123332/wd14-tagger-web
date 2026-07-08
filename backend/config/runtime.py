"""运行时设备偏好与启动校验（设置页可改、改完立即生效或重启生效的配置）。

- force_cpu：反推（ONNX tagger）是否强制走 CPU，改完立即生效，无需重启。
  持久化到 data/device_pref.json；文件缺失/损坏/无该键均默认 False。
- ensure_data_dir_writable：数据目录可写性校验，启动自检与设置页保存前共用。
"""
from __future__ import annotations

import json
from pathlib import Path

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


def ensure_data_dir_writable(path: Path | None = None) -> None:
    """确认数据目录存在且可写。

    path 默认 settings.DATA_DIR（启动自检用）；设置页保存前可传候选路径校验。
    通过即返回；失败抛 OSError，由调用方决定包装成启动报错或 HTTP 400。
    """
    d = path or settings.DATA_DIR
    d.mkdir(parents=True, exist_ok=True)
    probe = d / ".writetest"
    probe.write_bytes(b"")
    probe.unlink()
