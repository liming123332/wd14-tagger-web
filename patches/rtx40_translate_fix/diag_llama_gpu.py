# -*- coding: utf-8 -*-
"""诊断翻译 GPU 加载崩溃（0xC000001D）。

模拟 translator._load 的真实环境（先 _register_cuda_dll_dirs，再 GPU 加载），
在崩溃前把 GGML verbose 输出（检测到的 GPU / 加载的后端 / kernel）抓出来，
同时探测每个 ggml-cuda.dll 的架构——定位「装对了 sm89 仍崩」的根因。
"""
import sys
import os
import glob

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

WEB = os.path.join(os.getcwd(), "wd14-tagger-web")
sys.path.insert(0, WEB)

print("=" * 56)
print("  翻译 GPU 加载诊断（0xC000001D / 非法指令）")
print("=" * 56)

# 1. 注册 CUDA DLL（模拟 translator._load 环境）
try:
    from backend.tagger._onnx_providers import _register_cuda_dll_dirs
    _register_cuda_dll_dirs()
    print("[1] CUDA DLL 目录已注册 ✓（模拟翻译进程环境）")
except Exception as e:
    print("[1] 注册失败 ✗:", repr(e))

# 2. import llama_cpp
try:
    import llama_cpp
    print("[2] import llama_cpp ✓  version =", llama_cpp.__version__)
    print("    path =", llama_cpp.__file__)
except Exception as e:
    print("[2] import llama_cpp 失败 ✗:", repr(e))
    print("    => llama.dll 依赖的 CUDA DLL 仍缺失")
    sys.exit(2)

# 3. 列出所有 ggml-cuda.dll + sha256（两个 hash 不同 = 不同架构 = 冲突实锤）
import hashlib
print("[3] 所有 ggml-cuda.dll（看 site-packages/bin/ 是否有残留；sha256 不同=不同架构）:")
sp = os.path.dirname(os.path.dirname(llama_cpp.__file__))
found = sorted(glob.glob(os.path.join(sp, "**", "ggml-cuda.dll"), recursive=True))
for h in found:
    data = open(h, "rb").read()
    sha = hashlib.sha256(data).hexdigest()[:16]
    mark = "  <<< 非标准位置（卸载残留嫌疑）" if os.path.basename(os.path.dirname(h)) == "bin" else ""
    print("    ", h.replace(sp, "...site-packages"), "| sha", sha, "|",
          len(data) // 1024 // 1024, "MB", mark)

# 4. GPU 加载 GGUF（verbose=True：崩溃前会打印 GGML 检测到的 GPU / backend）
gguf = glob.glob(os.path.join(WEB, "models", "hy_mt2_2bit", "*.gguf"))
print("[4] GPU 加载测试（n_gpu_layers=-1，verbose 打印 GGML 初始化信息）:")
if not gguf:
    print("    未找到 models/hy_mt2_2bit/*.gguf，跳过 GPU 加载")
else:
    print("    模型:", os.path.basename(gguf[0]))
    print("-" * 56)
    try:
        from llama_cpp import Llama
        Llama(model_path=gguf[0], n_gpu_layers=-1, n_ctx=512, verbose=True)
        print("-" * 56)
        print("    GPU 加载成功 ✓（翻译应该能用）")
    except Exception as e:
        print("-" * 56)
        print("    GPU 加载崩溃 ✗:", repr(e))

print()
print("诊断结束。请把以上【全部内容】截图发回。")
