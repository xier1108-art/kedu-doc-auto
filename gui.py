"""
비전자문서등록 자동입력 GUI
============================
- PDF 파일을 창에 드래그 → 자동 추출 → (필요하면 값 수정) → 폼에 일괄 입력
- 파일 선택 버튼도 지원
- API 키 설정 다이얼로그 내장

실행:
    pythonw gui.py [PDF경로]
또는 바탕화면 바로가기 더블클릭, 우클릭 [Send to → 비전자문서등록]
"""
from __future__ import annotations

import dataclasses
import re
import sys
import threading
import traceback
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

from ai_extract import (
    extract_smart, get_api_key, save_api_key,
    list_available_models, get_model, save_model_id,
    get_model_label, TIER_HINT,
)
from auto_fill import apply_defaults, apply_pdf, apply_taskcard
from wxs_form import WXSForm

import taskcard
import user as user_mod

# 추출 결과 → 사용자가 고칠 수 있는 입력칸 (DocMeta 속성, 화면 이름, 폼에 들어가는 곳)
FIELDS = [
    ("title",        "제목",     "제목"),
    ("sender",       "발신기관", "발신기관명 · 발신명의 · 원기안부서"),
    ("receiver",     "수신자",   "수신자명"),
    ("doc_no",       "문서번호", "생산기관문서번호"),
    ("enforce_date", "시행일자", "YYYY-MM-DD"),
]
EMPTY_BG = "#fff4e5"   # 값이 비어 있는 칸 (확인 필요)
NORMAL_BG = "white"


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("비전자문서등록 자동입력")
        root.geometry("760x600")
        root.minsize(640, 520)

        self._extracted_meta = None
        self._extracted_path: Path | None = None
        self._busy = False

        self._build_ui()
        self._update_api_status()

        # CLI 인자로 받은 PDF 가 있으면 즉시 처리
        if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
            self.root.after(300, lambda: self.process_pdf(sys.argv[1]))

    # ──────────────── UI ────────────────

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        # 상단 타이틀
        top = ttk.Frame(self.root)
        top.pack(fill=tk.X, **pad)
        ttk.Label(top, text="📄 비전자문서등록 자동입력", font=("맑은 고딕", 14, "bold")).pack(side=tk.LEFT)
        ttk.Button(top, text="⚙ 설정", width=8, command=self.open_settings).pack(side=tk.RIGHT, padx=4)

        self.api_label = ttk.Label(self.root, text="", foreground="gray", font=("맑은 고딕", 9))
        self.api_label.pack(anchor=tk.W, padx=10, pady=(2, 0))

        # 드래그앤드롭 영역
        self.drop_frame = tk.Frame(self.root, bg="#eef4fb", relief="ridge", bd=2)
        self.drop_frame.pack(fill=tk.X, **pad)
        msg = "여기에 PDF 파일을 끌어다 놓으세요" if HAS_DND else "[파일 선택] 버튼으로 PDF를 골라주세요"
        self.drop_label = tk.Label(self.drop_frame, text=msg,
                                   bg="#eef4fb", fg="#356", font=("맑은 고딕", 11),
                                   pady=20)
        self.drop_label.pack(fill=tk.X)
        if HAS_DND:
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind("<<Drop>>", self.on_drop)
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind("<<Drop>>", self.on_drop)

        # 액션 버튼
        action = ttk.Frame(self.root)
        action.pack(fill=tk.X, **pad)
        self.pick_btns = [
            ttk.Button(action, text="📁 PDF 파일 선택", command=self.choose_file),
            ttk.Button(action, text="🗂 다운로드 폴더에서 최근 PDF", command=self.choose_latest),
        ]
        self.pick_btns[0].pack(side=tk.LEFT)
        self.pick_btns[1].pack(side=tk.LEFT, padx=6)

        # 저장된 과제카드 / 사용자 (한 줄씩)
        saved = ttk.LabelFrame(self.root, text="매번 자동으로 넣는 값")
        saved.pack(fill=tk.X, padx=10, pady=(2, 4))
        row1 = ttk.Frame(saved)
        row1.pack(fill=tk.X, padx=6, pady=(4, 2))
        self.tc_label = ttk.Label(row1, text="", foreground="gray", font=("맑은 고딕", 9))
        self.tc_label.pack(side=tk.LEFT)
        ttk.Button(row1, text="📌 과제카드 저장", command=self.save_taskcard).pack(side=tk.RIGHT)
        row2 = ttk.Frame(saved)
        row2.pack(fill=tk.X, padx=6, pady=(2, 6))
        self.user_label = ttk.Label(row2, text="", foreground="gray", font=("맑은 고딕", 9))
        self.user_label.pack(side=tk.LEFT)
        ttk.Button(row2, text="👤 사용자 저장", command=self.save_user).pack(side=tk.RIGHT)
        self._refresh_tc_label()
        self._refresh_user_label()

        # 추출 결과 — 직접 고칠 수 있는 입력칸
        head = ttk.Frame(self.root)
        head.pack(fill=tk.X, padx=10, pady=(8, 2))
        ttk.Label(head, text="추출 결과", font=("맑은 고딕", 10, "bold")).pack(side=tk.LEFT)
        ttk.Label(head, text="  틀린 값은 여기서 바로 고친 뒤 입력하세요",
                  foreground="gray", font=("맑은 고딕", 9)).pack(side=tk.LEFT)

        # 어떤 방식으로 추출됐는지 (Claude 실패 → 규칙 추출이면 눈에 띄게 경고)
        self.source_label = tk.Label(self.root, text="", anchor="w", justify="left",
                                     font=("맑은 고딕", 9), wraplength=720)
        self.source_label.pack(fill=tk.X, padx=10)

        form = ttk.Frame(self.root)
        form.pack(fill=tk.X, padx=10, pady=(4, 0))
        form.columnconfigure(1, weight=1)
        self.vars: dict[str, tk.StringVar] = {}
        self.entries: dict[str, tk.Entry] = {}
        for r, (key, label, hint) in enumerate(FIELDS):
            ttk.Label(form, text=label, width=9).grid(row=r, column=0, sticky="w", pady=2)
            var = tk.StringVar()
            ent = tk.Entry(form, textvariable=var, font=("맑은 고딕", 10),
                           relief="solid", bd=1, state="disabled")
            ent.grid(row=r, column=1, sticky="ew", pady=2)
            ttk.Label(form, text=hint, foreground="gray", font=("맑은 고딕", 8)).grid(
                row=r, column=2, sticky="w", padx=(6, 0))
            var.trace_add("write", lambda *_a, e=ent, v=var: self._mark_empty(e, v))
            self.vars[key] = var
            self.entries[key] = ent

        # 적용 버튼 + 진행 표시
        bottom = ttk.Frame(self.root)
        bottom.pack(fill=tk.X, **pad)
        self.apply_btn = ttk.Button(bottom, text="✅ 비전자문서등록 폼에 입력",
                                    command=self.on_apply, state=tk.DISABLED)
        self.apply_btn.pack(side=tk.LEFT)
        self.status = ttk.Label(bottom, text="대기 중", foreground="gray")
        self.status.pack(side=tk.LEFT, padx=10)
        self.pb = ttk.Progressbar(bottom, mode="indeterminate", length=160)
        self.pb.pack(side=tk.RIGHT)

        # 로그 (기본은 접어둠 — 오류가 나면 자동으로 펼침)
        log_head = ttk.Frame(self.root)
        log_head.pack(fill=tk.X, padx=10)
        self.log_toggle = ttk.Button(log_head, text="▸ 상세 로그 보기", command=self.toggle_log)
        self.log_toggle.pack(side=tk.LEFT)
        self.log_frame = ttk.Frame(self.root)
        self.log_text = tk.Text(self.log_frame, height=8, font=("Consolas", 9),
                                bg="#1e1e1e", fg="#d4d4d4")
        sb = ttk.Scrollbar(self.log_frame, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log("준비 완료. PDF를 드롭하거나 [PDF 파일 선택] 버튼을 누르세요.")

    def toggle_log(self, show: bool | None = None):
        visible = bool(self.log_frame.winfo_manager())
        if show is None:
            show = not visible
        if show and not visible:
            self.log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(4, 10))
            self.log_toggle.config(text="▾ 상세 로그 숨기기")
        elif not show and visible:
            self.log_frame.pack_forget()
            self.log_toggle.config(text="▸ 상세 로그 보기")

    @staticmethod
    def _mark_empty(entry: tk.Entry, var: tk.StringVar):
        if str(entry.cget("state")) == "disabled":
            return
        entry.config(bg=NORMAL_BG if var.get().strip() else EMPTY_BG)

    def _set_fields_state(self, enabled: bool):
        for key, ent in self.entries.items():
            ent.config(state="normal" if enabled else "disabled")
            if enabled:
                self._mark_empty(ent, self.vars[key])

    def _update_api_status(self):
        key = get_api_key()
        model_label = get_model_label()
        if key:
            text = f"☁ Claude API: 활성 [{model_label}]"
            self.api_label.config(text=text, foreground="#0a7")
        else:
            text = "☁ Claude API: 미설정 — [⚙ 설정] 에서 API 키를 등록해주세요 (지금은 파일명/본문 규칙으로만 추출)"
            self.api_label.config(text=text, foreground="#a40")

    # ──────────────── 이벤트 ────────────────

    def on_drop(self, event):
        # tkdnd2 는 여러 파일을 공백으로 구분하고, 공백 있는 경로는 {...} 로 감싼다
        paths = self.root.tk.splitlist(event.data)
        pdfs = [p for p in paths if p.lower().endswith(".pdf") and Path(p).exists()]
        if not pdfs:
            self.log(f"PDF 파일이 아닙니다: {event.data}")
            messagebox.showinfo("알림", "PDF 파일을 끌어다 놓아주세요.")
            return
        if len(pdfs) > 1:
            self.log(f"여러 파일 중 첫 번째만 처리합니다: {Path(pdfs[0]).name}")
        self.process_pdf(pdfs[0])

    def choose_file(self):
        path = filedialog.askopenfilename(
            title="PDF 선택",
            filetypes=[("PDF", "*.pdf"), ("모든 파일", "*.*")],
            initialdir=str(Path.home() / "Downloads"),
        )
        if path:
            self.process_pdf(path)

    def choose_latest(self):
        downloads = Path.home() / "Downloads"
        pdfs = list(downloads.glob("*.pdf"))
        if not pdfs:
            messagebox.showinfo("알림", "다운로드 폴더에 PDF가 없습니다.")
            return
        latest = max(pdfs, key=lambda p: p.stat().st_mtime)
        self.process_pdf(latest)

    def _refresh_tc_label(self):
        saved = taskcard.load()
        if taskcard.is_valid(saved):
            self.tc_label.config(text=f"📌 과제카드: {taskcard.summary(saved)}", foreground="#0a7")
        else:
            self.tc_label.config(text="📌 과제카드: 미저장 — 폼에서 한 번 선택 후 [과제카드 저장]",
                                 foreground="#a40")

    def _refresh_user_label(self):
        saved = user_mod.load()
        if user_mod.is_valid(saved):
            self.user_label.config(text=f"👤 접수자/업무담당자: {user_mod.summary(saved)}", foreground="#0a7")
        else:
            self.user_label.config(text="👤 접수자/업무담당자: 미저장 — 폼에서 한 번 선택 후 [사용자 저장]",
                                   foreground="#a40")

    def save_user(self):
        try:
            from wxs_form import WXSForm as _WF
            f = _WF.attach()
        except Exception as e:
            messagebox.showerror("연결 실패",
                                 f"비전자문서등록 창에 연결하지 못했습니다.\n\n{e}")
            return
        data = user_mod.capture(f)
        if not user_mod.is_valid(data):
            messagebox.showwarning(
                "사용자 미선택",
                "접수자/업무담당자가 아직 선택되지 않았습니다.\n\n"
                "비전자문서등록 창의 접수자 옆 🔍 버튼을 눌러서\n"
                "본인을 선택한 뒤 다시 [👤 사용자 저장] 을 눌러주세요.\n\n"
                "(업무담당자도 같은 방법으로 본인 선택)"
            )
            return
        user_mod.save(data)
        self._refresh_user_label()
        self.log(f"✓ 사용자 저장: {user_mod.summary(data)}")
        messagebox.showinfo("저장 완료",
                            f"사용자 정보가 저장되었습니다.\n\n{user_mod.summary(data)}\n\n"
                            "이후 PDF 입력 시 자동으로 적용됩니다.")

    def save_taskcard(self):
        try:
            from wxs_form import WXSForm as _WF
            f = _WF.attach()
        except Exception as e:
            messagebox.showerror("연결 실패",
                                 f"비전자문서등록 창에 연결하지 못했습니다.\n\n{e}")
            return
        data = taskcard.capture(f)
        if not taskcard.is_valid(data):
            messagebox.showwarning(
                "선택된 과제카드 없음",
                "비전자문서등록 창에서 🔍 버튼으로 과제카드를 한 번 선택한 뒤\n"
                "다시 [📌 과제카드 저장] 을 눌러주세요."
            )
            return
        taskcard.save(data)
        self._refresh_tc_label()
        self.log(f"✓ 과제카드 저장: {taskcard.summary(data)}")
        messagebox.showinfo("저장 완료",
                            f"과제카드가 저장되었습니다.\n\n{taskcard.summary(data)}\n\n"
                            "이후 PDF 입력 시 자동으로 적용됩니다.")

    def _set_busy(self, busy: bool):
        self._busy = busy
        for b in self.pick_btns:
            b.config(state=tk.DISABLED if busy else tk.NORMAL)
        if busy:
            self.pb.start(10)
        else:
            self.pb.stop()

    def process_pdf(self, pdf_path: str | Path):
        """PDF 추출 (백그라운드 스레드)."""
        if self._busy:
            self.log("이전 작업이 끝난 뒤 다시 시도하세요.")
            return
        path = Path(pdf_path)
        for v in self.vars.values():
            v.set("")
        self._set_fields_state(False)
        self.source_label.config(text="", bg=self.root.cget("bg"))
        self.apply_btn.config(state=tk.DISABLED)
        self.status.config(text=f"추출 중: {path.name}", foreground="black")
        self._set_busy(True)
        self.log(f"\n=== {path.name} ===")
        self._extracted_meta = None
        self._extracted_path = path

        threading.Thread(target=self._extract_thread, args=(path,), daemon=True).start()

    def _extract_thread(self, path: Path):
        try:
            meta = extract_smart(path, prefer="claude")
            self.root.after(0, self._on_extract_done, meta, None)
        except Exception as e:
            tb = traceback.format_exc()
            self.root.after(0, self._on_extract_done, None, (e, tb))

    def _on_extract_done(self, meta, error):
        self._set_busy(False)
        if error:
            err, tb = error
            self.status.config(text=f"추출 실패: {err}", foreground="red")
            self.log(tb)
            self.toggle_log(True)
            return
        self._extracted_meta = meta
        for key, _label, _hint in FIELDS:
            self.vars[key].set(getattr(meta, key) or "")
        self._set_fields_state(True)

        name = Path(meta.source_file).name if meta.source_file else ""
        if meta.warning:
            # Claude 를 쓰려다 실패 → 파일명/본문 규칙으로 대체된 결과. 정확도가 낮으니 경고.
            self.source_label.config(
                text=f"⚠ Claude 추출 실패 → 파일명/본문 규칙으로 추출했습니다. 값을 꼭 확인하세요.\n"
                     f"   이유: {meta.warning}",
                bg="#fdecea", fg="#b3261e")
            self.status.config(text="규칙 추출 완료 — 값 확인 후 입력", foreground="#a40")
        else:
            self.source_label.config(text=f"✓ {meta.engine or '추출'}  ·  {name}",
                                     bg=self.root.cget("bg"), fg="#0a7")
            self.status.config(text="추출 완료 — 값 확인 후 [폼에 입력]", foreground="#0a7")

        missing = [label for key, label, _h in FIELDS if not self.vars[key].get().strip()]
        if missing:
            self.log(f"⚠ 비어 있는 칸: {', '.join(missing)} (주황색 칸)")
        self.log(str(meta))
        self.apply_btn.config(state=tk.NORMAL)

    def _edited_meta(self):
        """입력칸에서 고친 값으로 DocMeta 사본을 만든다."""
        values = {key: self.vars[key].get().strip() for key, _l, _h in FIELDS}
        return dataclasses.replace(self._extracted_meta, **values)

    def on_apply(self):
        if not self._extracted_meta or self._busy:
            return
        meta = self._edited_meta()
        if not any(getattr(meta, key) for key, _l, _h in FIELDS):
            messagebox.showwarning("값 없음", "입력할 값이 하나도 없습니다. 칸을 채워주세요.")
            return
        if meta.enforce_date and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", meta.enforce_date):
            if not messagebox.askyesno(
                "시행일자 형식",
                f"시행일자 '{meta.enforce_date}' 가 YYYY-MM-DD 형식이 아닙니다.\n"
                "폼에서 오류가 날 수 있습니다. 그래도 입력할까요?"):
                return
        self.apply_btn.config(state=tk.DISABLED)
        self.status.config(text="폼 연결 중…", foreground="black")
        self._set_busy(True)
        threading.Thread(target=self._apply_thread, args=(meta,), daemon=True).start()

    def _apply_thread(self, meta):
        # 백그라운드 스레드에서 COM 호출하려면 STA 초기화 필수
        # (그렇지 않으면 IE 의 parentWindow.execScript 등이 E_NOINTERFACE)
        import pythoncom
        pythoncom.CoInitialize()
        try:
            try:
                f = WXSForm.attach()
            except Exception as e:
                self.root.after(0, self._on_apply_error, str(e))
                return
            try:
                log_lines = []
                log_lines.append("─ 기본값 적용 ─")
                log_lines.extend(apply_defaults(f))
                log_lines.append("─ PDF 데이터 적용 ─")
                log_lines.extend(apply_pdf(f, meta))
                # 과제카드는 모든 set 끝난 뒤 마지막에 적용
                log_lines.append("─ 과제카드 적용 ─")
                log_lines.extend(apply_taskcard(f))
                self.root.after(0, self._on_apply_done, log_lines)
            except Exception:
                tb = traceback.format_exc()
                self.root.after(0, self._on_apply_error, tb)
        finally:
            pythoncom.CoUninitialize()

    def _on_apply_done(self, lines):
        self._set_busy(False)
        for line in lines:
            self.log(line)
        problems = [ln.strip() for ln in lines if ln.lstrip().startswith(("✗", "⚠"))]
        self.apply_btn.config(state=tk.NORMAL)
        if problems:
            self.status.config(text="⚠ 일부 항목 입력 안 됨 — 로그 확인", foreground="#a40")
            self.toggle_log(True)
            messagebox.showwarning(
                "일부 확인 필요",
                "폼 입력은 끝났지만 아래 항목은 직접 확인해 주세요.\n\n"
                + "\n".join(problems[:8])
                + "\n\n폼에서 내용을 확인한 뒤 [저장] 버튼을 클릭하세요.")
        else:
            self.status.config(text="✅ 입력 완료. 폼에서 검토 후 저장하세요.", foreground="#0a7")
            messagebox.showinfo("완료", "비전자문서등록 폼 입력 완료.\n폼에서 내용을 확인한 뒤 [저장] 버튼을 클릭하세요.")

    def _on_apply_error(self, msg):
        self._set_busy(False)
        self.log(f"[에러] {msg}")
        self.toggle_log(True)
        self.status.config(text="입력 실패. 비전자문서등록 창이 열려있는지 확인.", foreground="red")
        self.apply_btn.config(state=tk.NORMAL)
        messagebox.showerror("실패", f"폼에 입력하지 못했습니다.\n\n{msg}")

    # ──────────────── 설정 ────────────────

    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Claude API 설정")
        win.geometry("700x540")
        win.transient(self.root)
        win.grab_set()

        # ── API 키 섹션 ──
        ttk.Label(win, text="Anthropic API 키", font=("맑은 고딕", 11, "bold")).pack(pady=(14, 4))
        ttk.Label(win, text="https://console.anthropic.com/settings/keys 에서 발급",
                  foreground="gray").pack()
        entry = ttk.Entry(win, width=80, show="*")
        entry.pack(pady=10, padx=20, fill=tk.X)
        existing = get_api_key()
        if existing:
            entry.insert(0, existing)

        ttk.Label(win, text="키는 %USERPROFILE%\\.kedu_anthropic_key 에 저장됩니다.",
                  foreground="gray", font=("맑은 고딕", 9)).pack()

        # ── 구분선 ──
        ttk.Separator(win, orient="horizontal").pack(fill=tk.X, padx=20, pady=12)

        # ── 모델 선택 섹션 ──
        ttk.Label(win, text="Claude 모델", font=("맑은 고딕", 11, "bold")).pack(pady=(0, 4))
        ttk.Label(win, text="새로고침하면 이 키로 쓸 수 있는 최신 목록을 가져옵니다 (기본·추천: Sonnet 5.5)",
                  foreground="gray", font=("맑은 고딕", 9)).pack()

        # 콤보박스 + 새로고침 버튼
        combo_row = ttk.Frame(win)
        combo_row.pack(fill=tk.X, padx=20, pady=8)

        tier_order = {"fable": 0, "opus": 1, "sonnet": 2, "haiku": 3}
        cur_id = get_model()

        def _prepare(models: list[dict]) -> list[dict]:
            models = sorted(models, key=lambda m: (tier_order.get(m["tier"], 9), m["id"]))
            # 지금 쓰는 모델이 목록에 없으면 맨 앞에 넣는다 — 안 그러면 콤보가 첫 항목을
            # 가리켜 [저장] 한 번에 모델이 엉뚱하게 바뀐다.
            if not any(m["id"] == cur_id for m in models):
                models.insert(0, {"id": cur_id, "name": cur_id, "tier": "?"})
            return models

        def _format(m: dict) -> str:
            tier_hint = TIER_HINT.get(m["tier"], "")
            return f"{m['name']:25s}  ({m['id']})  — {tier_hint}"

        # 초기 모델 목록 (캐시 또는 fallback)
        current_models = _prepare(list_available_models(refresh=False))

        combo = ttk.Combobox(combo_row, width=85, state="readonly")
        combo["values"] = [_format(m) for m in current_models]
        combo.current(next(i for i, m in enumerate(current_models) if m["id"] == cur_id))
        combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 상태 라벨 (새로고침 결과)
        status = ttk.Label(win, text="", foreground="gray", font=("맑은 고딕", 9))
        status.pack(pady=(2, 0))

        def refresh_models():
            nonlocal current_models
            status.config(text="API 호출 중…", foreground="#06a")
            win.update_idletasks()
            try:
                sel_id = current_models[combo.current()]["id"] if combo.current() >= 0 else cur_id
                new_models = _prepare(list_available_models(refresh=True))
                current_models = new_models
                combo["values"] = [_format(m) for m in new_models]
                combo.current(next((i for i, m in enumerate(new_models) if m["id"] == sel_id), 0))
                status.config(text=f"✓ {len(new_models)} 개 모델 — 목록 갱신됨", foreground="#0a7")
            except Exception as e:
                status.config(text=f"✗ 새로고침 실패: {e}", foreground="#a40")

        ttk.Button(combo_row, text="🔄 새로고침", command=refresh_models).pack(side=tk.LEFT, padx=6)

        # tier 안내
        ttk.Label(win, text="모델별 특성:", font=("맑은 고딕", 10, "bold")).pack(pady=(10, 2))
        for tier, desc in TIER_HINT.items():
            ttk.Label(win, text=f"  • {tier.capitalize()}: {desc}",
                      foreground="#555", font=("맑은 고딕", 9)).pack(anchor=tk.W, padx=30)

        ttk.Label(win,
                  text="설정은 %USERPROFILE%\\.kedu_anthropic_model 에 저장됩니다.",
                  foreground="gray", font=("맑은 고딕", 9)).pack(pady=(10, 0))

        def save():
            # API 키
            k = entry.get().strip()
            if k:
                if not k.startswith("sk-ant-"):
                    messagebox.showwarning("형식 오류", "Anthropic 키는 'sk-ant-' 로 시작합니다.", parent=win)
                    return
                save_api_key(k)
            # 모델
            sel = combo.current()
            if sel < 0 or sel >= len(current_models):
                messagebox.showwarning("선택 오류", "모델을 선택해주세요.", parent=win)
                return
            try:
                save_model_id(current_models[sel]["id"])
            except Exception as e:
                messagebox.showwarning("모델 저장 실패", str(e), parent=win)
                return
            self._update_api_status()
            messagebox.showinfo("완료", "설정이 저장되었습니다.", parent=win)
            win.destroy()

        bf = ttk.Frame(win)
        bf.pack(pady=14)
        ttk.Button(bf, text="저장", command=save).pack(side=tk.LEFT, padx=5)
        ttk.Button(bf, text="취소", command=win.destroy).pack(side=tk.LEFT, padx=5)

    # ──────────────── 로그 ────────────────

    def log(self, msg: str):
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)


def _close_splash():
    """PyInstaller splash screen 닫기 (있을 때만)."""
    try:
        import pyi_splash  # type: ignore
        pyi_splash.close()
    except Exception:
        pass  # 개발 환경 또는 splash 없이 빌드된 경우


def main():
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    App(root)
    # GUI 가 mainloop 진입 직전에 splash 닫음 (모든 import 끝났음을 의미)
    _close_splash()
    root.mainloop()


if __name__ == "__main__":
    main()
