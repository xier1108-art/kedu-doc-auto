"""
OCR + 텍스트 LLM 분리 파이프라인 (오프라인)
=============================================

발상: vision-LLM 한 번에 다 시키지 말고
      ① 전문 OCR(EasyOCR) 으로 텍스트만 빠르게 추출
      ② 작은 텍스트 LLM(gemma3:4b 텍스트 모드) 으로 의미 분류

산업 표준 패턴 (Google Document AI / AWS Textract 등도 동일).

장점
----
- 속도: 비전 인코더 우회 → CPU에서 5~10배 빠름
- 정확도: 한국어 OCR은 EasyOCR 이 작은 멀티모달 LLM 보다 우수
- 모듈화: OCR / LLM 독립적으로 교체 가능
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib import request

import fitz  # pymupdf

from pdf_parser import DocMeta

OLLAMA_URL = "http://localhost:11434"
DEFAULT_MODEL = "gemma3:4b"  # 텍스트 모드로만 사용

_reader = None  # lazy singleton


def _get_reader():
    """EasyOCR Reader 싱글톤. 첫 호출 시 모델 다운로드 (~150MB)."""
    global _reader
    if _reader is None:
        import easyocr
        _reader = easyocr.Reader(["ko", "en"], gpu=False, verbose=False)
    return _reader


# ──────────────────────────────────────────────
# 1단계: PDF → 텍스트 (EasyOCR)
# ──────────────────────────────────────────────

def _format_pages(pages_text: list[str]) -> str:
    """페이지 구분을 명확히 표시한 단일 문자열로 합침."""
    parts = []
    for i, t in enumerate(pages_text, start=1):
        parts.append(f"━━━ 페이지 {i} ━━━\n{t}")
    return "\n\n".join(parts)


def pdf_to_text(pdf_path: Path, max_pages: int = 2, dpi: int = 200) -> tuple[str, dict]:
    """
    PDF 첫 max_pages 를 OCR. 디지털 PDF면 pdfplumber 우선, 안되면 EasyOCR.
    반환: (페이지 구분된 텍스트, 메타정보)
    """
    meta = {"ocr_engine": None, "pages": 0, "ocr_seconds": 0.0}

    # 시도 1: pdfplumber
    try:
        import pdfplumber
        with pdfplumber.open(pdf_path) as pdf:
            texts: list[str] = []
            for i, page in enumerate(pdf.pages):
                if i >= max_pages:
                    break
                t = (page.extract_text() or "").strip()
                if t:
                    texts.append(t)
            if texts:
                meta["ocr_engine"] = "pdfplumber (digital PDF)"
                meta["pages"] = len(texts)
                return _format_pages(texts), meta
    except Exception:
        pass

    # 시도 2: EasyOCR (스캔 PDF)
    t0 = time.time()
    reader = _get_reader()
    pages_text: list[str] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            results = reader.readtext(pix.tobytes("png"), detail=0, paragraph=True)
            pages_text.append("\n".join(results))
    meta["ocr_engine"] = "EasyOCR (ko+en)"
    meta["pages"] = len(pages_text)
    meta["ocr_seconds"] = round(time.time() - t0, 1)
    return _format_pages(pages_text), meta


# ──────────────────────────────────────────────
# 2단계: 텍스트 → JSON (gemma3:4b 텍스트 모드)
# ──────────────────────────────────────────────

PROMPT_TEMPLATE = """한국 공공기관 접수용 문서 OCR 결과를 분석해 메타데이터를 JSON 으로 추출.
유형은 두 가지:
  [A] 일반 공문 (수신/참조/제목/시행 양식)
  [B] 조달청 검사검수요청서 등 나라장터 양식

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 1단계: 표지 페이지 + 유형 식별
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[A 유형 — 일반 공문] 표지 결정 패턴:
  ✓ "수신:", "참조:", "제목:" 라벨
  ✓ 하단 "시행 {{회사}}({{학교}})제YYYY-N호({{날짜}})" 줄
  ✓ "끝." + 직인 위치

[B 유형 — 검사검수요청서] 표지 결정 패턴:
  ✓ "검사검수요청서" 큰 헤더 (또는 "검 사 검 수 요 청 서")
  ✓ "※나라장터전자문서출력물"
  ✓ [공공기관] / [납품업체] 박스 + "검사검수요청번호:", "계약건명:" 라벨

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 2단계: 유형별 추출 규칙
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

═══════ [A 유형 — 일반 공문] ═══════
[발신자] 표지 최상단 회사명. ✗ 본문 인용 "설계사공문: DNB ..." 아님.
[제목] "제목:" 줄, 짧고 문서 유형 (보고/회신/제출 등). ✗ 본문 큰 공사명 아님.
[문서번호] 하단 "시행" 줄 본인 번호 (예: "대성(갈현초)제2026-84호").
[수신자] "수신:" 직위 제거 (서부교육지원청장 → 서부교육지원청).
[요지] 본문 1~2문장(100자).

═══════ [B 유형 — 검사검수요청서] ═══════
[제목] "검사검수요청서[{{계약건명}}]" 형식. 금액 절대 포함 X.
  예: "검사검수요청서[갈현초그린스마트미래학교및복합화증개축관급자재(레미콘-1차)]"
[발신자] "[납품업체]" 박스의 "업 체 명:" 옆 회사명
  ✗ "[공공기관]" / "[실제납품업체]" 아님. 예: "경기서북부레미콘사업협동조합".
[수신자] "[공공기관]" 박스의 "기 관 명:" 옆 기관명
  ✂ "서울특별시교육청서울특별시서부교육지원청" → "서울특별시서부교육지원청"
[문서번호] "검사검수요청번호:" 옆 값 (예: "R26NQ05390037-000")
  ✗ "계약번호", "납품요구번호" 아님.
[시행일자] "작성일자:" 옆 날짜 → YYYY-MM-DD
  ✗ "검사요청일자", "검수요청일자" 아님.
[요지] 빈 문자열 "" (사용자 지시).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[OCR 텍스트 — 페이지 구분 포함]
{ocr_text}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[출력] JSON 한 객체만:
{{
  "cover_page": 1,    // 표지 페이지. 없으면 0
  "doc_type": "A" 또는 "B",   // A: 공문, B: 검사검수요청서
  "title": "...",
  "sender": "...",
  "receiver": "...",
  "doc_no": "...",
  "date": "YYYY-MM-DD",
  "summary": "..."
}}

표지 식별 안되면 cover_page=0, doc_type="?", 나머지 빈 문자열.
파일명({filename}) 은 회사마다 임의로 짓는 경우 있으므로 PDF 본문 우선."""


def text_to_json(ocr_text: str, filename: str = "", model: str = DEFAULT_MODEL,
                 timeout: int = 120) -> dict:
    """OCR 결과 텍스트 → 구조화된 dict. Ollama 텍스트 추론."""
    prompt = PROMPT_TEMPLATE.format(ocr_text=ocr_text[:6000], filename=filename)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 600},
        "format": "json",  # Ollama 가 JSON 강제 출력
    }
    req = request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())

    text = data.get("response", "").strip()
    # format=json 옵션이면 보통 직접 JSON, 아니면 추출
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            return json.loads(m.group())
        raise ValueError(f"LLM 응답 JSON 파싱 실패: {text[:300]}")


# ──────────────────────────────────────────────
# 통합 진입점
# ──────────────────────────────────────────────

def is_available(model: str = DEFAULT_MODEL) -> bool:
    """Ollama + EasyOCR 사용 가능 여부."""
    try:
        with request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2) as r:
            data = json.loads(r.read())
        names = {m["name"] for m in data.get("models", [])}
        if model not in names and not any(n.startswith(model.split(":")[0] + ":") for n in names):
            return False
    except Exception:
        return False
    try:
        import easyocr  # noqa
    except ImportError:
        return False
    return True


def extract_with_ocr_llm(pdf_path: Path, model: str = DEFAULT_MODEL,
                         max_pages: int = 2) -> tuple[DocMeta | None, dict]:
    """
    PDF → OCR → LLM JSON 추출.
    반환: (DocMeta, 통계dict). 실패 시 (None, {error: ...}).
    """
    stats: dict = {}
    if not is_available(model):
        return None, {"error": "Ollama 또는 EasyOCR 사용 불가"}

    t_total = time.time()

    # 1단계: OCR
    text, ocr_meta = pdf_to_text(pdf_path, max_pages=max_pages)
    stats.update(ocr_meta)
    if not text.strip():
        return None, {**stats, "error": "OCR 결과 텍스트 없음"}
    stats["ocr_chars"] = len(text)

    # 2단계: 텍스트 LLM
    t_llm = time.time()
    try:
        data = text_to_json(text, filename=pdf_path.name, model=model)
    except Exception as e:
        return None, {**stats, "error": f"LLM 파싱 실패: {e}"}
    stats["cover_page"] = data.get("cover_page", 0)
    stats["llm_seconds"] = round(time.time() - t_llm, 1)
    stats["total_seconds"] = round(time.time() - t_total, 1)

    meta = DocMeta(
        title=str(data.get("title", "")).strip(),
        sender=str(data.get("sender", "")).strip(),
        receiver=str(data.get("receiver", "")).strip(),
        doc_no=str(data.get("doc_no", "")).strip(),
        enforce_date=str(data.get("date", "")).strip(),
        summary=str(data.get("summary", "")).strip(),
        source_file=str(pdf_path),
        notes=[
            f"OCR: {ocr_meta['ocr_engine']} ({ocr_meta.get('ocr_seconds', '?')}s)",
            f"LLM: {model} ({stats['llm_seconds']}s)",
            f"총 {stats['total_seconds']}s",
        ],
    )
    return meta, stats


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ocr_extract.py <pdf>")
        sys.exit(1)
    meta, stats = extract_with_ocr_llm(Path(sys.argv[1]))
    out = Path(__file__).parent / "_ocr_meta.txt"
    if meta:
        out.write_text(str(meta) + "\n\nStats:\n" + json.dumps(stats, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    else:
        out.write_text("FAILED\n" + json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote: {out}")
