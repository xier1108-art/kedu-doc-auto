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
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        # 디버그 모드는 콘솔 띄워서 에러 메시지 확인
        "--console" if debug else "--windowed",
        "--name", "비전자문서등록" + ("_debug" if debug else ""),

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

        # 무거운 모듈 제외 — 오프라인 LLM(Ollama)은 외부 프로그램이고
        # easyocr+torch는 단일 EXE에 넣기엔 너무 큼 (~500MB+).
        # 사용자가 오프라인 OCR 원하면 별도 설치 안내.
        "--exclude-module", "easyocr",
        "--exclude-module", "torch",
        "--exclude-module", "torchvision",
        "--exclude-module", "scipy",
        "--exclude-module", "matplotlib",
        "--exclude-module", "pandas",
        "--exclude-module", "IPython",
        "--exclude-module", "notebook",
        "--exclude-module", "jupyter",

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
    print("    - 오프라인 LLM(Gemma) 비활성 (Ollama 별도 설치 시 활성)")
    print("    - 오프라인 OCR(EasyOCR) 비활성 (Claude API 키 권장)")
    print("    - Windows Defender 가 처음에 검사 후 차단할 수 있음 (서명 안 함)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
