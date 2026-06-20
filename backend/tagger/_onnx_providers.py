"""ONNX 执行后端（Execution Provider）选择 + Windows CUDA DLL 路径注册。

封装 core/CLTagger/CLTaggerV2 三处重复的 provider 探测逻辑。优先级：

    CUDA  >  DirectML  >  CPU

- CUDAExecutionProvider：性能最优，需 onnxruntime-gpu（CUDA 13 + cuDNN）+ N 卡。
  注意 Blackwell（RTX 50/5090/5080，sm_120）需 onnxruntime-gpu 1.27（CUDA 13）才含内核，
  旧版（如 1.23 CUDA 12）会静默退回 CPU。
- DmlExecutionProvider：Windows 通用 GPU 后端，需 onnxruntime-directml，N/A/I 卡通吃。
- CPUExecutionProvider：兜底，任何环境都有。

available 显式传入时直接据此选择（测试用，不碰真实 onnxruntime）；
available=None 时探测当前 onnxruntime（运行时实际行为）。

Windows CUDA DLL 注册（_register_cuda_dll_dirs）：
    onnxruntime-gpu 的 CUDA EP 在 Windows 用传统 LoadLibrary 加载
    onnxruntime_providers_cuda.dll，其依赖（cudnn64_9.dll、cublas64_13.dll、
    nvrtc64_130_0.dll 等）按 PATH 环境变量搜索。pip 装的 nvidia-cudnn-cu13 /
    nvidia-cublas / nvidia-cuda-nvrtc 把 DLL 放在 site-packages/nvidia/{cudnn,cu13}/bin/，
    不在 PATH —— 不注册则 onnxruntime_providers_cuda.dll 加载失败、CUDA EP 创建失败、
    静默退回 CPU（Blackwell 上尤其隐蔽：available 里仍有 CUDAExecutionProvider，
    但 session.get_providers() 只剩 CPU）。修复：把上述 bin 目录 + 系统 CUDA toolkit
    bin prepend 到 PATH（os.add_dll_directory 对此依赖链解析无效，必须改 PATH）。
"""
from __future__ import annotations

import os
import sys


def _register_cuda_dll_dirs() -> None:
    """把 pip 装的 nvidia-*-cu13 DLL 目录 + 系统 CUDA toolkit bin 注册进 DLL 搜索路径。

    仅 Windows 生效；非 Windows 直接返回。幂等（进程内只执行一次）。
    将目录同时 prepend 到 PATH（onnxruntime 内部 LoadLibrary 解析依赖走 PATH）
    并调用 os.add_dll_directory（双保险）。目录不存在则跳过。
    """
    if sys.platform != "win32":
        return
    if getattr(_register_cuda_dll_dirs, "_done", False):
        return
    _register_cuda_dll_dirs._done = True  # type: ignore[attr-defined]

    import importlib.util

    dirs: list[str] = []
    # pip 装的 nvidia namespace 包：site-packages/nvidia/<pkg>/bin
    # （cudnn/bin → cudnn64_9.dll；cu13/bin → cublas/nvrtc DLL）
    spec = importlib.util.find_spec("nvidia")
    roots = list(spec.submodule_search_locations) if (spec and spec.submodule_search_locations) else []
    for root in roots:
        for sub in os.listdir(root):
            b = os.path.join(root, sub, "bin")
            if not os.path.isdir(b):
                continue
            dirs.append(b)  # 如 cudnn/bin（cudnn64_9.dll 直接在此）
            # cu13 系列（cublas/nvrtc）把 DLL 放在 bin/<arch>/，如 cu13/bin/x86_64/cublasLt64_13.dll
            for inner in os.listdir(b):
                inner_dir = os.path.join(b, inner)
                if os.path.isdir(inner_dir):
                    dirs.append(inner_dir)
    # 系统 CUDA toolkit bin（CUDA_PATH，提供 cudart64_13.dll / cufft / curand 等）
    cuda_path = os.environ.get("CUDA_PATH")
    if cuda_path:
        for sub in ("bin", os.path.join("bin", "x64")):
            b = os.path.join(cuda_path, sub)
            if os.path.isdir(b):
                dirs.append(b)

    if not dirs:
        return
    os.environ["PATH"] = os.pathsep.join(dirs) + os.pathsep + os.environ.get("PATH", "")
    for d in dirs:
        try:
            os.add_dll_directory(d)
        except (OSError, FileNotFoundError):
            pass


def select_providers(available: list[str] | None = None) -> list[str]:
    """返回 providers 列表，最优 GPU 后端插首位、CPU 兜底在末尾。

    返回形如 ["CUDAExecutionProvider", "CPUExecutionProvider"]；若无可用 GPU
    后端则仅 ["CPUExecutionProvider"]。同一次调用最多塞一个 GPU 后端（不混搭）。
    """
    providers = ["CPUExecutionProvider"]
    if available is None:
        # 须在 import onnxruntime 前 prepend PATH，否则 cudnn64_9.dll 找不到、CUDA EP 静默退 CPU
        _register_cuda_dll_dirs()
        try:
            import onnxruntime as ort

            available = list(ort.get_available_providers())
        except Exception:
            return providers
    avail = set(available)
    if "CUDAExecutionProvider" in avail:
        providers.insert(0, "CUDAExecutionProvider")
    elif "DmlExecutionProvider" in avail:
        providers.insert(0, "DmlExecutionProvider")
    return providers
