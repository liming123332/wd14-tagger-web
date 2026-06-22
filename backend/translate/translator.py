from __future__ import annotations
from pathlib import Path
import json
import re
import threading
import logging

from backend.config import settings
from backend.tagger.models_spec import ModelSpec

logger = logging.getLogger(__name__)

# 腾讯 Hy-MT2-1.8B-GGUF（unsloth 重打包 Q4_K_M）：33 语种「快思维」翻译模型。
# 原版 tencent/Hy-MT2-*-GGUF 依赖腾讯自定义 STQ kernel（未并入 llama.cpp 主线，标准 wheel 加载
# 报 tensor offset 不匹配）；unsloth 用标准 llama.cpp 量化器重转成 Q4_K_M（标准 K-quant），绕开
# STQ，保留 Hy-MT2 权重质量。Q4_K_M 在 1.8B 上近乎无损（IQ2_M 2-bit 会让 solo/pleated_skirt 等
# 高频词语义丢失），1.13GB，GPU 卸载加载 ~0.7s、推理 ~0.15s/条。
# 用 llama-cpp-python 进程内加载（Blackwell CUDA wheel，与 onnxruntime-gpu 同代 sm_120），
# 仿 tagger 的 ensure_loaded 懒加载模式。翻译不落地：每次 /api/translate 现译，模型常驻不重载。
#
# folder 沿用 hy_mt2_2bit（历史命名，模型文件已在此目录）；实际为 Q4_K_M，不影响功能。
# 不进 tagger 的 MODEL_SPECS：那套是 onnx 反推模型字典（prep/tag_source 体系），翻译模型结构
# 不同（单 GGUF + llama.cpp 推理），独立管理 spec，但下载仍复用 _download_util.download_files。
TRANSLATE_SPEC = ModelSpec(
    key="hy_mt2_2bit",
    label="Hy-MT2 1.8B (翻译)",
    folder="hy_mt2_2bit",
    files={"Hy-MT2-1.8B-Q4_K_M.gguf":
           "https://huggingface.co/unsloth/Hy-MT2-1.8B-GGUF/resolve/main/Hy-MT2-1.8B-Q4_K_M.gguf"},
    prep="gguf",
    tag_source="none",
)

# 目标语言（模型卡 prompt 模板里的 target_lang，用英文语言名；默认译成中文）
DEFAULT_TARGET = "Chinese"

# 模型卡推荐 prompt 模板：只要翻译结果，不要任何解释
_PROMPT_TMPL = ("Translate the following text into {target}. Note that you should "
                "only output the translated result without any additional explanation: {text}")

# danbooru 高频标签中英对照词典（后处理兜底）：danbooru 专有标签（1girl/solo/pleated_skirt 等）
# 通用翻译模型易译错（solo→仅限），词典命中直接用权威译名、跳过模型（更快更准）。未命中再走 Hy-MT2。
# key 为原始 danbooru tag（带下划线），value 为中文译名。danbooru_glossary.json 可自行扩充。
_GLOSSARY_PATH = Path(__file__).parent / "danbooru_glossary.json"
_GLOSSARY: dict[str, str] = {}
if _GLOSSARY_PATH.exists():
    try:
        _GLOSSARY = json.loads(_GLOSSARY_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("danbooru 词典加载失败 %s: %s", _GLOSSARY_PATH, e)

# 反向词典：中文→标准英文 tag（复用 _GLOSSARY 反转）。中→英标签时精准命中 danbooru 标准词
# （双马尾→twintails、水手服→serafuku、单人→solo），绕过通用翻译模型的 danbooru 词汇盲区。
_GLOSSARY_REVERSE: dict[str, str] = {}
for _en, _zh in _GLOSSARY.items():
    if not _en.startswith("_"):
        _GLOSSARY_REVERSE.setdefault(_zh, _en)


def _normalize_phrase(s: str) -> str:
    """英文短语规范化：小写、去标点、空格/连字符/下划线归一为单空格。

    中文添加标签时翻译成空格分隔的英文短语（cat ears），不保留下划线——用户要求标签
    保存/显示都不要下划线。"""
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)   # 去标点（保留字母数字下划线空格连字符）
    s = re.sub(r"[\s_-]+", " ", s)   # 空格/连字符/残留下划线 → 单空格
    return s.strip()


def is_downloaded(models_root: Path = settings.MODELS_DIR) -> bool:
    """GGUF 是否已存在于 models_root/hy_mt2_2bit/。"""
    d = Path(models_root) / TRANSLATE_SPEC.folder
    return all((d / name).exists() for name in TRANSLATE_SPEC.files)


class HyTranslator:
    """Hy-MT2 翻译器：ensure_loaded 懒加载 GGUF，translate 批量翻译，unload 释放。

    与 tagger 同款 ensure_loaded：未下载则先 _download（复用 _download_util，带进度/原子写/
    前端轮询），再 _load（llama-cpp-python Llama，n_gpu_layers=-1 全卸 GPU，GPU 不可用回退 CPU）。
    模型常驻单例；推理串行化（一个 Llama 实例不可并发推理，用 Lock 保护）。"""

    def __init__(self, models_root: Path = settings.MODELS_DIR):
        self.models_root = Path(models_root)
        self.model_dir = self.models_root / TRANSLATE_SPEC.folder
        self.llm = None
        self._lock = threading.Lock()  # 串行化 create_completion（GGUF 单实例不可并发推理）

    @property
    def loaded(self) -> bool:
        return self.llm is not None

    def ensure_loaded(self) -> None:
        if self.llm is not None:
            return
        self._download()
        self._load()

    def _download(self) -> None:
        # 复用 tagger 下载逻辑：逐文件 + 进度 + 原子 .part + 前端轮询 _state。
        # 单文件 GGUF，未下载时前端下载浮层会显示「下载模型 hy_mt2_2bit · xx%」。
        from backend.tagger._download_util import download_files
        download_files(TRANSLATE_SPEC, self.model_dir, TRANSLATE_SPEC.key)

    def _load(self) -> None:
        # 注册 CUDA DLL 路径（pip 装的 nvidia-cublas/cuda-runtime + 系统 CUDA toolkit）。
        # ggml-cuda.dll 加载时按 PATH 找 cublasLt64_13.dll/cudart64_13.dll，不注册则 GPU 加载
        # 失败回退 CPU（便携包到无系统 CUDA 的机器上尤其要靠这步）。复用 onnxruntime 同款逻辑，幂等。
        from backend.tagger._onnx_providers import _register_cuda_dll_dirs
        _register_cuda_dll_dirs()
        from llama_cpp import Llama
        gguf = self.model_dir / "Hy-MT2-1.8B-Q4_K_M.gguf"
        if not gguf.exists():
            raise FileNotFoundError(f"GGUF missing: {gguf}")
        # n_gpu_layers=-1：全部层卸载到 GPU（Blackwell CUDA wheel + RTX50）。
        # n_ctx=4096：批量翻译 prompt 不会很长，4096 足够。
        # GPU 不可用（如换到无 CUDA 机器）时抛错 → 回退 n_gpu_layers=0 纯 CPU（慢但能用）。
        try:
            self.llm = Llama(model_path=str(gguf), n_gpu_layers=-1,
                             n_ctx=4096, verbose=False)
        except Exception as e:
            msg = str(e).lower()
            # 0xC000001D / illegal instruction：wheel 架构与 GPU 不匹配（如 Blackwell
            # wheel 跑在 RTX 40 上）。此时 CPU 回退也会崩（同一坏 ggml-cuda.dll），直接抛
            # 友好提示而非裸 500。正常情况启动时 init_llama_wheel.py 已装对 wheel，不会走到这。
            if any(k in msg for k in ("0xc000001d", "illegal instruction",
                                      "status_illegal_instruction", "-1073741795")):
                raise RuntimeError(
                    "翻译推理库与显卡架构不匹配（非法指令 0xC000001D）。"
                    "请重启整合包——启动时会自动检测 GPU 并安装匹配的推理库；"
                    "若仍失败，请联系作者获取对应架构 wheel。"
                ) from e
            logger.warning("HyTranslator GPU 加载失败（%s），回退 CPU", e)
            try:
                self.llm = Llama(model_path=str(gguf), n_gpu_layers=0,
                                 n_ctx=4096, verbose=False)
            except Exception as e2:
                raise RuntimeError(
                    f"翻译推理库加载失败（GPU: {e}; CPU 回退: {e2}）。"
                    "可能是推理库与显卡架构不匹配，请重启整合包（启动时自动检测适配）。"
                ) from e2
        logger.info("HyTranslator 已加载: %s", gguf)

    def translate(self, texts: list[str], target: str = DEFAULT_TARGET) -> list[str]:
        """批量翻译：逐条 create_completion（短标签，GPU 每条 <0.3s）。

        单条失败/空输出回退原文，不阻塞其他条。模型卡推荐采样参数：
        temperature 0.7 / top_p 0.6 / top_k 20 / repeat_penalty 1.05。"""
        self.ensure_loaded()
        results: list[str] = []
        for t in texts:
            if not t or not t.strip():
                results.append(t)
                continue
            # 词典兜底：danbooru 专有标签（1girl/solo/pleated_skirt 等）模型常译错，命中直接用权威
            # 译名、跳过模型推理（更快更准）。未命中再走 Hy-MT2（下划线→空格，模型理解更准）。
            if t in _GLOSSARY:
                results.append(_GLOSSARY[t])
                continue
            prompt = _PROMPT_TMPL.format(target=target, text=t.replace("_", " "))
            try:
                with self._lock:
                    resp = self.llm.create_completion(
                        prompt, max_tokens=128, temperature=0.7, top_p=0.6,
                        top_k=20, repeat_penalty=1.05,
                    )
                out = (resp["choices"][0]["text"] or "").strip()
                results.append(out or t)  # 空输出回退原文
            except Exception as e:
                logger.warning("翻译失败 %r: %s", t, e)
                results.append(t)  # 失败回退原文
        return results

    def translate_to_tags(self, zh_texts: list[str]) -> list[str]:
        """中文 → 英文标签短语：反向词典兜底（中→标准 tag 后转空格），未命中走 Hy-MT2 + 规范化。

        详情页「中文添加标签」用：用户输入中文（双马尾/百褶裙），转成英文短语。
        反向词典命中（双马尾→twintails）精准；未命中（猫耳）走模型译成英文再规范化。
        输出空格分隔短语（cat ears），不带下划线——用户要求标签保存/显示都不要下划线。"""
        self.ensure_loaded()
        results: list[str] = []
        for zh in zh_texts:
            if not zh or not zh.strip():
                results.append(zh)
                continue
            zs = zh.strip()
            # 反向词典：中文→标准英文 tag（精准，绕过模型的 danbooru 词汇盲区），再下划线转空格
            if zs in _GLOSSARY_REVERSE:
                results.append(_GLOSSARY_REVERSE[zs].replace("_", " "))
                continue
            # 未命中走模型中→英（低温更稳），再规范成空格短语（不带下划线）
            prompt = _PROMPT_TMPL.format(target="English", text=zs)
            try:
                with self._lock:
                    resp = self.llm.create_completion(
                        prompt, max_tokens=64, temperature=0.3, top_p=0.6,
                        top_k=20, repeat_penalty=1.05,
                    )
                out = (resp["choices"][0]["text"] or "").strip()
                tag = _normalize_phrase(out)
                results.append(tag or zs)  # 空结果回退原文
            except Exception as e:
                logger.warning("中→英翻译失败 %r: %s", zh, e)
                results.append(zs)
        return results

    def unload(self) -> None:
        """释放 Llama 实例（显存/RAM），下次 ensure_loaded 重新加载。不删 GGUF 文件。"""
        if self.llm is not None:
            try:
                del self.llm
            except Exception:
                pass
            self.llm = None
            import gc
            gc.collect()
