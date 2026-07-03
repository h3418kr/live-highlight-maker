# -*- coding: utf-8 -*-
"""
완전 무설치(파이썬 내장) 포터블 패키지 빌더.

이 스크립트는 '전체 설치된 파이썬 3.11' 로 실행해야 합니다.
  (임베디드 파이썬에는 tkinter 가 없어서, 현재 파이썬에서 복사해 옵니다.)

결과물:  D:\\capcut\\배포_무설치\\  (통째로 압축해 배포하면 됨)
  - python\\           내장 파이썬 + 모든 패키지
  - ffmpeg\\           포터블 FFmpeg
  - models\\           Whisper 모델 (base, small)
  - *.py, 사용설명서, 실행.bat
"""
import os
import sys
import shutil
import zipfile
import subprocess
import urllib.request
import ssl

SRC = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(SRC, "배포_무설치")
PY_DIR = os.path.join(OUT, "python")
FFMPEG_DIR = os.path.join(OUT, "ffmpeg")
MODELS_DIR = os.path.join(OUT, "models")

PY_VER = "3.11.9"
EMBED_URL = f"https://www.python.org/ftp/python/{PY_VER}/python-{PY_VER}-embed-amd64.zip"
GETPIP_URL = "https://bootstrap.pypa.io/get-pip.py"
FFMPEG_URL = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"

CTX = ssl.create_default_context()


def log(m):
    print(m, flush=True)


def download(url, dest):
    log(f"    다운로드: {url}")
    with urllib.request.urlopen(url, context=CTX) as r, open(dest, "wb") as f:
        total = int(r.headers.get("Content-Length", 0))
        done = 0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r      {done*100//total}% ({done//1048576}MB)", end="", flush=True)
    if total:
        print()


# ── 1. 임베디드 파이썬 ─────────────────────────────────────────────
def step_embed_python():
    log("\n[1/6] 내장 파이썬 준비")
    if os.path.exists(os.path.join(PY_DIR, "python.exe")):
        log("      -> 이미 있음, 건너뜀")
        return
    os.makedirs(PY_DIR, exist_ok=True)
    zp = os.path.join(OUT, "_py_embed.zip")
    download(EMBED_URL, zp)
    with zipfile.ZipFile(zp) as z:
        z.extractall(PY_DIR)
    os.remove(zp)

    # python311._pth 수정: site 활성화 + site-packages 경로 추가
    pth = os.path.join(PY_DIR, "python311._pth")
    with open(pth, "w", encoding="utf-8") as f:
        f.write("python311.zip\n.\nLib\\site-packages\n\nimport site\n")
    log("      -> 내장 파이썬 준비 완료")


# ── 2. tkinter 복사 (현재 전체설치 파이썬에서) ────────────────────
def step_copy_tkinter():
    log("\n[2/6] tkinter / tcl-tk 복사")
    full = sys.base_prefix  # 현재(전체설치) 파이썬 경로
    dlls = os.path.join(full, "DLLs")
    lib = os.path.join(full, "Lib")

    copies = [
        (os.path.join(dlls, "_tkinter.pyd"), os.path.join(PY_DIR, "_tkinter.pyd")),
        (os.path.join(dlls, "tcl86t.dll"), os.path.join(PY_DIR, "tcl86t.dll")),
        (os.path.join(dlls, "tk86t.dll"), os.path.join(PY_DIR, "tk86t.dll")),
        (os.path.join(dlls, "zlib1.dll"), os.path.join(PY_DIR, "zlib1.dll")),
    ]
    for s, d in copies:
        if os.path.exists(s):
            shutil.copy2(s, d)
            log(f"      복사: {os.path.basename(s)}")
        else:
            log(f"      (없음, 건너뜀) {os.path.basename(s)}")

    # tkinter 패키지
    dst_tk = os.path.join(PY_DIR, "Lib", "site-packages", "tkinter")
    if not os.path.exists(dst_tk):
        shutil.copytree(os.path.join(lib, "tkinter"), dst_tk)
        log("      복사: Lib/tkinter")

    # tcl 라이브러리 폴더
    dst_tcl = os.path.join(PY_DIR, "tcl")
    src_tcl = os.path.join(full, "tcl")
    if os.path.isdir(src_tcl) and not os.path.exists(dst_tcl):
        shutil.copytree(src_tcl, dst_tcl)
        log("      복사: tcl/")
    log("      -> tkinter 준비 완료")


# ── 3. pip 설치 ───────────────────────────────────────────────────
def step_pip():
    log("\n[3/6] pip 설치")
    py = os.path.join(PY_DIR, "python.exe")
    getpip = os.path.join(OUT, "get-pip.py")
    download(GETPIP_URL, getpip)
    subprocess.run([py, getpip], check=True)
    os.remove(getpip)
    log("      -> pip 설치 완료")


# ── 4. 패키지 설치 (CPU torch) ────────────────────────────────────
def step_packages():
    log("\n[4/6] 패키지 설치 (torch CPU + 나머지)")
    py = os.path.join(PY_DIR, "python.exe")
    subprocess.run([py, "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
                   check=True)
    # CPU 전용 torch (용량 절감)
    subprocess.run([py, "-m", "pip", "install", "torch",
                    "--index-url", "https://download.pytorch.org/whl/cpu"], check=True)
    subprocess.run([py, "-m", "pip", "install", "-r",
                    os.path.join(SRC, "requirements.txt")], check=True)
    log("      -> 패키지 설치 완료")


# ── 5. FFmpeg ─────────────────────────────────────────────────────
def step_ffmpeg():
    log("\n[5/6] FFmpeg 준비")
    if os.path.exists(os.path.join(FFMPEG_DIR, "bin", "ffmpeg.exe")):
        log("      -> 이미 있음, 건너뜀")
        return
    zp = os.path.join(OUT, "_ffmpeg.zip")
    download(FFMPEG_URL, zp)
    tmp = os.path.join(OUT, "_ff_tmp")
    if os.path.exists(tmp):
        shutil.rmtree(tmp, ignore_errors=True)
    with zipfile.ZipFile(zp) as z:
        z.extractall(tmp)
    inner = None
    for n in os.listdir(tmp):
        c = os.path.join(tmp, n)
        if os.path.isdir(c) and os.path.exists(os.path.join(c, "bin", "ffmpeg.exe")):
            inner = c
            break
    if inner:
        if os.path.exists(FFMPEG_DIR):
            shutil.rmtree(FFMPEG_DIR, ignore_errors=True)
        shutil.move(inner, FFMPEG_DIR)
    shutil.rmtree(tmp, ignore_errors=True)
    os.remove(zp)
    log("      -> FFmpeg 준비 완료")


# ── 6. Whisper 모델 ───────────────────────────────────────────────
def step_models():
    log("\n[6/6] Whisper 모델 다운로드 (base, small)")
    os.makedirs(MODELS_DIR, exist_ok=True)
    py = os.path.join(PY_DIR, "python.exe")
    code = (
        "import whisper,sys;"
        "[whisper.load_model(m, download_root=sys.argv[1]) for m in ('base','small')];"
        "print('models ok')"
    )
    subprocess.run([py, "-c", code, MODELS_DIR], check=True)
    log("      -> 모델 준비 완료")


# ── 스크립트/설명서/런처 복사 ─────────────────────────────────────
def step_assets():
    log("\n[+] 스크립트 / 설명서 / 런처 복사")
    for f in ("gui.py", "auto_editor.py", "summarizer.py"):
        shutil.copy2(os.path.join(SRC, f), os.path.join(OUT, f))
    manual = os.path.join(SRC, "배포", "사용설명서.txt")
    if os.path.exists(manual):
        shutil.copy2(manual, os.path.join(OUT, "사용설명서.txt"))

    launcher = (
        "@echo off\r\n"
        "chcp 65001 >nul\r\n"
        "cd /d \"%~dp0\"\r\n"
        "set \"TCL_LIBRARY=%~dp0python\\tcl\\tcl8.6\"\r\n"
        "set \"TK_LIBRARY=%~dp0python\\tcl\\tk8.6\"\r\n"
        "start \"\" \"%~dp0python\\pythonw.exe\" \"%~dp0gui.py\"\r\n"
    )
    with open(os.path.join(OUT, "실행.bat"), "w", encoding="utf-8") as f:
        f.write(launcher)
    log("      -> 완료")


def main():
    if not sys.version.startswith("3.11"):
        log(f"[경고] 현재 파이썬 {sys.version.split()[0]} 입니다.")
        log("       tkinter 호환을 위해 3.11 전체설치 파이썬으로 실행을 권장합니다.")
    os.makedirs(OUT, exist_ok=True)
    log("=" * 55)
    log("  완전 무설치 포터블 패키지 빌드")
    log(f"  출력: {OUT}")
    log("=" * 55)
    step_embed_python()
    step_copy_tkinter()
    step_pip()
    step_packages()
    step_ffmpeg()
    step_models()
    step_assets()
    log("\n" + "=" * 55)
    log("  빌드 완료!  '배포_무설치' 폴더를 압축해 배포하세요.")
    log("  사용자는 압축을 풀고 '실행.bat' 만 더블클릭하면 됩니다.")
    log("=" * 55)


if __name__ == "__main__":
    main()
