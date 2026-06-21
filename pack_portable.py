# -*- coding: utf-8 -*-
"""
WD14 Tagger Web 便携整合包打包脚本（可重复执行）

产物结构（SD 整合包风格：runtime 与源码分离，便于升级）：
    <PKG_ROOT>/
      runtime/             便携 Python + 依赖（固定，升级不动）
      wd14-tagger-web/     源码（升级时整体替换即可）
      启动.bat / 使用说明.txt / 更新说明.txt

用法:
    python pack_portable.py                 # 首次打包 / 增量更新源码
    python pack_portable.py --force-runtime # 强制重建 runtime（依赖变动时）

升级流程（软件更新后）:
    1. 改完源码、cd frontend && npm run build（前端有改动时）
    2. 重跑 python pack_portable.py（runtime 已存在会跳过，只刷新源码）
    3. 把整个 <PKG_ROOT> 重新发出去；或只压缩 wd14-tagger-web 让对方覆盖
"""
from __future__ import annotations
import argparse
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

# 日志以 UTF-8 输出（否则 Windows GBK 控制台会乱码、emoji 会崩 UnicodeEncodeError）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# ===== 配置 =====
PY_VERSION = "3.13.14"  # onnxruntime-gpu 1.27（支持 RTX50/Blackwell sm_120）的 wheel 仅 cp311+，故从 3.10 升到 3.13
EMBED_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/python-{PY_VERSION}-embed-amd64.zip"
GETPIP_URL = "https://bootstrap.pypa.io/get-pip.py"
VCREDIST_URL = "https://aka.ms/vs/17/release/vc_redist.x64.exe"

# 脚本位于项目根 wd14-tagger-web/ 内，故源码根 = 脚本所在目录；
# 整合包输出到项目外的兄弟目录，避免被打进包里、便于升级时单独替换源码。
SRC_ROOT = Path(__file__).resolve().parent
PKG_ROOT = SRC_ROOT.parent / "WD14-Tagger-Web-Portable"

# 拷源码时排除的目录/文件
EXCLUDE_DIRS = {".venv", "node_modules", "__pycache__", ".git",
                ".pytest_cache", ".vscode"}  # 注意：frontend/dist 必须保留（后端托管）
EXCLUDE_FILE_SUFFIXES = (".pyc", ".pyo")


def log(msg: str) -> None:
    print(f"[pack] {msg}", flush=True)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    log("$ " + " ".join(str(c) for c in cmd))
    return subprocess.run(cmd, check=True, **kw)


def download(url: str, dest: Path, retries: int = 5) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        log(f"已存在，跳过: {dest.name}")
        return
    log(f"下载 {url} -> {dest}")
    import time
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pack_portable/1.0"})
            with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
                shutil.copyfileobj(r, f)
            log(f"  完成 {dest.stat().st_size // 1024} KB")
            return
        except Exception as e:  # 国内访问境外源常 SSL 断/超时，删半成品重试
            last_err = e
            dest.unlink(missing_ok=True)
            log(f"  失败(尝试 {attempt}/{retries}): {e}")
            time.sleep(3)
    raise RuntimeError(f"下载失败（{retries} 次重试后仍失败）: {url}\n  最近错误: {last_err}")


def prepare_runtime(force: bool) -> None:
    runtime = PKG_ROOT / "runtime"
    pyexe = runtime / "python.exe"
    if pyexe.exists() and not force:
        log("runtime 已存在，跳过（依赖变动请用 --force-runtime 重建）")
        return
    if runtime.exists():
        shutil.rmtree(runtime)
    runtime.mkdir(parents=True)

    # 1. 下载并解压 embed python
    zip_path = PKG_ROOT / "_python-embed.zip"
    download(EMBED_URL, zip_path)
    log("解压 embed python ...")
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(runtime)
    zip_path.unlink()

    # 2. 启用 site（embed 默认注释了 import site，导致 site-packages 不加载、pip 不可用）
    pth_files = list(runtime.glob("python*._pth"))
    assert pth_files, "未找到 python*._pth"
    pth = pth_files[0]
    txt = pth.read_text(encoding="utf-8")
    txt = txt.replace("#import site", "import site")
    pth.write_text(txt, encoding="utf-8")
    log(f"已启用 site: {pth.name}")

    # 3. 装 pip
    getpip = runtime / "get-pip.py"
    download(GETPIP_URL, getpip)
    run([str(pyexe), str(getpip), "--no-warn-script-location"])
    getpip.unlink()

    # 4. 装依赖。用清华镜像（国内下 onnxruntime/cudnn/cublas 等几百 MB 大文件稳），
    #    并复用 SRC_ROOT/_dl 下已下载的 nvidia CUDA wheel（--find-links，避免重复下大文件）。
    log("安装依赖（首次较慢：onnxruntime~213MB + cudnn~403MB + cublas~373MB + cufft~175MB 等）...")
    install_cmd = [str(pyexe), "-m", "pip", "install", "--upgrade",
                   "-r", str(SRC_ROOT / "requirements.txt"),
                   "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
                   "--extra-index-url", "https://pypi.org/simple",
                   "--retries", "5", "--timeout", "180"]
    dl_dir = SRC_ROOT / "_dl"
    if dl_dir.is_dir():
        install_cmd += ["--find-links", str(dl_dir)]
        log(f"  复用已下载 wheel: {dl_dir}")
    run(install_cmd)

    # 5. 验证关键依赖可 import
    run([str(pyexe), "-c",
         "import onnxruntime, fastapi, uvicorn, numpy, PIL, yaml, multipart, pydantic; "
         "print('runtime deps OK, onnxruntime', onnxruntime.__version__)"])
    log("runtime 就绪")


def _ignore_when_copy(directory: Path, names: list[str]) -> set[str]:
    ignore = set()
    # 不拷开发版的 anima 封面图（5万+文件，由 copy_cf_data 从 animadex-data 权威拷贝）
    if Path(directory).name == "characterfinder" and "anima" in names:
        ignore.add("anima")
    for n in names:
        if n in EXCLUDE_DIRS:
            ignore.add(n)
        if any(n.endswith(s) for s in EXCLUDE_FILE_SUFFIXES):
            ignore.add(n)
    return ignore


def _warn_if_dist_stale() -> None:
    """frontend/src 有比 dist 更新的文件时警告（提醒先 npm run build，否则整合包用旧前端）。"""
    src = SRC_ROOT / "frontend" / "src"
    dist = SRC_ROOT / "frontend" / "dist"
    if not src.exists() or not (dist / "index.html").exists():
        return  # 没法判断，交给后面的 dist 存在性检查
    def newest(root: Path) -> float:
        return max((f.stat().st_mtime for f in root.rglob("*") if f.is_file()), default=0.0)
    if newest(src) > newest(dist) + 1.0:  # 1 秒容差，避免文件系统时间精度抖动
        log("!!! 警告: frontend/src 有比 dist 更新的文件 —— 前端代码改过但没重新构建！")
        log("    整合包将使用旧的前端 dist。请先执行: cd frontend && npm run build，再重跑本脚本。")


def copy_source() -> None:
    _warn_if_dist_stale()
    dest = PKG_ROOT / "wd14-tagger-web"
    if dest.exists():
        shutil.rmtree(dest)
    log(f"拷贝源码 {SRC_ROOT} -> {dest}（排除 .venv/node_modules/.git 等）")
    shutil.copytree(SRC_ROOT, dest, ignore=_ignore_when_copy)

    # 确保前端已构建；若源里 frontend/dist 缺失，提示（不自动 npm build，避免依赖 node）
    if not (dest / "frontend" / "dist" / "index.html").exists():
        log("⚠️ 警告: frontend/dist/index.html 不存在！请先 cd frontend && npm run build 后重打包")
    else:
        log("frontend/dist 已就绪（后端将托管）")

    # 清空用户数据与模型内容，保留空目录（用户自己拷模型 / 生成数据）
    for sub in ("models", "data/images", "data/promptbox"):
        d = dest / sub
        d.mkdir(parents=True, exist_ok=True)
        for p in list(d.iterdir()):
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
    log("已清空 models/ 与 data/ 用户数据（保留空目录）")
    copy_cf_data()


def copy_cf_data() -> None:
    """从兄弟目录 sd-character-finder/data/ 拷角色/艺术家离线数据到整合包。

    characterfinder 的 5 个 SQLite 库 + danbooru_tags.csv 由上游 sdcf 抓取生成,
    不在 wd14-tagger-web 仓库内。若不补，整合包 data/characterfinder/ 只有空壳，
    后端 _migrate() 会因 'no such table: characters' 崩溃（角色/艺术家功能不可用）。

    只拷权威数据（5 DB + csv + 封面目录）；运行时数据（cf_overlay.db /
    favorites.json / recent_viewed.json / overlay/）不覆盖，保留各自初始状态。
    源目录不存在时警告跳过（不阻断打包——可能未克隆 sdcf）。
    """
    dest_cf = PKG_ROOT / "wd14-tagger-web" / "data" / "characterfinder"
    dest_cf.mkdir(parents=True, exist_ok=True)

    # 1) 角色/艺术家库 + danbooru 封面（sdcf 抓取产物）
    sdcf_data = SRC_ROOT.parent / "sd-character-finder" / "data"
    if sdcf_data.exists():
        files = ["characters.db", "artists.db", "anima_characters.db",
                 "anima_artists.db", "danbooru_tags.csv"]
        copied = []
        for f in files:
            src = sdcf_data / f
            if src.exists():
                shutil.copy2(src, dest_cf / f)
                copied.append(f"{f}({src.stat().st_size // 1024}KB)")
        for d in ("covers", "artist_covers"):
            src_d = sdcf_data / d
            dst_d = dest_cf / d
            if dst_d.exists():
                shutil.rmtree(dst_d)
            if src_d.exists():
                shutil.copytree(src_d, dst_d)
                copied.append(f"{d}/")
        log(f"已拷角色/艺术家库到 data/characterfinder/: {', '.join(copied)}")
    else:
        log("⚠️ 未找到 ../sd-character-finder/data/，缺少角色库（后端会报 'no such table'）")

    # 2) anima 封面（本地离线缩略图；后端 local_image_path 期望在 anima/ 下，
    #    否则离线时 /api/cf/asset 回退 CDN blobs.animadex.net 会加载失败）
    animadex = SRC_ROOT.parent / "animadex-data"
    if animadex.exists():
        anima_dst = dest_cf / "anima"
        batches = 0
        for s, d in [("characters/thumbs", "characters"),
                     ("characters/images", "characters"),
                     ("artists/thumbs", "artists"),
                     ("artists/images", "artists")]:
            sp = animadex / s
            if sp.exists():
                (anima_dst / d).mkdir(parents=True, exist_ok=True)
                shutil.copytree(sp, anima_dst / d, dirs_exist_ok=True)
                batches += 1
        log(f"已拷 anima 封面到 data/characterfinder/anima/（{batches} 批，离线缩略图）")
    else:
        log("⚠️ 未找到 ../animadex-data/，anima 封面将走 CDN（离线无图）")


def write_launchers() -> None:
    # 启动.bat：cwd=源码目录（让 ROOT 自动推断正确），用 runtime 的 python 起 uvicorn，
    # 后台延迟 3 秒打开浏览器（等 uvicorn 起来）。
    start_bat = PKG_ROOT / "启动.bat"
    start_bat.write_text(
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        'cd /d "%~dp0wd14-tagger-web"\r\n'
        "echo.\r\n"
        "echo ===== WD14 Tagger Web =====\r\n"
        "echo 浏览器访问: http://127.0.0.1:8000\r\n"
        "echo 关闭本窗口即停止服务\r\n"
        "echo ============================\r\n"
        "echo.\r\n"
        'start "" cmd /c "timeout /t 3 >nul && start http://127.0.0.1:8000"\r\n'
        '"%~dp0runtime\\python.exe" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000\r\n'
        "echo.\r\n"
        "echo 服务已停止。\r\n"
        "pause\r\n",
        encoding="utf-8", newline="",  # newline=""：禁用 Windows text mode 的 \n→\r\n 转换，
        # 否则我写的 \r\n 会被转成 \r\r\n（CR CR LF）。bat 必须 CRLF（LF-only 会让 cmd 行边界
        # 错乱、中文行被当命令执行）；newline="" 让 \r\n 原样落盘为标准 CRLF，跨平台一致。
    )
    log(f"写入 {start_bat.name}")

    usage = PKG_ROOT / "使用说明.txt"
    usage.write_text(
        "WD14 Tagger Web 使用说明\n"
        "========================\n\n"
        "1. 首次使用：把模型文件夹拷到 wd14-tagger-web\\models\\ 下。\n"
        "   （例如 models\\wd14\\、models\\cl_tagger\\、models\\cl_tagger_v2_01a\\ 等，\n"
        "    文件夹名要和程序里一致；不知道就全拷进去。）\n\n"
        "2. 双击「启动.bat」，会自动打开浏览器访问 http://127.0.0.1:8000\n"
        "   （若浏览器没自动开，手动打开浏览器输入这个地址）。\n\n"
        "3. 用完关闭弹出的黑色命令行窗口即可停止服务。\n\n"
        "常见问题：\n"
        "- 启动报错「找不到 xxx.dll」或一闪而过：双击本目录下的 vc_redist.x64.exe\n"
        "  安装微软运行库后重启电脑再试（一般 Win10/11 已自带，多数不用装）。\n"
        "- 端口 8000 被占用：关闭其他占用程序，或编辑 启动.bat 把 8000 改成别的端口。\n"
        "- 反推很慢：CPU 模式正常现象，耐心等待。\n",
        encoding="utf-8",
    )
    log(f"写入 {usage.name}")

    update_note = PKG_ROOT / "更新说明.txt"
    update_note.write_text(
        "软件升级说明\n"
        "============\n\n"
        "本包采用「整合包」结构：\n"
        "- runtime\\        便携 Python + 依赖，升级时【不要动】\n"
        "- wd14-tagger-web\\ 程序源码，【升级时只替换这个目录】\n"
        "- models\\          你的模型，【不要动】\n"
        "- data\\            你的图片/提示词数据，【不要动】\n\n"
        "升级方法（二选一）：\n"
        "方法 A（推荐）：我把更新后的整个新包发给你，解压后把旧的 models\\ 和 data\\\n"
        "              拷到新包的 wd14-tagger-web\\ 下覆盖即可。\n"
        "方法 B：我只发你一个 wd14-tagger-web 源码压缩包，解压后整个覆盖本包的\n"
        "       wd14-tagger-web\\ 文件夹（models/data 不在里面，不受影响）。\n",
        encoding="utf-8",
    )
    log(f"写入 {update_note.name}")

    # 更新anima数据.bat：双击即从本机 animadex-data 同步角色/艺术家数据到整合包 data。
    # 前置是用户先用 AnimaDex\import.bat 拉取最新数据；本 bat 只负责把数据搬进整合包。
    # %* 透传参数，故命令行可追加 --prune / --animadex-data 等。
    anima_bat = PKG_ROOT / "更新anima数据.bat"
    anima_bat.write_text(
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        'cd /d "%~dp0"\r\n'
        "echo.\r\n"
        "echo ===== 更新 Anima 角色/艺术家数据 =====\r\n"
        "echo 从本机 animadex-data 同步到整合包 data\r\n"
        "echo 前提：先用 AnimaDex\\import.bat 拉取最新数据\r\n"
        "echo ========================================\r\n"
        "echo.\r\n"
        'if not exist "runtime\\python.exe" (\r\n'
        "    echo [错误] 未找到 runtime\\python.exe，这不是完整整合包。\r\n"
        "    pause & exit /b 1\r\n"
        ")\r\n"
        '"%~dp0runtime\\python.exe" "%~dp0wd14-tagger-web\\scripts\\update_anima.py" %*\r\n'
        "echo.\r\n"
        "pause\r\n",
        encoding="utf-8", newline="",  # 同 start_bat：bat 必须 CRLF，禁用 text mode 双重转换
    )
    log(f"写入 {anima_bat.name}")


def fetch_vcredist() -> None:
    """附带微软 VC++ 运行库安装包，对方缺 dll 时可装。"""
    dest = PKG_ROOT / "vc_redist.x64.exe"
    if dest.exists():
        log("vc_redist.x64.exe 已存在，跳过")
        return
    try:
        download(VCREDIST_URL, dest)
    except Exception as e:
        log(f"⚠️ 下载 vc_redist 失败（可忽略，多数机器已自带）: {e}")


def main() -> None:
    global PKG_ROOT
    ap = argparse.ArgumentParser()
    ap.add_argument("--force-runtime", action="store_true", help="强制重建 runtime")
    ap.add_argument("--pkg-root", default=str(PKG_ROOT), help="整合包输出目录")
    ap.add_argument("--no-vcredist", action="store_true", help="不附带 vc_redist")
    args = ap.parse_args()

    PKG_ROOT = Path(args.pkg_root)
    PKG_ROOT.mkdir(parents=True, exist_ok=True)
    log(f"整合包目录: {PKG_ROOT}")

    prepare_runtime(force=args.force_runtime)
    copy_source()
    write_launchers()
    if not args.no_vcredist:
        fetch_vcredist()

    log("全部完成")
    log(f"  整合包: {PKG_ROOT}")
    log(f"  启动:   双击 {PKG_ROOT/'启动.bat'}")


if __name__ == "__main__":
    main()
