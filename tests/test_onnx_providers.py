"""select_providers() 单元测试：验证 ONNX 执行后端优先级 CUDA > DirectML > CPU。

select_providers(available) 接受显式的 available providers 列表（测试注入），
不触碰真实 onnxruntime —— 因此在任意 onnxruntime 版本（CPU/GPU）下都能跑。
背景：RTX 5080 是 Blackwell sm_120，官方 onnxruntime-gpu 1.27 (CUDA 13) 才含
其内核；provider 选择逻辑封装后，装 gpu 包→CUDA、装 directml 包→DirectML、
都没有→CPU，一套代码三套环境自适应。"""
from __future__ import annotations

from backend.tagger._onnx_providers import select_providers


def test_prefers_cuda_over_cpu():
    # 有 CUDA → CUDA 优先，CPU 兜底在后
    assert select_providers(["CUDAExecutionProvider", "CPUExecutionProvider"]) == [
        "CUDAExecutionProvider",
        "CPUExecutionProvider",
    ]


def test_dml_when_no_cuda():
    # 无 CUDA 有 DirectML → 走 DirectML（Windows 通用 GPU 后端）
    assert select_providers(["DmlExecutionProvider", "CPUExecutionProvider"]) == [
        "DmlExecutionProvider",
        "CPUExecutionProvider",
    ]


def test_cuda_beats_dml():
    # CUDA 与 DirectML 同时在 → CUDA 胜出（性能最优），不同时塞两个 GPU 后端
    p = select_providers(["DmlExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"])
    assert p[0] == "CUDAExecutionProvider"
    assert "DmlExecutionProvider" not in p


def test_cpu_only():
    assert select_providers(["CPUExecutionProvider"]) == ["CPUExecutionProvider"]


def test_empty_defaults_to_cpu():
    assert select_providers([]) == ["CPUExecutionProvider"]


def test_unknown_providers_ignored():
    # 未识别的 provider（如云端的 AzureExecutionProvider）不入选，保底 CPU
    assert select_providers(["AzureExecutionProvider"]) == ["CPUExecutionProvider"]
