"""
설치 스크립트 (install.bat 가 호출)
====================================
한글 안내가 깨지지 않도록 Python 으로 처리.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# 콘솔 출력 한글 깨짐 방지 (Windows)
if sys.platform == "win32":
    try:
        # UTF-8 코드페이지 강제
        os.system("chcp 65001 > nul")
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass


REQUIRED_PACKAGES = [
    "pywinauto", "comtypes", "pdfplumber", "pypdf", "anthropic",
    "tkinterdnd2", "pywin32", "pymupdf", "pillow", "easyocr",
]


def banner(title: str) -> None:
    line = "=" * 64
    print(f"\n{line}\n  {title}\n{line}")


def step(n: int, total: int, msg: str) -> None:
    print(f"\n[{n}/{total}] {msg}")


def run(cmd: list[str], check: bool = True) -> int:
    print(f"  $ {' '.join(cmd)}")
    res = subprocess.run(cmd)
    if check and res.returncode != 0:
        print(f"  ✗ 실패 (exit code {res.returncode})")
    return res.returncode


def main() -> int:
    banner("비전자문서등록 자동입력 - 설치")
    print(f"  Python: {sys.executable}")
    print(f"  버전:   {sys.version.split()[0]}")

    project = Path(__file__).parent.resolve()
    print(f"  설치경로: {project}")

    # 1. 패키지 설치
    step(1, 3, "Python 패키지 설치 중 (몇 분 소요)…")
    code = run([sys.executable, "-m", "pip", "install", "--user", "--quiet",
                *REQUIRED_PACKAGES])
    if code != 0:
        print("  ✗ 일부 패키지 설치 실패. 수동 설치 필요.")
        print(f"    pip install --user {' '.join(REQUIRED_PACKAGES)}")
        return 1
    print("  ✓ 완료")

    # 2. 바탕화면 / SendTo 바로가기
    step(2, 3, "바탕화면 / SendTo 바로가기 생성")
    shortcuts_py = project / "install_shortcuts.py"
    if shortcuts_py.exists():
        code = run([sys.executable, str(shortcuts_py)], check=False)
        if code != 0:
            print("  ! 바로가기 생성 실패. 수동 실행 가능: python install_shortcuts.py")
    else:
        print(f"  ! {shortcuts_py.name} 없음 — 건너뜀")

    # 3. Ollama 안내
    step(3, 3, "오프라인 LLM (Ollama) 안내")
    print("""
    오프라인에서도 사용하려면 Ollama 가 필요합니다 (선택 사항):
      1. https://ollama.com/download/OllamaSetup.exe 다운로드 + 설치
      2. 명령 프롬프트에서: ollama pull gemma3:4b   (3.3GB 다운로드)

    Claude API 키만 사용한다면 Ollama 는 설치 안 해도 됩니다.
    (Anthropic 키: https://console.anthropic.com/settings/keys 에서 발급)
    """)

    # 마무리 안내
    banner("설치 완료!")
    print("""
  다음 단계:
    1. 바탕화면의 [비전자문서등록] 더블클릭
    2. K-에듀파인 비전자문서등록 창을 열고 본인 정보 1회 캡처:
       - 접수자/업무담당자 옆 🔍 으로 본인 선택
       - 과제카드 옆 🔍 으로 조직 카드 선택
       - GUI 의 [👤 사용자 저장] + [📌 과제카드 저장] 클릭
    3. (선택) [⚙ 설정] 에서 Anthropic API 키 등록
    4. PDF 드래그 → [✅ 폼에 입력] → 자동
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
