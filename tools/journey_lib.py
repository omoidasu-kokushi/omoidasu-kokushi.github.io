# -*- coding: utf-8 -*-
"""インストールから合格までを通しで走らせるための道具一式。

**時計を進められることが要**。忘却スケジュールも模試の解禁も
「何日経ったか」で動くので、実時間で待っていては一生検証できない。
`Date` ごと差し替えて、テストから日数を進める。
"""
import json, time

CLOCK = r"""
(() => {
  const RealDate = Date;
  let offset = 0;
  class FakeDate extends RealDate {
    constructor(...a) { if (a.length === 0) { super(RealDate.now() + offset); } else { super(...a); } }
    static now() { return RealDate.now() + offset; }
    static parse(...a) { return RealDate.parse(...a); }
    static UTC(...a) { return RealDate.UTC(...a); }
  }
  window.Date = FakeDate;
  window.__advance = (ms) => { offset += ms; return offset; };
  window.__offset  = () => offset;
  window.__setOffset = (ms) => { offset = ms; return offset; };
})();
"""

DAY = 86400000
HOUR = 3600000


def new_page(pw, profile=None, offline=False):
    if profile:
        ctx = pw.chromium.launch_persistent_context(profile, args=["--no-sandbox"],
                                                    viewport={"width": 390, "height": 844})
        pg = ctx.pages[0] if ctx.pages else ctx.new_page()
        br = None
    else:
        br = pw.chromium.launch(args=["--no-sandbox"])
        ctx = br.new_context(viewport={"width": 390, "height": 844})
        pg = ctx.new_page()
    ctx.add_init_script(CLOCK)
    pg.set_default_timeout(600000)
    return br, ctx, pg


def boot(pg, url, dismiss_welcome=True, wait=1800):
    pg.goto(url, wait_until="load")
    pg.wait_for_function("window.__APP_READY === true", timeout=180000)
    pg.wait_for_timeout(wait)
    if dismiss_welcome:
        try:
            pg.click("#welcome-start", timeout=4000)
        except Exception:
            pass
        pg.wait_for_timeout(600)


def advance_days(pg, days, to_hour=7):
    """指定日数ぶん進めて、その日の朝 to_hour 時にそろえる。
       日界は朝4:00なので、7時にそろえておけば『その日ぶん』が出そろう。"""
    pg.evaluate("(ms) => window.__advance(ms)", int(days * DAY))
    cur = pg.evaluate("() => new Date().getHours()")
    delta = (to_hour - cur) % 24
    if delta:
        pg.evaluate("(ms) => window.__advance(ms)", int(delta * HOUR))
    return pg.evaluate("() => new Date().toISOString()")


def answer_current_ui(pg, want_right=True, ground=True, timeout=15000):
    """いま画面に出ている問題を、正解／不正解を指定して解く（模試用）。
       正解肢は Main.state.current.atoms から引く（画面には出ていない）。"""
    pg.wait_for_function(
        "() => document.querySelector('#choice-list .choice-card')"
        " || (document.querySelector('#numeric-wrap')"
        "     && document.querySelector('#numeric-wrap').offsetParent !== null)",
        timeout=timeout)
    if pg.is_visible("#numeric-wrap"):
        val = pg.evaluate("""() => {
          const q = window.Main.state.current && window.Main.state.current.question;
          return q && q.numeric_answer != null ? String(q.numeric_answer) : '1';
        }""")
        pg.fill("#numeric-input", val if want_right else "0")
    else:
        pg.wait_for_selector("#choice-list.is-ready", timeout=timeout)
        pg.wait_for_timeout(260)
        plan = pg.evaluate("""(right) => {
          const cur = window.Main.state.current;
          if (!cur) return null;
          const atoms = cur.atoms || [];
          const rightNums = atoms.filter(a => a.is_correct).map(a => a.original_num);
          const wrongNums = atoms.filter(a => !a.is_correct).map(a => a.original_num);
          let pick;
          if (right) { pick = rightNums.slice(); }
          else {
            pick = wrongNums.length ? wrongNums.slice(0, Math.max(1, rightNums.length))
                                    : rightNums.slice(0, 1);
          }
          return { pick, n: atoms.length };
        }""", want_right)
        if not plan:
            return False
        if ground:
            marks = pg.locator("#choice-list .choice-mark")
            for k in range(marks.count()):
                try:
                    marks.nth(k).click(timeout=3000)
                except Exception:
                    pass
        for num in plan["pick"]:
            try:
                pg.click("#choice-list .choice-card[data-num='%s'] .choice-body" % num, timeout=6000)
            except Exception:
                pass
    try:
        pg.wait_for_selector("#btn-confirm:not([disabled])", timeout=8000)
        pg.click("#btn-confirm")
        return True
    except Exception:
        return False


def answer_and_next(pg, want_right=True, timeout=15000):
    """通常モード（解説を挟む）で1問解いて次へ進む。"""
    if not answer_current_ui(pg, want_right=want_right, ground=False, timeout=timeout):
        return False
    try:
        pg.wait_for_selector("#btn-next:not([hidden])", timeout=timeout)
        pg.wait_for_timeout(120)
        pg.click("#btn-next", timeout=timeout)
        pg.wait_for_timeout(150)
        return True
    except Exception:
        return False


def run_session_ui(pg, n, right_ratio=0.7, timeout=15000):
    """いま出ているセッションを n 問ぶん解く。戻り値は (解けた数, 正解にした数)。"""
    done = 0; right = 0
    for i in range(n * 2):
        if done >= n:
            break
        if not pg.is_visible("#screen-quiz"):
            break
        want = ((i % 100) / 100.0) < right_ratio
        if not answer_and_next(pg, want_right=want, timeout=timeout):
            break
        done += 1
        if want:
            right += 1
    return done, right


def tour_next(pg, tries=40):
    """その場ガイドの吹き出しを最後まで送る。出ていなければ何もしない。"""
    n = 0
    for _ in range(tries):
        if not pg.is_visible("#onb-layer"):
            break
        try:
            pg.click("#onb-next", timeout=2500)
            n += 1
            pg.wait_for_timeout(320)
        except Exception:
            break
    return n


def tour_skip(pg):
    if pg.is_visible("#onb-layer"):
        try:
            pg.click("#onb-skip", timeout=2500)
            pg.wait_for_timeout(400)
            return True
        except Exception:
            return False
    return False


def close_modals(pg):
    try:
        pg.evaluate("() => { if (window.Main && window.Main.closeModals) window.Main.closeModals(); }")
    except Exception:
        pass
