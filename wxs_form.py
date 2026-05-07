"""
WXSClient (K-에듀파인 비전자문서등록) 자동 입력 라이브러리
==================================================

K-에듀파인의 비전자문서등록 창은 MFC 셸 + 임베디드 IE 컨트롤(WebBrowser ActiveX)이며,
폼 자체는 https://klef.sen.go.kr/.../retrievePrdctnDocRegistScrin.do 의 HTML이다.
임베디드 IE에서 IHTMLDocument2를 가져오면 일반 웹페이지처럼 DOM을 조작할 수 있다.

사용 예
-------
    from wxs_form import WXSForm
    f = WXSForm.attach()
    f.fill({
        "TITLE": "근로자 노임관련 조치결과 보고",
        "DRFTINSTTNM": "장위토건",
        "DSPTCHNMCN": "장위토건",
        "ORGDRAFTDEPTNAME": "장위토건",
        "DOCREGNO": "1",
        "ENFORCEDATE": "2026-04-29",
    })
    # 라디오/체크박스
    f.set_radio("PUBLICATION", "PUBLICATION2")     # 비공개
    f.set_radio("rcverType",   "rcverType1")       # 시행종류 1번
    f.check("ho5", True)                           # 5호 체크
    # 셀렉트
    f.set_select("registSe", "1")                  # 일반문서

필드 매핑
---------
- TITLE              : 제목
- docOutline         : 문서요지 (textarea)
- DRFTINSTTNM        : 발신기관명
- DSPTCHNMCN         : 발신명의
- ORGDRAFTDEPTNAME   : 원기안(발신)부서
- ORGDRAFTERNAME     : 원기안자
- DOCREGNO           : 생산기관문서번호
- DRAFTDATE          : 접수일자
- APPROVALDATE       : 처리일자
- ENFORCEDATE        : 시행일자
- DRAFTERNAME        : 접수자(이름)
- LASTSIGNERNAME     : 업무담당자(이름)
- RECEIVERNAME       : 수신자명
- PAGECNT            : 페이지수
- PUBLICRESTRIC      : 공개제한사유
- cnSumry            : 내용요약 (textarea)

라디오/셀렉트
- R_SENDRECEIVE  : 등록구분  → SENDRECEIVE2(접수) / SENDRECEIVE1(생산)
- PUBLICATION    : 대국민공개 → PUBLICATION0(공개) / 1(부분공개) / 2(비공개)
- othbcAt        : 공개제한근거 호 → ho1~ho8 (체크박스, 복수 선택 가능)
- othbclmtDeChk  : 공개제한기간 → othbclmtDeChk1(지정날짜) / 2(영구)
- readngScope    : 직원열람범위 → readngScope1(기관) / 3(부서)
- SECURITY       : 직원열람제한 → SECURITY0(설정안함) / 3(결재완료) / 1(지정날짜) / 2(영구)
- rcverType      : 시행종류 → rcverType1~4
- registSe       : 등록구분(관리정보) → '1'(일반문서) 등 (select)
- selectStatus   : 상태 → 'audit' 등 (select)
"""
from __future__ import annotations

import ctypes
import subprocess
from ctypes import wintypes
from typing import Mapping

import comtypes
import comtypes.client

# 첫 실행 시 MSHTML 타입라이브러리 컴파일 (수 초 소요)
try:
    from comtypes.gen import MSHTML  # type: ignore
except (ImportError, OSError):
    comtypes.client.GetModule("mshtml.tlb")
    from comtypes.gen import MSHTML  # type: ignore

user32 = ctypes.WinDLL("user32", use_last_error=True)
oleacc = ctypes.WinDLL("oleacc")

EnumChildProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
EnumWinProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumChildWindows.argtypes = [wintypes.HWND, EnumChildProc, wintypes.LPARAM]
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.RegisterWindowMessageW.argtypes = [wintypes.LPCWSTR]
user32.RegisterWindowMessageW.restype = wintypes.UINT
user32.SendMessageTimeoutW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    wintypes.UINT, wintypes.UINT, ctypes.POINTER(wintypes.LPARAM),
]
user32.GetWindowThreadProcessId.argtypes = [
    wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
]
oleacc.ObjectFromLresult.argtypes = [
    wintypes.LPARAM, ctypes.POINTER(comtypes.GUID),
    wintypes.WPARAM, ctypes.POINTER(ctypes.c_void_p),
]


def _find_wxs_pids() -> list[int]:
    """실행 중인 모든 WXSClient.exe 프로세스 PID 목록."""
    out = subprocess.run(
        ["tasklist", "/FI", "IMAGENAME eq WXSClient.exe", "/FO", "CSV", "/NH"],
        capture_output=True, text=True, encoding="cp949"
    ).stdout
    pids: list[int] = []
    for line in out.strip().splitlines():
        if "WXSClient" not in line:
            continue
        try:
            pids.append(int(line.split('","')[1]))
        except (IndexError, ValueError):
            continue
    return pids


def _find_wxs_windows(pid: int) -> list[int]:
    """해당 PID의 visible top-level 윈도우 모두."""
    found: list[int] = []

    def cb(hwnd, _):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value == pid and user32.IsWindowVisible(hwnd):
            found.append(hwnd)
        return True

    user32.EnumWindows(EnumWinProc(cb), 0)
    return found


def _find_ie_server(parent: int) -> int | None:
    found: list[int] = []

    def cb(hwnd, _):
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        if buf.value == "Internet Explorer_Server":
            found.append(hwnd)
            return False
        return True

    user32.EnumChildWindows(parent, EnumChildProc(cb), 0)
    return found[0] if found else None


def _get_html_document(ie_server_hwnd: int):
    """IHTMLDocument2를 잡아서 반환. (IHTMLDocument3는 호출 시점에 QI)"""
    msg = user32.RegisterWindowMessageW("WM_HTML_GETOBJECT")
    lresult = wintypes.LPARAM()
    user32.SendMessageTimeoutW(
        ie_server_hwnd, msg, 0, 0, 2, 1000, ctypes.byref(lresult)
    )
    iid = MSHTML.IHTMLDocument2._iid_
    pdoc = ctypes.POINTER(MSHTML.IHTMLDocument2)()
    hr = oleacc.ObjectFromLresult(
        lresult, ctypes.byref(iid), 0,
        ctypes.cast(ctypes.byref(pdoc), ctypes.POINTER(ctypes.c_void_p)),
    )
    if hr != 0:
        raise OSError(f"ObjectFromLresult failed: {hr:#x}")
    return pdoc


class WXSForm:
    """비전자문서등록 폼 핸들. doc(IHTMLDocument2)와 doc3(IHTMLDocument3) 양쪽을 보유."""

    def __init__(self, doc):
        self.doc = doc                                          # IHTMLDocument2
        self.doc3 = doc.QueryInterface(MSHTML.IHTMLDocument3)   # IHTMLDocument3

    @classmethod
    def attach(cls) -> "WXSForm":
        """모든 WXSClient 프로세스/윈도우를 순회하면서 IE_Server 가 있고
        URL 에 'PrdctnDocRegist' (비전자문서등록 화면) 가 들어있는 첫 폼을 잡는다.
        다중 인스턴스 환경에서도 안정적."""
        pids = _find_wxs_pids()
        if not pids:
            raise RuntimeError("WXSClient.exe 프로세스를 찾을 수 없습니다. 비전자문서등록 창을 열어주세요.")

        last_err = None
        first_doc = None  # IE 가 있긴 한데 URL 매칭 안되면 일단 보관
        for pid in pids:
            for hwnd in _find_wxs_windows(pid):
                ie = _find_ie_server(hwnd)
                if not ie:
                    continue
                try:
                    doc = _get_html_document(ie)
                except Exception as e:
                    last_err = e
                    continue
                # URL 검사 - 진짜 비전자문서등록 화면인지
                try:
                    url = (doc.url or "").lower()
                    if "prdctndocregist" in url or "비전자" in (doc.title or ""):
                        return cls(doc)
                except Exception:
                    pass
                if first_doc is None:
                    first_doc = doc
        if first_doc is not None:
            return cls(first_doc)
        raise RuntimeError(
            f"비전자문서등록 폼의 Internet Explorer_Server 를 찾지 못했습니다.\n"
            f"WXSClient 프로세스 {len(pids)} 개 발견했지만 폼 컨트롤 접근 실패.\n"
            f"폼 창이 활성/표시 상태인지 확인해주세요. (마지막 에러: {last_err})"
        )

    # ---------- 단일 필드 조작 ----------
    def get_element(self, element_id: str):
        # IHTMLDocument3.getElementById 우선, 실패 시 doc.all.namedItem 으로 fallback
        el = None
        try:
            el = self.doc3.getElementById(element_id)
        except Exception:
            pass
        if el is None:
            try:
                el = self.doc.all.item(element_id)
            except Exception:
                el = None
        if el is None:
            raise KeyError(f"id='{element_id}' 요소를 찾을 수 없습니다.")
        return el

    def set_value(self, element_id: str, value: str) -> None:
        """input[type=text|hidden] / textarea / select 에 값 입력 후 onchange 발생.

        IHTMLElement 자체에는 value setter 가 없으므로:
        ① IHTMLInputElement / TextArea / Select 로 QI 시도 (가장 안전)
        ② 실패 시 JavaScript 인젝션 (호환성 최강)
        """
        el = self.get_element(element_id)

        # ── ① 하위 인터페이스로 QI ──
        for iface_name in ("IHTMLInputElement", "IHTMLTextAreaElement",
                           "IHTMLSelectElement", "IHTMLInputTextElement"):
            iface = getattr(MSHTML, iface_name, None)
            if iface is None:
                continue
            try:
                sub = el.QueryInterface(iface)
                sub.value = value
                self._trigger_change(element_id)
                return
            except Exception:
                continue

        # ── ② JavaScript 인젝션 fallback ──
        self._set_value_via_js(element_id, value)
        self._trigger_change(element_id)

    def _set_value_via_js(self, element_id: str, value: str) -> None:
        """JS 로 value 설정 — 모든 element 종류에서 작동."""
        import json as _json
        eid = _json.dumps(element_id, ensure_ascii=False)
        val = _json.dumps(value, ensure_ascii=False)
        script = (
            f"(function(){{var e=document.getElementById({eid});"
            f"if(e){{e.value={val};}}}})();"
        )
        try:
            self.doc.parentWindow.execScript(script, "JavaScript")
        except Exception as e:
            raise RuntimeError(f"JS value 설정 실패 ({element_id}): {e}")

    def _trigger_change(self, element_id: str) -> None:
        """onchange + jQuery change + dispatchEvent('change') 모두 시도."""
        import json as _json
        eid = _json.dumps(element_id, ensure_ascii=False)
        script = (
            f"(function(){{var e=document.getElementById({eid});if(!e)return;"
            f"try{{if(typeof $==='function')$(e).trigger('change');}}catch(_){{}}"
            f"try{{if(e.onchange)e.onchange();}}catch(_){{}}"
            f"try{{var ev=document.createEvent('HTMLEvents');"
            f"ev.initEvent('change',true,true);e.dispatchEvent(ev);}}catch(_){{}}"
            f"}})();"
        )
        try:
            self.doc.parentWindow.execScript(script, "JavaScript")
        except Exception:
            pass

    def set_radio(self, name: str, target_id: str) -> None:
        """name 속성이 같은 라디오 그룹에서 target_id 선택."""
        radios = None
        try:
            radios = self.doc3.getElementsByName(name)
        except Exception:
            radios = None
        if radios is not None and radios.length > 0:
            for i in range(radios.length):
                r = radios.item(i)
                if r.id == target_id:
                    r.checked = True
                    try:
                        self.doc.parentWindow.execScript(
                            f"document.getElementById('{target_id}').click()", "JavaScript"
                        )
                    except Exception:
                        pass
                    return
        # fallback: id로 직접 찾아서 click
        el = self.get_element(target_id)
        try:
            el.click()
            return
        except Exception:
            pass
        el.checked = True

    def check(self, element_id: str, checked: bool = True) -> None:
        """체크박스 on/off. onclick 핸들러도 동기적으로 트리거.

        K-에듀파인의 ho5 등은 onclick 에 setPublicationExireDate() 같은
        후속 처리가 걸려 있어, 단순 .checked 할당만으로는 불완전.
        """
        el = self.get_element(element_id)
        # IHTMLInputElement 로 QI 해야 .checked 접근 가능
        try:
            inp = el.QueryInterface(MSHTML.IHTMLInputElement)
        except Exception:
            inp = None
        # 이미 원하는 상태면 noop
        if inp is not None:
            try:
                if bool(inp.checked) == checked:
                    return
            except Exception:
                pass
        # 1순위: el.click() — 자연스레 토글 + onclick 트리거
        try:
            el.click()
            # click 후 의도한 상태가 아니면 다시 한 번 토글
            if inp is not None:
                try:
                    if bool(inp.checked) != checked:
                        el.click()
                except Exception:
                    pass
            return
        except Exception:
            pass
        # 2순위: checked 직접 set + fireEvent
        if inp is not None:
            try:
                inp.checked = checked
            except Exception:
                pass
        try:
            el.fireEvent("onclick")
        except Exception:
            pass

    def set_select(self, element_id: str, value: str) -> None:
        """<select>의 value 변경."""
        el = self.get_element(element_id)
        el.value = value

    # ---------- 일괄 입력 ----------
    def fill(self, values: Mapping[str, str]) -> dict:
        """{id: value} 사전을 받아 일괄 입력. 결과는 {id: 'ok'|에러메시지}."""
        result: dict[str, str] = {}
        for k, v in values.items():
            try:
                self.set_value(k, str(v))
                result[k] = "ok"
            except Exception as e:
                result[k] = f"ERROR: {e}"
        return result

    # ---------- 디버그 ----------
    def list_fields(self) -> list[dict]:
        out = []
        for tag in ("INPUT", "SELECT", "TEXTAREA"):
            els = self.doc.all.tags(tag)
            for i in range(els.length):
                el = els.item(i)
                out.append({
                    "tag": tag,
                    "id": el.id,
                    "name": getattr(el, "name", None),
                    "type": getattr(el, "type", None),
                    "value": getattr(el, "value", None),
                })
        return out

    def click(self, element_id: str) -> None:
        """버튼 클릭."""
        el = self.get_element(element_id)
        el.click()


if __name__ == "__main__":
    import json
    f = WXSForm.attach()
    print(f"URL : {f.doc.url}")
    print(f"Title: {f.doc.title}")
    print(f"Fields: {len(f.list_fields())}")
    print(json.dumps(f.list_fields()[:5], ensure_ascii=False, indent=2))
