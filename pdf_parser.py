"""
PDF 파일명/본문에서 비전자문서등록 폼에 필요한 메타데이터를 추출.

지원 파일명 패턴 (한국 공문서 관행)
-----------------------------------
A: "{발신기관}-{문서번호}({YYMMDD}) to{수신기관}_{제목}.pdf"
   예) "중동초-28(260428) to서부교육지원청_서울중동초 근로자 노임관련 조치결과 보고.pdf"

B: "{YY.MM.DD} {발신기관}({학교})제{YYYY}-{seq}호. {제목}.pdf"
   예) "26.04.28 대성(갈현초)제2026-84호. 설계도서 검토서(건축3차) 보고.pdf"

C: "{seq}. {내부번호}-{YYYY}-{문서번호}({YYMMDD}) {제목}.pdf"
   예) "50. 250110-2026-170(260407) 건설환경 악화에 의한 공사비 원가 상승 및 공기 지연 현황 보고.pdf"

D: 단순 제목 — "꿈마루 검토의견서-수정.pdf"

본문에서 추출 시도하는 항목
---------------------------
- 발신기관명 / 수신자 / 문서번호 / 시행일자 / 제목 / 첫 단락(요지)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber


@dataclass
class DocMeta:
    title: str = ""           # 제목 → TITLE
    sender: str = ""          # 발신기관 → DRFTINSTTNM, DSPTCHNMCN, ORGDRAFTDEPTNAME
    receiver: str = ""        # 수신 → RECEIVERNAME
    doc_no: str = ""          # 문서번호 → DOCREGNO
    enforce_date: str = ""    # 시행일자 (YYYY-MM-DD) → ENFORCEDATE
    summary: str = ""         # 문서요지 → docOutline
    source_file: str = ""     # 원본 PDF 경로
    notes: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        lines = ["DocMeta {"]
        for k, v in self.__dict__.items():
            if k == "notes":
                continue
            lines.append(f"  {k:14} = {v!r}")
        if self.notes:
            lines.append(f"  notes        = {self.notes}")
        lines.append("}")
        return "\n".join(lines)


# ---------- 날짜 파서 ----------

def _to_iso_date(raw: str) -> str:
    """다양한 날짜 표기를 YYYY-MM-DD 로 정규화."""
    raw = raw.strip()
    # YYMMDD (6자리)
    m = re.fullmatch(r"(\d{2})(\d{2})(\d{2})", raw)
    if m:
        yy, mm, dd = m.groups()
        return f"20{yy}-{mm}-{dd}"
    # YY.MM.DD
    m = re.fullmatch(r"(\d{2})\.(\d{1,2})\.(\d{1,2})", raw)
    if m:
        yy, mm, dd = m.groups()
        return f"20{yy}-{int(mm):02d}-{int(dd):02d}"
    # YYYY-MM-DD
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", raw)
    if m:
        return raw
    # YYYY.MM.DD
    m = re.fullmatch(r"(\d{4})\.(\d{1,2})\.(\d{1,2})\.?", raw)
    if m:
        y, mm, dd = m.groups()
        return f"{y}-{int(mm):02d}-{int(dd):02d}"
    return ""


# ---------- 파일명 패턴 매칭 ----------

PAT_A = re.compile(
    r"^(?P<sender>[^\-_/\\]+)"
    r"-(?P<seq>\d+)"
    r"\((?P<date>\d{6})\)"
    r"\s*to(?P<recv>[^_]+)"
    r"_(?P<title>.+)$"
)

PAT_B = re.compile(
    r"^(?P<date>\d{2}\.\d{1,2}\.\d{1,2})\s+"
    r"(?P<sender>[^()]+?)"
    r"(?:\((?P<school>[^)]+)\))?"
    r"제(?P<year>\d{4})-(?P<seq>\d+)호\.?\s*"
    r"(?P<title>.+)$"
)

PAT_C = re.compile(
    r"^\d+\.\s+"
    r"\d+-(?P<year>\d{4})-(?P<seq>\d+)"
    r"\((?P<date>\d{6})\)\s+"
    r"(?P<title>.+)$"
)


def parse_filename(stem: str) -> DocMeta:
    m = PAT_A.match(stem)
    if m:
        return DocMeta(
            sender=m["sender"].strip(),
            receiver=m["recv"].strip(),
            doc_no=m["seq"],
            enforce_date=_to_iso_date(m["date"]),
            title=m["title"].strip(),
            notes=["filename pattern A"],
        )
    m = PAT_B.match(stem)
    if m:
        sender = m["sender"].strip()
        if m["school"]:
            sender = f"{sender}({m['school']})"
        return DocMeta(
            sender=sender,
            doc_no=f"{m['year']}-{m['seq']}",
            enforce_date=_to_iso_date(m["date"]),
            title=m["title"].strip(),
            notes=["filename pattern B"],
        )
    m = PAT_C.match(stem)
    if m:
        return DocMeta(
            doc_no=f"{m['year']}-{m['seq']}",
            enforce_date=_to_iso_date(m["date"]),
            title=m["title"].strip(),
            notes=["filename pattern C"],
        )
    # fallback: 전체 파일명을 제목으로
    return DocMeta(title=stem, notes=["filename pattern D (no metadata)"])


# ---------- PDF 본문 파싱 ----------

_DOC_NO_RE = re.compile(r"문서번호\s*[:：]?\s*([0-9가-힣()A-Za-z\-]+)")
_TITLE_RE = re.compile(r"제\s*목\s*[:：]?\s*([^\n]+)")
_SENDER_RE = re.compile(r"(발신|보낸이|발신명의|기관명)\s*[:：]?\s*([^\n]+)")
_RECEIVER_RE = re.compile(r"수\s*신\s*[:：]?\s*([^\n]+)")
_DATE_RE = re.compile(r"시행일자?\s*[:：]?\s*(\d{4}[\.\-]\d{1,2}[\.\-]\d{1,2}\.?)")


def parse_pdf_body(pdf_path: Path, meta: DocMeta) -> DocMeta:
    """본문에서 비어있는 항목을 보충."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages[:2]:  # 처음 2페이지면 충분
                text += (page.extract_text() or "") + "\n"
    except Exception as e:
        meta.notes.append(f"PDF parse error: {e}")
        return meta

    text = text.strip()
    if not text:
        meta.notes.append("PDF has no extractable text (스캔 PDF로 추정)")
        return meta

    if not meta.title:
        m = _TITLE_RE.search(text)
        if m:
            meta.title = m.group(1).strip()
    if not meta.sender:
        m = _SENDER_RE.search(text)
        if m:
            meta.sender = m.group(2).strip()
    if not meta.receiver:
        m = _RECEIVER_RE.search(text)
        if m:
            meta.receiver = m.group(1).strip().split()[0]  # 첫 단어만
    if not meta.doc_no:
        m = _DOC_NO_RE.search(text)
        if m:
            meta.doc_no = m.group(1).strip()
    if not meta.enforce_date:
        m = _DATE_RE.search(text)
        if m:
            meta.enforce_date = _to_iso_date(m.group(1))

    # 요지: 본문 첫 단락 (제목 줄 제외)
    if not meta.summary:
        # 제목 줄 다음 첫 100~200자
        summary_text = text
        if meta.title and meta.title in summary_text:
            summary_text = summary_text.split(meta.title, 1)[-1]
        # 빈 줄 무시하고 첫 의미있는 단락
        for para in re.split(r"\n\s*\n", summary_text):
            para = para.strip().replace("\n", " ")
            if len(para) >= 20 and not para.startswith("문서번호"):
                meta.summary = para[:200]
                break

    return meta


def extract(pdf_path: str | Path) -> DocMeta:
    """PDF 경로를 받아 파일명 + 본문 양쪽에서 메타데이터 추출."""
    p = Path(pdf_path)
    if not p.exists():
        raise FileNotFoundError(p)
    meta = parse_filename(p.stem)
    meta.source_file = str(p)
    meta = parse_pdf_body(p, meta)
    return meta


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        m = extract(sys.argv[1])
    else:
        # 데모: 다운로드 폴더에서 가장 최근 PDF
        downloads = Path.home() / "Downloads"
        latest = max(downloads.glob("*.pdf"), key=lambda p: p.stat().st_mtime)
        print(f"[Latest PDF] {latest.name}\n")
        m = extract(latest)

    out = Path(__file__).parent / "_pdf_meta.txt"
    out.write_text(str(m), encoding="utf-8")
    print(f"Wrote: {out}")
