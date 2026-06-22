from __future__ import annotations
from pathlib import Path
import time
import urllib.request

from backend.tagger.models_spec import ModelSpec

# 模型下载的公共逻辑 + 进度状态。
#
# 三个 tagger 类（OnnxTagger / CLTagger / CLTaggerV2）的 _download 原本各自重复一份
# urlopen + shutil.copyfileobj 的静默拷贝——大文件（如 cl_tagger_v2 的 2.2GB 权重）
# 下载时控制台和页面都没任何反馈。这里统一抽出：分块读取、控制台 print 进度、
# 并维护模块级 _state 供前端轮询 GET /api/taggers/download-progress。
#
# 单任务模型：同时只有一个下载在进行（前端按钮互斥），故一份全局状态够用。

_state: dict = {
    "active": False,      # 是否正在下载
    "key": "",            # 模型 key
    "file": "",           # 当前文件名
    "index": 0,           # 当前第几个文件（0-based）
    "total_files": 0,     # 待下载文件总数
    "downloaded": 0,      # 当前文件已下载字节
    "size": 0,            # 当前文件总字节（无 Content-Length 时为 0）
    "done": False,        # 全部完成
    "error": "",          # 失败原因
}

_LOG_INTERVAL = 0.5  # 控制台进度日志最小间隔（秒），避免大文件刷屏


def get_state() -> dict:
    return dict(_state)


def _human(n: int) -> str:
    """字节 → 可读（B/KB/MB/GB）。"""
    f = float(n)
    for unit in ("B", "KB", "MB", "GB"):
        if f < 1024:
            return f"{int(f)}B" if unit == "B" else f"{f:.1f}{unit}"
        f /= 1024
    return f"{f:.1f}TB"


def download_files(spec: ModelSpec, model_dir: Path, key: str) -> None:
    """逐文件下载 spec.files 到 model_dir：skip 已有、.part 原子写、Content-Length 校验。

    下载时分块（1MB）读取，每 0.5s 向 stdout 打印一行进度（后端控制台可见），
    同时更新模块级 _state（前端轮询可见）。任一文件失败：删 .part、记 error、向上抛。"""
    model_dir.mkdir(parents=True, exist_ok=True)
    files = list(spec.files.items())
    _state.update(active=True, key=key, total_files=len(files), done=False, error="",
                  index=0, file="", downloaded=0, size=0)
    print(f"[下载] {key}: 开始，共 {len(files)} 个文件 -> {model_dir}", flush=True)
    try:
        for idx, (name, url) in enumerate(files):
            _state.update(index=idx, file=name, downloaded=0, size=0)
            dst = model_dir / name
            if dst.exists():
                print(f"[下载] {key}: {name} 已存在，跳过", flush=True)
                continue
            tmp = dst.with_suffix(dst.suffix + ".part")
            print(f"[下载] {key}: 下载 {name}（{idx + 1}/{len(files)}）", flush=True)
            try:
                with urllib.request.urlopen(url) as resp:
                    expected = resp.headers.get("Content-Length")
                    total = int(expected) if expected and str(expected).isdigit() else 0
                    _state["size"] = total
                    downloaded = 0
                    start = time.time()
                    last_log = 0.0
                    with tmp.open("wb") as f:
                        while True:
                            chunk = resp.read(1024 * 1024)  # 1MB
                            if not chunk:
                                break
                            f.write(chunk)
                            downloaded += len(chunk)
                            _state["downloaded"] = downloaded
                            now = time.time()
                            if now - last_log >= _LOG_INTERVAL:
                                last_log = now
                                elapsed = now - start
                                speed = (downloaded / elapsed / (1024 * 1024)) if elapsed > 0 else 0.0
                                if total:
                                    pct = downloaded * 100 / total
                                    print(f"[下载]   {name}: {_human(downloaded)}/{_human(total)} "
                                          f"({pct:.1f}%, {speed:.1f} MB/s)", flush=True)
                                else:
                                    print(f"[下载]   {name}: {_human(downloaded)} ({speed:.1f} MB/s)", flush=True)
                if expected is not None and str(tmp.stat().st_size) != expected:
                    raise IOError(f"{name} 下载不完整：期望 {expected}，实际 {tmp.stat().st_size}")
                tmp.replace(dst)
                print(f"[下载] {key}: 完成 {name}", flush=True)
            except BaseException as e:
                # gated 模型（如 cl_tagger_v2）会在这里抛 HTTPError 401/403——打印原因，
                # 前端也会收到 download failed: <原因> 的错误提示。
                print(f"[下载] {key}: 失败 {name}: {e}", flush=True)
                tmp.unlink(missing_ok=True)
                raise
        _state.update(active=False, done=True, downloaded=0, size=0)
        print(f"[下载] {key}: 全部完成", flush=True)
    except BaseException as e:
        _state.update(active=False, done=False, error=str(e))
        raise
