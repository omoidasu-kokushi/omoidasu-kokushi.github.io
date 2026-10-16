#!/usr/bin/env bash
# 全スイートを通す。V1.43 時点の期待値：16スイート・855項目・全通過。
#
# 使い方:  cd appH && bash tests/run_all.sh
#
# ローカルのHTTPサーバを立ててから走らせる。file:// では
# Service Worker も IndexedDB も動かないので、必ずhttpで開くこと。
set -u

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-8900}"
export APP_DIR
export APP_URL="${APP_URL:-http://127.0.0.1:${PORT}/index.html}"

# python3 が「在る」だけでは足りない。Windows の python3 は Microsoft Store へ
# 飛ばす偽物（実行すると "Python was not found" で落ちる）なので、実際に動くかで選ぶ。
# Linux では従来どおり python3 が選ばれる。
if [ -n "${PYTHON:-}" ]; then
  :
elif python3 -c 'import sys' >/dev/null 2>&1; then
  PYTHON=python3
elif python -c 'import sys; sys.exit(sys.version_info[0] != 3)' >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Python 3 が見つかりません（python3 も python も動かない）" >&2
  exit 1
fi

# Windows の Python は既定で cp932 を使うため、テストが ⏲ ☐ ◀ などを print すると
# UnicodeEncodeError で落ち、node の出力（UTF-8）を text=True で読むと None になる。
# UTF-8 モードに固定する。Linux では元から UTF-8 なので何も変わらない。
export PYTHONUTF8=1

started=0
if ! curl -sf "http://127.0.0.1:${PORT}/index.html" >/dev/null 2>&1; then
  (cd "$APP_DIR" && "$PYTHON" -m http.server "$PORT" >/dev/null 2>&1 &)
  started=1
  sleep 2
fi

pass=0
fail=0
for t in "$APP_DIR"/tests/test_batch*.py "$APP_DIR"/tests/test_regress.py "$APP_DIR"/tests/test_restore_guard.py "$APP_DIR"/tests/test_buy_dialog_overwrite.py "$APP_DIR"/tests/test_tax_slash.py "$APP_DIR"/tests/test_tax_fullwidth.py "$APP_DIR"/tests/test_exp_button_size.py "$APP_DIR"/tests/test_garble_report.py "$APP_DIR"/tests/test_case_series.py "$APP_DIR"/tests/test_knock_count.py "$APP_DIR"/tests/test_session_tally.py "$APP_DIR"/tests/test_verdict_coach.py "$APP_DIR"/tests/test_import_hygiene.py "$APP_DIR"/tests/test_mermaid_vertical.py "$APP_DIR"/tests/test_bessatsu_image.py "$APP_DIR"/tests/test_stem_image.py "$APP_DIR"/tests/test_narrow_320.py "$APP_DIR"/tests/test_tax_space.py "$APP_DIR"/tests/test_interrupt_guard.py "$APP_DIR"/tests/test_search_exam_abort.py "$APP_DIR"/tests/test_pick_badge.py "$APP_DIR"/tests/test_qty_mode.py "$APP_DIR"/tests/test_pomo_resume.py "$APP_DIR"/tests/test_break_restart.py "$APP_DIR"/tests/test_explain_btn.py "$APP_DIR"/tests/test_atom_layout.py "$APP_DIR"/tests/test_atom_echo.py "$APP_DIR"/tests/test_exam_history.py "$APP_DIR"/tests/test_exam_mix_quota.py "$APP_DIR"/tests/test_oneq_fast.py "$APP_DIR"/tests/test_seed_hisshu.py "$APP_DIR"/tests/test_oneq_verdict.py "$APP_DIR"/tests/test_hard_interval.py "$APP_DIR"/tests/test_free_exam_variant.py "$APP_DIR"/tests/test_seed_resume.py "$APP_DIR"/tests/test_free_exam_once.py "$APP_DIR"/tests/test_free_mock_bundle.py "$APP_DIR"/tests/test_free_units_gate.py "$APP_DIR"/tests/test_free_exam_cards.py "$APP_DIR"/tests/test_wording_product.py "$APP_DIR"/tests/test_exam_mark_free.py "$APP_DIR"/tests/test_exam_review_list.py "$APP_DIR"/tests/test_level5_weak_mock.py "$APP_DIR"/tests/test_exam_paper.py "$APP_DIR"/tests/test_exam_resume.py "$APP_DIR"/tests/test_exam_marks.py "$APP_DIR"/tests/test_exam_review_read.py "$APP_DIR"/tests/test_answer_position.py "$APP_DIR"/tests/test_exam_endtime.py "$APP_DIR"/tests/test_exam_review_back.py "$APP_DIR"/tests/test_exam_review_open.py "$APP_DIR"/tests/test_wording_together.py "$APP_DIR"/tests/test_tree_mock_badge.py "$APP_DIR"/tests/test_mock_search_leak.py "$APP_DIR"/tests/test_print_escape.py "$APP_DIR"/tests/test_onboard_abort.py; do
  [ -e "$t" ] || continue
  printf '%-26s ' "$(basename "$t")"
  out="$("$PYTHON" "$t" 2>&1)"
  if [ $? -eq 0 ]; then
    pass=$((pass + 1))
    echo "$out" | tail -1
  else
    fail=$((fail + 1))
    echo "$out" | tail -1
    echo "$out" | grep -E '^\s+NG' | head -8
  fi
done

echo
echo "スイート: 通過 ${pass} / 失敗 ${fail}"
[ "$started" = "1" ] && echo "（このスクリプトが立てたHTTPサーバは動いたままです）"
exit $([ "$fail" -eq 0 ] && echo 0 || echo 1)
