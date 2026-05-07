"""
K-에듀파인 비전자문서등록 자동 입력 메인 스크립트
================================================

사용법
------
    python auto_fill.py <PDF경로>
    python auto_fill.py                    # 다운로드 폴더에서 가장 최근 PDF
    python auto_fill.py --dry-run <PDF>    # 폼에 입력하지 않고 추출 결과만 출력

동작
----
1) 비전자문서등록 창(WXSClient.exe)에 연결
2) 사용자 기본값 자동 적용 (대국민공개여부=비공개, 5호 등)
3) PDF 파일명 + 본문에서 메타데이터 추출
4) 폼에 일괄 입력 (저장 버튼은 누르지 않음 - 사용자가 검토 후 직접 클릭)

기본값 (DEFAULTS 상수에서 변경 가능)
"""
from __future__ import annotations

import sys
from pathlib import Path

from ai_extract import extract_smart
from pdf_parser import DocMeta
from wxs_form import WXSForm
import taskcard
import user as user_mod


# ─────────────────────────────────────────────
# 사용자 기본값 (요청에 따라 항상 적용)
# ─────────────────────────────────────────────
USER_NAME = "김상현"

DEFAULTS = {
    # 대국민공개여부 = 비공개
    "radio_PUBLICATION":   "PUBLICATION2",
    # 공개제한근거 = 5호
    "check_ho":            ["ho5"],
    # 직원열람범위 = 기관
    "radio_readngScope":   "readngScope1",
    # 직원열람제한 = 설정안함
    "radio_SECURITY":      "SECURITY0",
    # 등록구분 = 접수
    "radio_R_SENDRECEIVE": "SENDRECEIVE2",
    # 접수자 / 업무담당자
    "DRAFTERNAME":         USER_NAME,
    "LASTSIGNERNAME":      USER_NAME,
}

TASK_CARD_HINT = "[교육시설공사집행관리] 교육시설공사집행관리"
# 과제카드는 K-에듀파인 자체 팝업 검색이 필요한 항목이라
# JS 한 줄로 강제 설정하기 어렵습니다. 폼 상에 이미 셋업되어 있으면 그대로 유지됩니다.


# ─────────────────────────────────────────────
# 메인 로직
# ─────────────────────────────────────────────
def apply_defaults(f: WXSForm) -> list[str]:
    """기본값 항목들을 폼에 적용. 적용/실패 항목 리스트 반환."""
    log: list[str] = []
    try:
        f.set_radio("PUBLICATION", DEFAULTS["radio_PUBLICATION"])
        log.append("✓ 대국민공개여부 = 비공개")
    except Exception as e:
        log.append(f"✗ 대국민공개여부: {e}")

    for ho in DEFAULTS["check_ho"]:
        try:
            f.check(ho, True)
            log.append(f"✓ 공개제한근거 {ho} 체크")
        except Exception as e:
            log.append(f"✗ {ho}: {e}")

    try:
        f.set_radio("readngScope", DEFAULTS["radio_readngScope"])
        log.append("✓ 직원열람범위 = 기관")
    except Exception as e:
        log.append(f"✗ 직원열람범위: {e}")

    try:
        f.set_radio("SECURITY", DEFAULTS["radio_SECURITY"])
        log.append("✓ 직원열람제한 = 설정안함")
    except Exception as e:
        log.append(f"✗ 직원열람제한: {e}")

    try:
        f.set_radio("R_SENDRECEIVE", DEFAULTS["radio_R_SENDRECEIVE"])
        log.append("✓ 등록구분 = 접수")
    except Exception as e:
        log.append(f"✗ 등록구분: {e}")

    # 접수자 / 업무담당자 — 저장된 사용자 정보 (모든 hidden 필드 포함) 복원
    saved_user = user_mod.load()
    if user_mod.is_valid(saved_user):
        try:
            user_mod.apply(f, saved_user)
            log.append(f"✓ 접수자/업무담당자 = {user_mod.summary(saved_user)}")
        except Exception as e:
            log.append(f"✗ 사용자 정보 적용: {e}")
    else:
        # fallback: 이름만 표시 (검증은 통과 못함)
        try:
            f.set_value("DRAFTERNAME", DEFAULTS["DRAFTERNAME"])
            f.set_value("LASTSIGNERNAME", DEFAULTS["LASTSIGNERNAME"])
            log.append(f"⚠ 사용자 이름만 입력 (저장된 ID 없음 → '부서 불일치' 오류 발생 가능)")
            log.append("   → GUI 의 [👤 사용자 저장] 으로 실제 ID 1회 캡처 필요")
        except Exception as e:
            log.append(f"✗ 사용자 이름 입력: {e}")

    return log


def apply_taskcard(f: WXSForm) -> list[str]:
    """저장된 과제카드를 폼에 적용. 다른 set_value 들 다 끝난 뒤 마지막에 호출."""
    log: list[str] = []
    saved = taskcard.load()
    if not taskcard.is_valid(saved):
        log.append("- 과제카드: 저장된 값 없음 (GUI 의 [📌 과제카드 저장] 버튼으로 1회 캡처 필요)")
        return log
    # 시도를 두 번 — 첫 시도가 화면 갱신 안되는 IE quirk 대응
    import time
    for attempt in (1, 2):
        try:
            ok = taskcard.apply(f, saved)
            time.sleep(0.15)  # IE 렌더링 reflow 대기
            after = taskcard.capture(f)
            if taskcard.is_valid(after):
                log.append(f"✓ 과제카드 = {taskcard.summary(saved)}"
                           + ("" if attempt == 1 else f" (재시도 {attempt} 회 성공)"))
                log.append(f"  └ DOM 확인 OK ({len(after['cards'])} 개 카드)")
                return log
        except Exception as e:
            log.append(f"  시도 {attempt} 예외: {e}")
        time.sleep(0.2)
    log.append("✗ 과제카드 2회 시도 후에도 DOM 에 반영 안 됨 (페이지 새로고침 필요할 수 있음)")
    return log


def apply_pdf(f: WXSForm, meta: DocMeta) -> list[str]:
    """PDF에서 추출한 메타데이터를 폼에 적용."""
    log: list[str] = []

    mapping = [
        ("TITLE",            meta.title,        "제목"),
        ("DRFTINSTTNM",      meta.sender,       "발신기관명"),
        ("DSPTCHNMCN",       meta.sender,       "발신명의"),
        ("ORGDRAFTDEPTNAME", meta.sender,       "원기안(발신)부서"),
        ("DOCREGNO",         meta.doc_no,       "생산기관문서번호"),
        ("ENFORCEDATE",      meta.enforce_date, "시행일자"),
        ("RECEIVERNAME",     meta.receiver,     "수신자명"),
        ("docOutline",       meta.summary,      "문서요지"),
    ]
    for field_id, value, label in mapping:
        if not value:
            log.append(f"  - {label}: (PDF에서 추출 안 됨, 건너뜀)")
            continue
        try:
            f.set_value(field_id, value)
            log.append(f"✓ {label} = {value!r}")
        except Exception as e:
            log.append(f"✗ {label}: {e}")

    # PDF 의 페이지 수 → PAGECNT
    if meta.source_file:
        try:
            from pathlib import Path
            import fitz
            with fitz.open(Path(meta.source_file)) as doc:
                pages = len(doc)
            f.set_value("PAGECNT", str(pages))
            log.append(f"✓ 쪽수 (PAGECNT) = {pages}")
        except Exception as e:
            log.append(f"✗ 쪽수: {e}")

    return log


def find_target_pdf(arg: str | None) -> Path:
    if arg:
        p = Path(arg)
        if not p.exists():
            print(f"파일을 찾을 수 없습니다: {p}", file=sys.stderr)
            sys.exit(1)
        return p
    downloads = Path.home() / "Downloads"
    pdfs = list(downloads.glob("*.pdf"))
    if not pdfs:
        print("다운로드 폴더에 PDF가 없습니다. 인자로 PDF 경로를 지정하세요.", file=sys.stderr)
        sys.exit(1)
    return max(pdfs, key=lambda p: p.stat().st_mtime)


def main() -> int:
    args = sys.argv[1:]
    dry_run = "--dry-run" in args
    if dry_run:
        args.remove("--dry-run")
    pdf_arg = args[0] if args else None
    pdf = find_target_pdf(pdf_arg)

    print("┌─ 입력 PDF ───────────────────────")
    print(f"│ {pdf.name}")
    print("└──────────────────────────────────")

    meta = extract_smart(pdf)
    print(meta)
    print()

    if dry_run:
        print("[--dry-run] 폼에는 입력하지 않습니다.")
        return 0

    print("┌─ 비전자문서등록 폼 연결 ─────────")
    try:
        f = WXSForm.attach()
        print(f"│ ✓ {f.doc.title}")
    except Exception as e:
        print(f"│ ✗ {e}")
        print("│   비전자문서등록 창을 먼저 열어주세요.")
        return 2
    print("└──────────────────────────────────\n")

    print("┌─ 기본값 적용 ────────────────────")
    for line in apply_defaults(f):
        print(f"│ {line}")
    print("└──────────────────────────────────\n")

    print("┌─ PDF 데이터 적용 ────────────────")
    for line in apply_pdf(f, meta):
        print(f"│ {line}")
    print("└──────────────────────────────────\n")

    print("✅ 자동 입력 완료. 화면에서 확인 후 [저장] 버튼을 클릭해주세요.")
    print("   ※ 과제카드명/접수자ID는 K-에듀파인 자체 팝업이 필요할 수 있습니다.")
    print("     이미 셋업된 경우 그대로 유지됩니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
