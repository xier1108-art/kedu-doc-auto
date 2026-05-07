"""
공유용 ZIP 패키징 도구 (개발자용)
====================================
개인 데이터 / 임시 파일을 제외하고 안전한 ZIP 을 생성합니다.

실행: python package.py
산출: dist/비전자문서등록_자동입력_vYYYYMMDD.zip
"""
from __future__ import annotations

import datetime as _dt
import sys
import zipfile
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.resolve()
DIST_DIR = PROJECT_DIR / "dist"

# 절대 포함하지 않을 파일/폴더
EXCLUDE_DIRS = {"__pycache__", ".git", ".venv", "venv", "dist", "build",
                ".vscode", ".idea", ".claude"}
EXCLUDE_PREFIXES = ("_",)  # _probe.py, _test.py 등
EXCLUDE_SUFFIXES = (".pyc", ".pyo", ".zip")
EXCLUDE_EXACT = {".kedu_anthropic_key", ".kedu_user.json", ".kedu_taskcard.json"}

# 포함할 파일 (.gitignore 와 비슷한 화이트리스트 — 명시적으로 안전)
INCLUDE_FILES = {
    "ai_extract.py", "auto_fill.py", "gui.py", "install.bat", "install.py",
    "install_shortcuts.py", "local_extract.py", "ocr_extract.py",
    "package.py", "pdf_parser.py", "README.md", "SHARING.md",
    "taskcard.py", "user.py", "wxs_form.py", ".gitignore",
}


def _should_exclude(path: Path) -> bool:
    """경로가 제외 대상인지 확인 (개인 데이터 / 임시 파일 / 캐시)."""
    name = path.name
    if name in EXCLUDE_EXACT:
        return True
    if name.startswith(EXCLUDE_PREFIXES):
        return True
    if name.endswith(EXCLUDE_SUFFIXES):
        return True
    if path.is_dir() and name in EXCLUDE_DIRS:
        return True
    if any(part in EXCLUDE_DIRS for part in path.parts):
        return True
    return False


def main() -> int:
    DIST_DIR.mkdir(exist_ok=True)
    today = _dt.date.today().strftime("%Y%m%d")
    out = DIST_DIR / f"비전자문서등록_자동입력_v{today}.zip"
    if out.exists():
        out.unlink()

    print("=" * 60)
    print(f"ZIP 패키징: {out.name}")
    print("=" * 60)

    included: list[str] = []
    skipped: list[str] = []
    risky: list[str] = []  # 개인정보 후보 — 발견 시 경고

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(PROJECT_DIR.rglob("*")):
            if path.is_dir():
                continue
            rel = path.relative_to(PROJECT_DIR)

            # 화이트리스트 우선 (top-level 만)
            if rel.parts[0] in INCLUDE_FILES and len(rel.parts) == 1:
                zf.write(path, rel)
                included.append(str(rel))
                continue

            # 제외 대상이면 스킵
            if _should_exclude(rel) or _should_exclude(path):
                skipped.append(str(rel))
                # 개인정보 후보면 strong 경고
                if rel.name in EXCLUDE_EXACT:
                    risky.append(str(rel))
                continue

            # 그 외는 화이트리스트에 없으므로 안전하게 스킵
            skipped.append(str(rel))

    # ── 보고 ──
    print(f"\n[포함된 파일] ({len(included)} 개)")
    for n in included:
        print(f"  ✓ {n}")

    print(f"\n[제외된 파일] ({len(skipped)} 개)")
    for n in skipped[:20]:
        print(f"  - {n}")
    if len(skipped) > 20:
        print(f"  ... 외 {len(skipped) - 20} 개 더")

    if risky:
        print("\n⚠ 위험 파일이 폴더에 있었습니다 (자동 제외됨):")
        for n in risky:
            print(f"  ⚠ {n}")
        print("  → ZIP 에는 안 들어갔지만, 이 파일들이 프로젝트 폴더에 있는 것 자체가 비정상.")
        print("    원래 위치: %USERPROFILE%\\")

    size_mb = out.stat().st_size / 1024 / 1024
    print(f"\n결과: {out}")
    print(f"      {size_mb:.2f} MB, {len(included)} 파일")
    print()
    print("📤 이 ZIP 을 메일/카카오톡/공유드라이브로 전송하세요.")
    print("    받는 사람: 압축 해제 → install.bat 더블클릭.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
