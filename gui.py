"""
비전자문서등록 자동입력 GUI
============================
- PDF 파일을 창에 드래그 → 자동 추출 → 폼에 일괄 입력
- 파일 선택 버튼도 지원
- API 키 설정 다이얼로그 내장

실행:
    pythonw gui.py [PDF경로]
또는 바탕화면 바로가기 더블클릭, 우클릭 [Send to → 비전자문서등록]
"""
from __future__ import annotations

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


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("비전자문서등록 자동입력")
        root.geometry("720x560")
        root.minsize(600, 480)

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

        # 추출 엔진은 Claude 만 사용 (다른 옵션 제거됨 — v1.0.7)
        self.backend_var = tk.StringVar(value="claude")
        self.api_label = ttk.Label(self.root, text="", foreground="gray", font=("맑은 고딕", 9))
        self.api_label.pack(anchor=tk.W, padx=10, pady=(2, 0))

        # 드래그앤드롭 영역
        self.drop_frame = tk.Frame(self.root, bg="#eef4fb", relief="ridge", bd=2)
        self.drop_frame.pack(fill=tk.X, **pad)
        msg = "여기에 PDF 파일을 끌어다 놓으세요" if HAS_DND else "[파일 선택] 버튼으로 PDF를 골라주세요"
        self.drop_label = tk.Label(self.drop_frame, text=msg,
                                   bg="#eef4fb", fg="#356", font=("맑은 고딕", 11),
                                   pady=24)
        self.drop_label.pack(fill=tk.X)
        if HAS_DND:
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind("<<Drop>>", self.on_drop)
            self.drop_label.drop_target_register(DND_FILES)
            self.drop_label.dnd_bind("<<Drop>>", self.on_drop)

        # 액션 버튼
        action = ttk.Frame(self.root)
        action.pack(fill=tk.X, **pad)
        ttk.Button(action, text="📁 PDF 파일 선택", command=self.choose_file).pack(side=tk.LEFT)
        ttk.Button(action, text="🗂 다운로드 폴더에서 최근 PDF",
                   command=self.choose_latest).pack(side=tk.LEFT, padx=6)
        ttk.Button(action, text="📌 과제카드 저장",
                   command=self.save_taskcard).pack(side=tk.RIGHT)
        self.tc_label = ttk.Label(action, text="", foreground="gray", font=("맑은 고딕", 9))
        self.tc_label.pack(side=tk.RIGHT, padx=8)
        self._refresh_tc_label()

        # 사용자(접수자/업무담당자) 저장 줄
        action2 = ttk.Frame(self.root)
        action2.pack(fill=tk.X, padx=10)
        ttk.Button(action2, text="👤 사용자 저장",
                   command=self.save_user).pack(side=tk.RIGHT)
        self.user_label = ttk.Label(action2, text="", foreground="gray", font=("맑은 고딕", 9))
        self.user_label.pack(side=tk.RIGHT, padx=8)
        self._refresh_user_label()

        # 추출 결과 표시
        ttk.Label(self.root, text="추출 결과", font=("맑은 고딕", 10, "bold")).pack(anchor=tk.W, padx=10, pady=(8, 2))
        self.tree = ttk.Treeview(self.root, columns=("value",), show="tree headings", height=8)
        self.tree.heading("#0", text="필드")
        self.tree.heading("value", text="값")
        self.tree.column("#0", width=140, anchor=tk.W)
        self.tree.column("value", width=520, anchor=tk.W)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=10)

        # 적용 버튼 + 진행 표시
        bottom = ttk.Frame(self.root)
        bottom.pack(fill=tk.X, **pad)
        self.apply_btn = ttk.Button(bottom, text="✅ 비전자문서등록 폼에 입력",
                                    command=self.on_apply, state=tk.DISABLED)
        self.apply_btn.pack(side=tk.LEFT)
        self.status = ttk.Label(bottom, text="대기 중", foreground="gray")
        self.status.pack(side=tk.LEFT, padx=10)
        self.pb = ttk.Progressbar(bottom, mode="indeterminate", length=180)
        self.pb.pack(side=tk.RIGHT)

        # 로그
        self.log_text = tk.Text(self.root, height=8, font=("Consolas", 9), bg="#1e1e1e", fg="#d4d4d4")
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.log("준비 완료. PDF를 드롭하거나 [PDF 파일 선택] 버튼을 누르세요.")

    def _update_api_status(self):
        key = get_api_key()
        model_label = get_model_label()
        if key:
            text = f"☁ Claude API: 활성 [{model_label}]"
            self.api_label.config(text=text, foreground="#0a7")
        else:
            text = "☁ Claude API: 미설정 — [⚙ 설정] 에서 API 키를 등록해주세요"
            self.api_label.config(text=text, foreground="#a40")

    # ──────────────── 이벤트 ────────────────

    def on_drop(self, event):
        # tkdnd2 returns paths that may be space-separated and brace-quoted
        raw = event.data.strip()
        # parse first {...} or first whitespace-separated path
        if raw.startswith("{") and raw.endswith("}"):
            path = raw[1:-1]
        else:
            path = raw.split()[0] if raw else ""
        if path and Path(path).exists():
            self.process_pdf(path)
        else:
            self.log(f"드롭한 경로를 인식할 수 없음: {raw}")

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
            self.tc_label.config(text=f"📌 {taskcard.summary(saved)}", foreground="#0a7")
        else:
            self.tc_label.config(text="📌 과제카드 미저장 →",  foreground="#a40")

    def _refresh_user_label(self):
        saved = user_mod.load()
        if user_mod.is_valid(saved):
            self.user_label.config(text=f"👤 {user_mod.summary(saved)}", foreground="#0a7")
        else:
            self.user_label.config(text="👤 사용자 미저장 →", foreground="#a40")

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
                "접수자/업무담당자가 placeholder 상태입니다.\n\n"
                "비전자문서등록 창의 접수자 옆 🔍 버튼을 눌러서\n"
                "본인(김상현)을 선택한 뒤 다시 [👤 사용자 저장] 을 눌러주세요.\n\n"
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

    def process_pdf(self, pdf_path: str | Path):
        """PDF 추출 (백그라운드 스레드)."""
        path = Path(pdf_path)
        self.tree.delete(*self.tree.get_children())
        self.apply_btn.config(state=tk.DISABLED)
        self.status.config(text=f"추출 중: {path.name}")
        self.pb.start(10)
        self.log(f"\n=== {path.name} ===")
        self._extracted_meta = None
        self._extracted_path = path

        threading.Thread(target=self._extract_thread, args=(path,), daemon=True).start()

    def _extract_thread(self, path: Path):
        try:
            meta = extract_smart(path, prefer=self.backend_var.get())
            self.root.after(0, self._on_extract_done, meta, None)
        except Exception as e:
            tb = traceback.format_exc()
            self.root.after(0, self._on_extract_done, None, (e, tb))

    def _on_extract_done(self, meta, error):
        self.pb.stop()
        if error:
            err, tb = error
            self.status.config(text=f"추출 실패: {err}", foreground="red")
            self.log(tb)
            return
        self._extracted_meta = meta
        self.status.config(text="추출 완료. [폼에 입력] 버튼을 눌러주세요.", foreground="#0a7")

        rows = [
            ("제목 (TITLE)",            meta.title),
            ("발신기관 (DRFTINSTTNM)",  meta.sender),
            ("수신자 (RECEIVERNAME)",   meta.receiver),
            ("문서번호 (DOCREGNO)",     meta.doc_no),
            ("시행일자 (ENFORCEDATE)",  meta.enforce_date),
            ("요지 (docOutline)",       meta.summary),
            ("[notes]",                 ", ".join(meta.notes)),
        ]
        for k, v in rows:
            self.tree.insert("", tk.END, text=k, values=(v or "(없음)",))

        self.log(str(meta))
        self.apply_btn.config(state=tk.NORMAL)

    def on_apply(self):
        if not self._extracted_meta:
            return
        self.apply_btn.config(state=tk.DISABLED)
        self.status.config(text="폼 연결 중…", foreground="black")
        self.pb.start(10)
        threading.Thread(target=self._apply_thread, daemon=True).start()

    def _apply_thread(self):
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
                log_lines.extend(apply_pdf(f, self._extracted_meta))
                # 과제카드는 모든 set 끝난 뒤 마지막에 적용
                log_lines.append("─ 과제카드 적용 ─")
                log_lines.extend(apply_taskcard(f))
                self.root.after(0, self._on_apply_done, log_lines)
            except Exception as e:
                tb = traceback.format_exc()
                self.root.after(0, self._on_apply_error, tb)
        finally:
            pythoncom.CoUninitialize()

    def _on_apply_done(self, lines):
        self.pb.stop()
        for line in lines:
            self.log(line)
        self.status.config(text="✅ 입력 완료. 폼에서 검토 후 저장하세요.", foreground="#0a7")
        self.apply_btn.config(state=tk.NORMAL)
        try:
            messagebox.showinfo("완료", "비전자문서등록 폼 입력 완료.\n폼에서 내용을 확인한 뒤 [저장] 버튼을 클릭하세요.")
        except Exception:
            pass

    def _on_apply_error(self, msg):
        self.pb.stop()
        self.log(f"[에러] {msg}")
        self.status.config(text="입력 실패. 비전자문서등록 창이 열려있는지 확인.", foreground="red")
        self.apply_btn.config(state=tk.NORMAL)
        messagebox.showerror("실패", f"폼에 입력하지 못했습니다.\n\n{msg}")

    # ──────────────── 설정 ────────────────

    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Claude API 설정")
        win.geometry("680x520")
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
        ttk.Label(win, text="사용 가능한 모델 — 새로고침 시 본인 키로 사용 가능한 최신 목록을 가져옵니다",
                  foreground="gray", font=("맑은 고딕", 9)).pack()

        # 콤보박스 + 새로고침 버튼
        combo_row = ttk.Frame(win)
        combo_row.pack(fill=tk.X, padx=20, pady=8)

        # 초기 모델 목록 (캐시 또는 fallback)
        current_models = list_available_models(refresh=False)
        # tier 순서: opus → sonnet → haiku
        tier_order = {"opus": 0, "sonnet": 1, "haiku": 2}
        current_models.sort(key=lambda m: (tier_order.get(m["tier"], 9), m["id"]))

        def _format(m: dict) -> str:
            tier_hint = TIER_HINT.get(m["tier"], "")
            return f"{m['name']:25s}  ({m['id']})  — {tier_hint}"

        combo = ttk.Combobox(combo_row, width=85, state="readonly")
        combo["values"] = [_format(m) for m in current_models]
        # 현재 선택된 모델 위치
        cur_id = get_model()
        cur_idx = next((i for i, m in enumerate(current_models) if m["id"] == cur_id), 0)
        combo.current(cur_idx)
        combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # 상태 라벨 (새로고침 결과)
        status = ttk.Label(win, text="", foreground="gray", font=("맑은 고딕", 9))
        status.pack(pady=(2, 0))

        def refresh_models():
            status.config(text="API 호출 중…", foreground="#06a")
            win.update_idletasks()
            try:
                new_models = list_available_models(refresh=True)
                new_models.sort(key=lambda m: (tier_order.get(m["tier"], 9), m["id"]))
                # combo 갱신
                nonlocal current_models
                current_models = new_models
                combo["values"] = [_format(m) for m in new_models]
                cur_idx2 = next((i for i, m in enumerate(new_models) if m["id"] == cur_id), 0)
                combo.current(cur_idx2)
                status.config(text=f"✓ {len(new_models)} 개 모델 발견 — 캐시 갱신됨", foreground="#0a7")
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
                    messagebox.showwarning("형식 오류", "Anthropic 키는 'sk-ant-' 로 시작합니다.")
                    return
                save_api_key(k)
            # 모델
            sel = combo.current()
            if sel < 0 or sel >= len(current_models):
                messagebox.showwarning("선택 오류", "모델을 선택해주세요.")
                return
            try:
                save_model_id(current_models[sel]["id"])
            except Exception as e:
                messagebox.showwarning("모델 저장 실패", str(e))
                return
            self._update_api_status()
            messagebox.showinfo("완료", "설정이 저장되었습니다.")
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
