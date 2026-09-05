#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""バッチCV：ホーム最下部に法的文書リンク（V2.27）"""
import io, os, sys, re
APP = os.environ.get("APP_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
R = []
def ok(n, c, d=""):
    R.append((bool(c), n, d))
html = io.open(os.path.join(APP, "index.html"), encoding="utf-8").read()
css = io.open(os.path.join(APP, "styles.css"), encoding="utf-8").read()
home = html[html.find('id="screen-home"'):html.find('id="screen-quiz"')]
ok("ホーム内にプライバシーポリシーへのリンク", 'privacy.html' in home)
ok("ホーム内に利用規約へのリンク", 'terms.html' in home)
ok("build-stampより上（最下部領域）にある", home.find('home-legal') < home.find('build-stamp'))
ok("設定内の既存リンクも残っている", html.count('privacy.html') >= 2)
ok("スタイルがある", '.home-legal{' in css)
used = set(re.findall(r"var\(--([\w-]+)", css[css.find('.home-legal{'):css.find('.home-legal a{')+120]))
defined = set(re.findall(r"--([\w-]+)\s*:", css))
ok("使う変数は定義済み（V2.25の教訓）", used <= defined, str(used - defined))
bad = [x for x in R if not x[0]]
for g, n, d in R:
    print(("  ok  " if g else "  NG  ") + n + (("   << " + d) if (d and not g) else ""))
print("\n%d/%d  batchCV" % (len(R) - len(bad), len(R)))
sys.exit(1 if bad else 0)
