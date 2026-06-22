# -*- coding: utf-8 -*-
"""首次启动检测 GPU 架构，按需切换 llama-cpp-python 翻译推理库 wheel。

整合包默认预装 Blackwell（RTX 50 / sm_120）的翻译推理库；RTX 40（Ada / sm_89）
等其他架构由本脚本在启动时自动切换到匹配 wheel，避免 ggml-cuda.dll 无对应内核
导致 0xC000001D（STATUS_ILLEGAL_INSTRUCTION）崩溃、/api/translate 500。

由 启动.bat 在 uvicorn 启动前调用：此时是独立子进程、尚未 import llama_cpp，
pip 可安全覆盖 wheel（ggml-cuda.dll 未被任何进程持有）。

每次启动轻量检测：nvidia-smi 查 compute capability（~300ms）+ 读已装版本（~1ms）；
已匹配则秒过，不匹配才 pip install。无 N 卡 / 未知架构 / 无匹配 wheel 时打印提示后
正常退出，绝不阻断主服务启动。无状态文件——天然应对换卡或手动改 wheel。
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Windows GBK 控制台兜底：强制 UTF-8 输出（与 fetch_anima.py 同款）
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# 路径（适配任意安装位置：本脚本在 wd14-tagger-web/scripts/，wheel 在 wd14-tagger-web/_llama_wheels/）
SCRIPT_DIR = Path(__file__).resolve().parent
WEB_ROOT = SCRIPT_DIR.parent                  # wd14-tagger-web/
WHEELS_DIR = WEB_ROOT / "_llama_wheels"       # 打包时 wheel 拷到这里（_dl 在 EXCLUDE_DIRS 不进包）

# nvidia-smi 返回的 compute capability -> 架构名。
# Blackwell 桌面/工作站是 sm_120（cc=12.0），数据中心 B 系列是 sm_100（cc=10.0），都映射 blackwell。
# Ada=RTX40, Ampere=RTX30, Turing=RTX20/GTX16。
CC_TO_ARCH = {
    "12.0": "blackwell",
    "10.0": "blackwell",
    "8.9": "ada",
    "8.6": "ampere",
    "7.5": "turing",
}

# wheel 文件名关键词（arch -> 必须全部出现在文件名小写形式里）
# blackwell: ...sm100.sm120.blackwell...；ada: ...sm89.ada...；ampere: ...sm86.ampere...；turing: ...sm75.turing...
ARCH_KEYWORDS = {
    "blackwell": ["blackwell"],
    "ada": ["sm89", "ada"],
    "ampere": ["sm86", "ampere"],
    "turing": ["sm75", "turing"],
}


def get_gpu_cc() -> str | None:
    """nvidia-smi 查第一张卡的 compute capability，返回 "8.9" 等；失败/无 N 卡返回 None。"""
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=10,
        )
        if r.returncode != 0 or not r.stdout.strip():
            return None
        line = r.stdout.strip().splitlines()[0].strip()  # 多卡取第一张
        return line.split(",")[0].strip()
    except Exception:
        return None


def get_installed_arch() -> str | None:
    """读已装 llama_cpp_python 的架构名。

    这些 wheel 的 METADATA Version 字段被规范化成 "0.3.20"（不含 local tag），arch 信息
    （sm89.ada / sm100.sm120.blackwell 等）只存在于 wheel 文件名里。pip 从本地 wheel 文件
    安装时会把文件 URL 记进 dist-info/direct_url.json，从这里提取 arch 最可靠。
    未装 / 无 direct_url.json / 无匹配返回 None（调用方会触发按 GPU 重装兜底）。
    """
    try:
        import importlib.metadata as md
        dist = md.distribution("llama_cpp_python")
    except Exception:
        return None
    # 1. direct_url.json 的 url（本地 wheel 安装时含完整文件名 + local version tag）
    du = dist.read_text("direct_url.json")
    if du:
        try:
            import json
            url = json.loads(du).get("url", "")
            m = re.search(r"(ada|ampere|turing|blackwell)", url)
            if m:
                return m.group(1)
        except Exception:
            pass
    # 2. 兜底：METADATA Version（万一某些 wheel 把 local tag 写进了 Version）
    m = re.search(r"(ada|ampere|turing|blackwell)", dist.version or "")
    return m.group(1) if m else None


def find_wheel(arch: str) -> Path | None:
    """在 _llama_wheels/ 找匹配 arch 的 wheel；目录不存在或无匹配返回 None。"""
    if not WHEELS_DIR.is_dir():
        return None
    kws = ARCH_KEYWORDS.get(arch, [])
    if not kws:
        return None
    for w in sorted(WHEELS_DIR.glob("llama_cpp_python*.whl")):
        name = w.name.lower()
        if all(k.lower() in name for k in kws):
            return w
    return None


def main() -> int:
    print("[init] 检测 GPU 架构，校验翻译推理库...")
    cc = get_gpu_cc()
    if not cc:
        print("[init] 未检测到 NVIDIA GPU（或 nvidia-smi 不可用），跳过，保持当前推理库。")
        return 0
    target = CC_TO_ARCH.get(cc)
    if not target:
        print(f"[init] 未知 GPU compute capability={cc}，跳过（如需适配请联系作者）。")
        return 0

    cur = get_installed_arch()
    if cur == target:
        print(f"[init] 推理库匹配（{cur}，GPU cc={cc}），无需切换。")
        return 0

    prefix = "[init] 当前未安装推理库，" if cur is None else f"[init] 当前推理库={cur}，"
    whl = find_wheel(target)
    if whl is None:
        print(f"{prefix}GPU 需要 {target}（cc={cc}），但 _llama_wheels/ 下无对应 wheel，保持现状。")
        print("[init]   翻译功能可能不可用。把对应架构 wheel 放入 "
              "wd14-tagger-web/_llama_wheels/ 后重启即可。")
        return 0

    print(f"{prefix}GPU 需要 {target}（cc={cc}），开始安装 {whl.name} ...")
    try:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", str(whl),
             "--no-deps", "--force-reinstall"],
        )
    except Exception as e:
        print(f"[init] 安装失败：{e}（翻译功能可能不可用，不阻断主服务）")
        return 0
    print(f"[init] 完成：已切换到 {target} 推理库。继续启动服务。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
