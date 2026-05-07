"""
과제카드(단위과제/관리과제) 자동 입력 모듈
============================================

K-에듀파인의 과제카드는 자체 팝업 검색으로만 선택 가능하지만,
팝업이 호출하는 콜백 함수(`fncTaskCardList`)와 hidden 필드(`untkID`, `mngtkID`)
구조가 페이지에 그대로 노출되어 있다.

전략: 사용자가 한 번 수동 선택한 상태를 캡처 → 파일에 저장 → 이후 자동 복원.

저장 위치: %USERPROFILE%\\.kedu_taskcard.json
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wxs_form import WXSForm, MSHTML

CONFIG_PATH = Path.home() / ".kedu_taskcard.json"


# ──────────────── 캡처 ────────────────

_CAPTURE_JS = r"""
(function(){
  function setOut(value) {
    var f = document.getElementById('_kedu_capture');
    if (!f) {
      f = document.createElement('input');
      f.type = 'hidden'; f.id = '_kedu_capture';
      document.body.appendChild(f);
    }
    f.value = value;
  }
  try {
    var data = {
      untkID: (document.getElementById('untkID') || {}).value || '',
      mngtkID: (document.getElementById('mngtkID') || {}).value || '',
      cards: []
    };

    // referTaskTable 안의 각 TR 이 하나의 과제카드 (fncTaskCardList 가 그렇게 만듦)
    // tr.querySelectorAll() 가 임베디드 IE 에서 가끔 작동 안하므로 getElementsByTagName 사용
    var rt = document.getElementById('referTaskTable');
    if (rt) {
      var trs = rt.getElementsByTagName('tr');
      for (var r = 0; r < trs.length; r++) {
        var ins = trs[r].getElementsByTagName('input');
        var card = {};
        for (var i = 0; i < ins.length; i++) {
          if (ins[i].type !== 'hidden') continue;
          var key = ins[i].name || ins[i].id || '';
          if (!key) continue;
          if (key.indexOf('_kedu') === 0 || key.indexOf('_diag') === 0) continue;
          card[key] = ins[i].value;
        }
        if (!card.tkcrdId) continue;  // 진짜 과제카드 row 만 (placeholder 제외)
        var label = '';
        try { label = (trs[r].innerText || trs[r].textContent || '').replace(/\s+/g, ' ').trim(); } catch(_e){}
        card._displayText = label;
        data.cards.push(card);
      }
    }

    setOut(JSON.stringify(data));
  } catch(e) {
    setOut(JSON.stringify({error: e.message, stack: (e.stack||'')}));
  }
})();
"""


def capture(form: WXSForm) -> dict[str, Any]:
    """현재 폼의 과제카드 상태를 dict 로 추출."""
    form.doc.parentWindow.execScript(_CAPTURE_JS, "JavaScript")
    raw = form.get_element("_kedu_capture").QueryInterface(MSHTML.IHTMLInputElement).value
    data = json.loads(raw or "{}")
    # IE 의 JSON.stringify quirk: cards (Array) 가 string 으로 직렬화될 수 있음 → 한 번 더 parse
    if isinstance(data.get("cards"), str):
        try:
            data["cards"] = json.loads(data["cards"])
        except json.JSONDecodeError:
            pass
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
    """저장된 과제카드 데이터가 유효한지(카드가 1개 이상)."""
    return bool(data) and bool(data.get("cards"))


def summary(data: dict[str, Any] | None) -> str:
    """사용자에게 보일 한 줄 요약."""
    if not is_valid(data):
        return "(저장된 과제카드 없음)"
    cards = data["cards"]
    parts = []
    for c in cards:
        nm = c.get("tkcrdNm") or c.get("_displayText") or "?"
        gb = {"01": "[단위]", "02": "[관리]", "03": "[기관]"}.get(c.get("taskGuBun", c.get("taskGubun", "")), "")
        parts.append(f"{gb} {nm}".strip())
    return ", ".join(parts)


# ──────────────── 적용 ────────────────

def _build_card_html(card: dict) -> str:
    """fncTaskCardList 가 만드는 HTML 과 동일한 구조를 Python 으로 생성."""
    gubun = card.get("taskGubun") or card.get("taskGuBun") or ""
    nm = card.get("tkcrdNm", "")
    dcry = card.get("dcryPrsrvPdSeNm", "")
    tkcrd_id = card.get("tkcrdId", "")
    goal_no = card.get("tkcrdGoalNo", "")
    plan_sn = card.get("actPlanSn", "")

    # 단위/관리 아이콘
    if gubun == "01":
        img = "<img class='Lbtn2' src='/bmsWeb/images/icon/ic_txt_unit.gif' alt='단위' />"
        suffix = f" ({dcry})" if dcry else ""
    elif gubun == "02":
        img = "<img class='Lbtn2' src='/bmsWeb/images/icon/ic_txt_adm.gif' alt='관리' />"
        suffix = ""
    else:
        img = ""
        suffix = ""

    # XSS 방지를 위해 따옴표/꺽쇠 escape
    def esc(s: str) -> str:
        return (s.replace("&", "&amp;").replace("<", "&lt;")
                  .replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;"))

    return (
        f"<tr><td id='testing' style='border:none'>"
        f"{img} {esc(nm)}{esc(suffix)} "
        f"<input type='hidden' id='tkcrdId' name='tkcrdId' value=\"{esc(tkcrd_id)}\" /> "
        f"<input type='hidden' id='tkcrdGoalNo' name='tkcrdGoalNo' value=\"{esc(goal_no)}\" /> "
        f"<input type='hidden' id='actPlanSn' name='actPlanSn' value=\"{esc(plan_sn)}\" /> "
        f"<input type='hidden' id='taskGuBun' name='taskGubun' value=\"{esc(gubun)}\" /> "
        f"<input type='hidden' id='tkcrdNm' name='tkcrdNm' value=\"{esc(nm)}\" /> "
        f"<input type='hidden' id='dcryPrsrvPdSeNm' name='dcryPrsrvPdSeNm' value=\"{esc(dcry)}\" /> "
        f"</td></tr>"
    )


def apply(form: WXSForm, data: dict[str, Any] | None = None) -> bool:
    """저장된 과제카드를 폼에 적용.
    execScript 가 백그라운드 스레드에서 E_NOINTERFACE 로 실패하는 경우가 있어,
    DOM 직접 조작 (IHTMLElement.innerHTML setter) 으로 처리한다.
    """
    if data is None:
        data = load()
    if not is_valid(data):
        return False

    # 1) tablebody 의 innerHTML 을 직접 set (execScript 우회)
    html = "".join(_build_card_html(c) for c in data["cards"])
    tbody = form.get_element("tablebody")

    # IHTMLElement.innerHTML setter 시도. 실패 시 outerHTML 로 fallback.
    set_via = None
    last_err: Exception | None = None
    for prop in ("innerHTML",):
        try:
            setattr(tbody, prop, html)
            set_via = prop
            break
        except Exception as e:
            last_err = e
            continue
    # tbody 직접 안되면 부모 table 의 children 변경 (IE quirk: tbody innerHTML은
    # 가끔 read-only 처럼 동작) → 이 때는 부모 td 안의 innerHTML 을 통째로 갈아끼움
    if set_via is None:
        try:
            referTable = form.get_element("referTaskTable")
            referTable.innerHTML = (
                "<caption>과제카드</caption>"
                f"<tbody id='tablebody'>{html}</tbody>"
            )
            set_via = "referTaskTable.innerHTML"
        except Exception as e:
            raise RuntimeError(f"tablebody 와 referTaskTable 모두 innerHTML 설정 실패: {last_err} / {e}")

    # 2) hidden 필드 untkID/mngtkID 동기화 (보통 비어있지만 혹시)
    for fid, key in (("untkID", "untkID"), ("mngtkID", "mngtkID")):
        try:
            form.set_value(fid, str(data.get(key, "")))
        except Exception:
            pass  # 없거나 실패해도 무시

    return True


# ──────────────── CLI ────────────────

if __name__ == "__main__":
    import sys
    cmd = sys.argv[1] if len(sys.argv) > 1 else "show"
    f = WXSForm.attach()

    if cmd == "capture":
        data = capture(f)
        if not is_valid(data):
            print("✗ 폼에 선택된 과제카드가 없습니다. 🔍 으로 한 번 선택 후 다시 실행하세요.")
            sys.exit(1)
        save(data)
        print(f"✅ 저장됨: {CONFIG_PATH}")
        print(f"   → {summary(data)}")
    elif cmd == "apply":
        if not apply(f):
            print("✗ 저장된 과제카드가 없습니다. 먼저 'python taskcard.py capture' 실행하세요.")
            sys.exit(1)
        print("✅ 적용 완료")
    elif cmd == "show":
        cur = capture(f)
        print(f"[현재 폼] {summary(cur)}")
        saved = load()
        print(f"[저장됨]   {summary(saved)}")
    elif cmd == "clear":
        if CONFIG_PATH.exists():
            CONFIG_PATH.unlink()
            print(f"✅ 삭제: {CONFIG_PATH}")
        else:
            print("(저장된 과제카드 없음)")
    else:
        print("Usage: python taskcard.py [capture | apply | show | clear]")
