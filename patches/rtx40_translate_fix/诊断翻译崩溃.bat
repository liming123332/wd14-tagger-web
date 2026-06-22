@echo off
chcp 65001 >nul
title 翻译崩溃诊断 (0xc000001d)
cd /d "%~dp0"

echo ========================================
echo   翻译崩溃诊断 (0xc000001d / 非法指令)
echo ========================================
echo.
echo 本脚本只读检测，不改任何东西。跑完把窗口全部内容截图发回即可。
echo.

if not exist "runtime\python.exe" (
    echo [错误] 未找到 runtime\python.exe
    echo 请把本脚本放到整合包根目录（能看到 runtime 文件夹的那一层）
    echo.
    pause
    exit /b 1
)

echo [1/4] GPU 型号 / 计算能力 / 驱动版本
echo ----------------------------------------
nvidia-smi --query-gpu=name,compute_cap,driver_version --format=csv 2>nul
if errorlevel 1 echo   (nvidia-smi 失败：驱动未装或不在 PATH)
echo.
echo   读法：compute_cap 必须是 8.9 才是 RTX 40 系；
echo         若是 8.6 = RTX 30、7.5 = RTX 20/GTX16，装的 sm89 wheel 也不匹配。
echo.

echo [2/4] 当前安装的 llama_cpp_python 架构 (最关键！)
echo ----------------------------------------
runtime\python.exe -c "import importlib.metadata as m,re; d=m.distribution('llama_cpp_python'); u=d.read_text('direct_url.json') or ''; mm=re.search(r'(blackwell|sm89|ada|sm100|sm120)', u.lower()); print('  version =', d.version); print('  url     =', u); print('  >>> 实际架构:', mm.group(1) if mm else '未知')"
echo.
echo   读法：若显示 blackwell = sm89 没装上（pip 被版本号跳过）；
echo         若显示 sm89/ada = 已装上，问题在别处（看 [1] 和 [3][4]）。
echo.

echo [3/4] ggml-cuda.dll 是否存在
echo ----------------------------------------
runtime\python.exe -c "import llama_cpp,glob,os; b=os.path.dirname(llama_cpp.__file__); dlls=glob.glob(os.path.join(b,'**','ggml-cuda.dll'),recursive=True); print('  llama_cpp 目录:', b); print('  ggml-cuda.dll :', dlls if dlls else '未找到 -> 无 GPU，会走 CPU')"
echo.

echo [4/4] CUDA 运行时 DLL (ggml-cuda.dll 的依赖)
echo ----------------------------------------
runtime\python.exe -c "import glob,os; from pathlib import Path; sp=Path('runtime/Lib/site-packages').resolve(); patt=[sp/'nvidia'/'cublas'/'bin'/'*.dll', sp/'nvidia'/'cuda_runtime'/'bin'/'*.dll', sp/'nvidia'/'cudnn'/'bin'/'*.dll']; dlls=[]; [dlls.extend(glob.glob(str(p))) for p in patt]; print('  找到', len(dlls), '个 nvidia CUDA DLL'); [print('   ', os.path.basename(x)) for x in sorted(dlls)]"
echo.

echo ========================================
echo 诊断完成。请把本窗口【从上到下全部内容】截图发回。
echo ========================================
pause
