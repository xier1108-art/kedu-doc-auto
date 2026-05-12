"""
독립 실행 EXE 빌드 (PyInstaller)
==================================
사용자 PC에 Python 설치 없이 EXE만으로 실행 가능하게 만든다.

산출: dist/비전자문서등록.exe

전제: 빌드 시점에 PyInstaller, comtypes, tkinterdnd2 등 모든 의존성 설치돼있어야.
실행: python build.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

PROJECT = Path(__file__).parent.resolve()
DIST = PROJECT / "dist"
BUILD = PROJECT / "build"


def step(msg: str) -> None:
    print(f"\n{'='*64}\n  {msg}\n{'='*64}")


def main() -> int:
    # ── 1) comtypes 의 MSHTML 타입라이브러리 사전 생성 ──
    # PyInstaller 가 동적 생성된 comtypes.gen 모듈을 못 잡으므로 빌드 전에 한 번 import 해서
    # %TEMP%/comtypes_cache 에 .py 파일을 만들고, 그걸 datas 로 포함시킨다.
    step("[1/4] comtypes MSHTML typelib 사전 생성")
    import comtypes.client
    comtypes.client.GetModule("mshtml.tlb")
    from comtypes.gen import MSHTML  # noqa: F401  (강제 로드)
    import comtypes.gen as _gen
    gen_dir = Path(_gen.__file__).parent
    print(f"  comtypes.gen 위치: {gen_dir}")
    print(f"  파일 수: {len(list(gen_dir.glob('*.py')))}")

    # ── 2) tkinterdnd2 데이터 파일 위치 ──
    step("[2/4] tkinterdnd2 데이터 위치 확인")
    import tkinterdnd2
    tkdnd_dir = Path(tkinterdnd2.__file__).parent
    print(f"  tkinterdnd2: {tkdnd_dir}")

    # ── 3) PyInstaller 호출 ──
    step("[3/4] PyInstaller 빌드 (수 분 소요)")
    if BUILD.exists():
        shutil.rmtree(BUILD, ignore_errors=True)
    debug = "--debug" in sys.argv
    onedir = "--onedir" in sys.argv  # 빠른 시작 모드 (폴더 배포)
    splash_png = PROJECT / "splash.png"
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        # onedir: 매 실행 즉시 시작 (1-3초). 폴더 통째로 배포.
        # onefile: 단일 EXE. 첫 실행 unpack 시간 30-60초.
        "--onedir" if onedir else "--onefile",
        "--console" if debug else "--windowed",
        "--name", "비전자문서등록" + ("_debug" if debug else ""),
        # splash: 즉시 표시 → 백그라운드에서 Python 시작 → import 끝나면 close
        *(["--splash", str(splash_png)] if splash_png.exists() and not debug else []),

        # 데이터 (런타임에 필요)
        "--add-data", f"{gen_dir};comtypes/gen",
        "--add-data", f"{tkdnd_dir};tkinterdnd2",

        # hidden imports — 동적 import 라 자동 탐지 안 됨
        "--hidden-import", "comtypes.gen.MSHTML",
        "--hidden-import", "comtypes.gen._3050F1C5_98B5_11CF_BB82_00AA00BDCE0B_0_4_0",
        "--hidden-import", "tkinterdnd2",
        "--hidden-import", "win32clipboard",
        "--hidden-import", "win32com.client",
        "--hidden-import", "pythoncom",
        "--hidden-import", "anthropic",
        "--hidden-import", "pdfplumber",
        "--hidden-import", "pypdf",
        "--hidden-import", "fitz",
        "--hidden-import", "PIL",

        # 무거운/사용 안 하는 모듈 제외 (v1.0.7 — Claude API 전용)
        "--exclude-module", "easyocr",
        "--exclude-module", "torch",
        "--exclude-module", "torchvision",
        "--exclude-module", "scipy",
        "--exclude-module", "matplotlib",
        "--exclude-module", "pandas",
        "--exclude-module", "IPython",
        "--exclude-module", "notebook",
        "--exclude-module", "jupyter",
        # 추가: GUI 에서 안 쓰는 오프라인 추출 모듈 (코드 남아있지만 EXE 에서 제외)
        "--exclude-module", "ocr_extract",
        "--exclude-module", "local_extract",

        # Entry point
        "gui.py",
    ]
    print("  $ " + " ".join(cmd[:5]) + " ...")
    res = subprocess.run(cmd, cwd=PROJECT)
    if res.returncode != 0:
        print(f"\n[✗] PyInstaller 빌드 실패 (exit {res.returncode})")
        return 1

    # ── 4) 결과 확인 ──
    step("[4/4] 결과 확인")
    if onedir:
        out_dir = DIST / "비전자문서등록"
        if not out_dir.exists():
            print(f"[✗] 폴더 없음: {out_dir}")
            return 1
        # 총 크기 계산
        total = sum(p.stat().st_size for p in out_dir.rglob("*") if p.is_file())
        print(f"  ✓ {out_dir} (폴더)")
        print(f"  ✓ 폴더 총 크기: {total/1024/1024:.1f} MB")
        # ZIP 으로 압축
        import zipfile
        zip_path = DIST / "비전자문서등록-fast.zip"
        if zip_path.exists():
            zip_path.unlink()
        print(f"  ZIP 압축 중…")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for p in out_dir.rglob("*"):
                if p.is_file():
                    zf.write(p, p.relative_to(DIST))
        print(f"  ✓ {zip_path}")
        print(f"  ✓ ZIP 크기: {zip_path.stat().st_size/1024/1024:.1f} MB")
        print()
        print("  ⚡ 빠른 시작 (onedir) 모드:")
        print("    - 받는 사람: ZIP 풀고 폴더 안의 '비전자문서등록.exe' 더블클릭")
        print("    - 매 실행 1~3초 (unpack 없음)")
    else:
        exe = DIST / "비전자문서등록.exe"
        if not exe.exists():
            print(f"[✗] EXE 없음: {exe}")
            return 1
        size_mb = exe.stat().st_size / 1024 / 1024
        print(f"  ✓ {exe}")
        print(f"  ✓ 크기: {size_mb:.1f} MB")
        print()
        print("  📤 이 EXE 한 파일만 보내면 됩니다.")
        print("     수신자: Python/Node 설치 불필요.")
        print()
        print("  ⚠ 단점:")
        print("    - 첫 실행 unpack 30~60초 (--onedir 모드로 빌드하면 즉시 시작)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
