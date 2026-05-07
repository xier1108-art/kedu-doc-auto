"""
오프라인 LLM(Ollama gemma3:4b) 으로 PDF 메타데이터 추출
=========================================================

흐름
----
1) pymupdf 로 PDF 첫 1~2 페이지를 이미지(PNG)로 렌더링
2) Ollama HTTP API 로 gemma3:4b 멀티모달 호출
3) JSON 파싱 → DocMeta

장점: 인터넷/API 키 불필요, 무료
단점: Claude 대비 정확도/속도 ↓ (CPU 추론)
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
from pathlib import Path
from urllib import request, error

import fitz  # pymupdf

from pdf_parser import DocMeta

OLLAMA_URL = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
DEFAULT_MODEL = "gemma3:4b"

PROMPT = """이 이미지는 한국 공문서입니다 (OCR 필요).
본문을 읽고 아래 항목을 JSON으로 정확히 추출하세요.
정보가 없으면 빈 문자열("") 입니다.

```json
{
  "title": "문서 제목",
  "sender": "발신기관",
  "receiver": "수신기관 (예: 서부교육지원청)",
  "doc_no": "문서번호 (예: 2026-84)",
  "date": "시행일자 YYYY-MM-DD",
  "summary": "본문 요지 1~2문장, 100자 이내"
}
```

다른 설명 없이 JSON만 출력."""


def is_available(model: str = DEFAULT_MODEL) -> bool:
    """Ollama 데몬 + 모델 다운로드 여부 확인."""
    try:
        with request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2) as r:
            data = json.loads(r.read())
        names = {m["name"] for m in data.get("models", [])}
        return model in names or any(n.startswith(model.split(":")[0] + ":") for n in names)
    except Exception:
        return False


def render_pdf_to_images(pdf_path: Path, max_pages: int = 2, dpi: int = 200) -> list[bytes]:
    """PDF 의 처음 max_pages 페이지를 PNG bytes 로 변환."""
    images: list[bytes] = []
    with fitz.open(pdf_path) as doc:
        for i, page in enumerate(doc):
            if i >= max_pages:
                break
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            images.append(pix.tobytes("png"))
    return images


def call_gemma(images: list[bytes], model: str = DEFAULT_MODEL,
               prompt: str = PROMPT, timeout: int = 300) -> str:
    """Ollama generate API 호출. 이미지 + 프롬프트 입력 → 텍스트 응답."""
    images_b64 = [base64.b64encode(img).decode("ascii") for img in images]
    payload = {
        "model": model,
        "prompt": prompt,
        "images": images_b64,
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 512},
    }
    req = request.Request(
        f"{OLLAMA_URL}/api/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with request.urlopen(req, timeout=timeout) as r:
            data = json.loads(r.read())
        return data.get("response", "")
    except error.URLError as e:
        raise RuntimeError(f"Ollama 호출 실패: {e}")


def extract_with_ollama(pdf_path: Path, model: str = DEFAULT_MODEL) -> DocMeta | None:
    """오프라인 LLM 으로 PDF 메타데이터 추출. 실패 시 None."""
    if not is_available(model):
        return None

    images = render_pdf_to_images(pdf_path, max_pages=2)
    if not images:
        return None

    text = call_gemma(images, model=model)
    # JSON 추출 (코드 펜스나 부가 텍스트가 섞일 수 있음)
    m = re.search(r"\{[\s\S]*?\}", text)
    if not m:
        raise ValueError(f"LLM 응답에서 JSON 객체를 찾지 못함:\n{text[:500]}")
    try:
        data = json.loads(m.group())
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 파싱 실패: {e}\n응답: {text[:500]}")

    return DocMeta(
        title=str(data.get("title", "")).strip(),
        sender=str(data.get("sender", "")).strip(),
        receiver=str(data.get("receiver", "")).strip(),
        doc_no=str(data.get("doc_no", "")).strip(),
        enforce_date=str(data.get("date", "")).strip(),
        summary=str(data.get("summary", "")).strip(),
        source_file=str(pdf_path),
        notes=[f"Ollama {model} (offline)"],
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python local_extract.py <pdf>")
        print(f"\nis_available({DEFAULT_MODEL}): {is_available(DEFAULT_MODEL)}")
        sys.exit(1)
    m = extract_with_ollama(Path(sys.argv[1]))
    out = Path(__file__).parent / "_local_meta.txt"
    if m:
        out.write_text(str(m), encoding="utf-8")
        print(f"Wrote: {out}")
    else:
        print("Ollama 사용 불가. ollama serve 가 실행 중인지, 모델이 받아졌는지 확인.")
