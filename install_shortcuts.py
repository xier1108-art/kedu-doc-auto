"""
Windows 통합 설치
=================
바탕화면 바로가기 + Send to 메뉴 항목을 생성합니다.
한 번만 실행하면 됩니다:

    python install_shortcuts.py

만든 항목
---------
1) 바탕화면 [📄 비전자문서등록] 바로가기
   - 더블클릭 → GUI 실행
   - PDF 파일을 아이콘에 끌어다 놓으면 즉시 처리

2) "보내기" 메뉴에 [비전자문서등록] 추가
   - 파일 탐색기에서 PDF 우클릭 → 보내기 → 비전자문서등록
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import win32com.client  # pywin32

PROJECT_DIR = Path(__file__).parent.resolve()
GUI_PY = PROJECT_DIR / "gui.py"

# pythonw.exe (콘솔 안 뜨게)
PYTHON_DIR = Path(sys.executable).parent
PYTHONW = PYTHON_DIR / "pythonw.exe"
if not PYTHONW.exists():
    PYTHONW = Path(sys.executable)  # fallback


def make_shortcut(path: Path, target: Path, args: str = "", workdir: Path | None = None,
                  icon: str = "", description: str = "") -> None:
    shell = win32com.client.Dispatch("WScript.Shell")
    sc = shell.CreateShortcut(str(path))
    sc.TargetPath = str(target)
    sc.Arguments = args
    sc.WorkingDirectory = str(workdir or target.parent)
    if icon:
        sc.IconLocation = icon
    if description:
        sc.Description = description
    sc.Save()


def install_desktop():
    desktop = Path(os.environ["USERPROFILE"]) / "Desktop"
    lnk = desktop / "비전자문서등록.lnk"
    make_shortcut(
        lnk,
        target=PYTHONW,
        args=f'"{GUI_PY}"',
        workdir=PROJECT_DIR,
        icon="shell32.dll,1",
        description="K-에듀파인 비전자문서등록 자동입력 (PDF 드래그 가능)",
    )
    print(f"✓ 바탕화면 바로가기: {lnk}")


def install_sendto():
    sendto = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "SendTo"
    sendto.mkdir(parents=True, exist_ok=True)
    lnk = sendto / "비전자문서등록.lnk"
    make_shortcut(
        lnk,
        target=PYTHONW,
        args=f'"{GUI_PY}"',
        workdir=PROJECT_DIR,
        icon="shell32.dll,1",
        description="K-에듀파인 비전자문서등록 자동입력",
    )
    print(f"✓ Send to 메뉴: {lnk}")


def main():
    print("Windows 통합 설치 중…")
    install_desktop()
    install_sendto()
    print("\n완료!")
    print("  • 바탕화면의 [비전자문서등록] 더블클릭")
    print("  • 또는 PDF 우클릭 → 보내기 → 비전자문서등록")


if __name__ == "__main__":
    main()
