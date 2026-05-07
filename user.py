"""
사용자(접수자/업무담당자) 정보 자동 입력 모듈
================================================

K-에듀파인 비전자문서등록 폼에서 접수자/업무담당자 필드는 readonly text +
검색 팝업(fncSearchUser)으로만 설정 가능하다. 우리는 직접 텍스트 입력 못 함.

문제: 자동 입력 시 DRAFTERID/LASTSIGNERID 가 placeholder("000000000000000")
      → "등록자와 기안자/접수자의 부서가 일치하지 않습니다" 오류

전략: 과제카드와 동일.
  ① 사용자가 1번만 폼의 🔍 버튼으로 자기 자신을 선택하면 hidden 필드들이
     실제 ID/부서 정보로 채워짐
  ② 그 시점의 값들을 캡처 → ~/.kedu_user.json 에 저장
  ③ 이후 자동 입력 시 모든 hidden 필드를 저장된 값으로 복원

저장 위치: %USERPROFILE%\\.kedu_user.json
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wxs_form import WXSForm, MSHTML

CONFIG_PATH = Path.home() / ".kedu_user.json"

# 캡처/복원 대상 필드 — readonly text + 그에 딸린 hidden 들
USER_FIELDS = [
    # 접수자 (Drafter)
    "DRAFTERNAME",          # text (표시)
    "DRAFTERID",            # hidden (검증용 ID)
    "DRAFTER_DEPT_ID",      # hidden (부서 ID)
    "DRAFTER_DEPT_NM",      # hidden (부서명)
    "DRAFTER_POSITION_NM",  # hidden (직위명)

    # 업무담당자 (LastSigner)
    "LASTSIGNERNAME",
    "LASTSIGNERID",
    "LASTSIGNER_DEPT_ID",
    "LASTSIGNER_DEPT_NM",
    "LASTSIGNER_POSITION_NM",
]

# placeholder 값들 — 이 값이면 사용자가 아직 검색 안 한 상태
_PLACEHOLDER_IDS = {"000000000000000", "0", ""}


def _read_input(form: WXSForm, element_id: str) -> str | None:
    """input 의 value 를 IHTMLInputElement 로 안전히 읽기."""
    try:
        el = form.get_element(element_id)
    except KeyError:
        return None
    try:
        inp = el.QueryInterface(MSHTML.IHTMLInputElement)
        return inp.value or ""
    except Exception:
        return None


def capture(form: WXSForm) -> dict[str, Any]:
    """현재 폼의 사용자/부서 값들을 dict 로 추출."""
    data: dict[str, Any] = {}
    for fid in USER_FIELDS:
        v = _read_input(form, fid)
        if v is not None:
            data[fid] = v
    return data


def save(data: dict[str, Any], path: Path = CONFIG_PATH) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load(path: Path = CONFIG_PATH) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def is_valid(data: dict[str, Any] | None) -> bool:
    """저장된 데이터가 유효한지 — DRAFTERID 가 placeholder 가 아니어야."""
    if not data:
        return False
    did = data.get("DRAFTERID", "")
    return bool(did) and did not in _PLACEHOLDER_IDS


def summary(data: dict[str, Any] | None) -> str:
    """한 줄 요약 (GUI 라벨용)."""
    if not is_valid(data):
        return "(저장된 사용자 없음)"
    name = data.get("DRAFTERNAME", "?")
    dept = data.get("DRAFTER_DEPT_NM", "")
    pos = data.get("DRAFTER_POSITION_NM", "")
    parts = [name]
    extra = " ".join(p for p in (dept, pos) if p)
    if extra:
        parts.append(f"({extra})")
    return " ".join(parts)


def apply(form: WXSForm, data: dict[str, Any] | None = None) -> bool:
    """저장된 사용자 정보를 폼의 모든 hidden 필드에 복원. 성공 시 True."""
    if data is None:
        data = load()
    if not is_valid(data):
        return False

    for fid in USER_FIELDS:
        if fid not in data:
            continue
        val = data[fid]
        try:
            form.set_value(fid, str(val))
        except Exception:
            pass  # 일부 필드 실패해도 다른 건 진행
    return True


# ──────────────── CLI ────────────────

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    f = WXSForm.attach()

    if cmd == "capture":
        data = capture(f)
        if not is_valid(data):
            print("✗ 폼에 선택된 사용자가 없습니다 (DRAFTERID 가 placeholder).")
            print("  접수자 옆 🔍 으로 자기 자신을 한 번 선택한 뒤 다시 실행하세요.")
            sys.exit(1)
        save(data)
        print(f"✅ 저장됨: {CONFIG_PATH}")
        print(f"   → {summary(data)}")
    elif cmd == "apply":
        if not apply(f):
            print("✗ 저장된 사용자가 없습니다. 먼저 'python user.py capture' 실행.")
            sys.exit(1)
        print("✅ 적용 완료")
    elif cmd == "show":
        cur = capture(f)
        print(f"[현재 폼]")
        print(json.dumps(cur, ensure_ascii=False, indent=2))
        print(f"\n[저장됨]   {summary(load())}")
    elif cmd == "clear":
        if CONFIG_PATH.exists():
            CONFIG_PATH.unlink()
            print(f"✅ 삭제: {CONFIG_PATH}")
        else:
            print("(저장된 사용자 없음)")
    else:
        print("Usage: python user.py [capture | apply | show | clear]")
