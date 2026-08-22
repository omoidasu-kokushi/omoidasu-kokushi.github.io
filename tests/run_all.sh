#!/usr/bin/env bash
# 全スイートを通す。V1.40 時点の期待値：13スイート・713項目・全通過。
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

started=0
if ! curl -sf "http://127.0.0.1:${PORT}/index.html" >/dev/null 2>&1; then
  (cd "$APP_DIR" && python3 -m http.server "$PORT" >/dev/null 2>&1 &)
  started=1
  sleep 2
fi

pass=0
fail=0
for t in "$APP_DIR"/tests/test_batch*.py "$APP_DIR"/tests/test_regress.py; do
  [ -e "$t" ] || continue
  printf '%-26s ' "$(basename "$t")"
  out="$(python3 "$t" 2>&1)"
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
