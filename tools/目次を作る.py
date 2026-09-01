#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/ と tools/ の日本語目次を作り直す。

英字だけのファイル名（test_batchAA.py 等）では中身が分からないため、
各ファイル先頭の docstring（すでに日本語で書いてある）を抜き出して表にする。
実行: python3 tools/目次を作る.py
出力: tests/テスト一覧.md ／ tools/道具一覧.md（毎回上書き。手で直さない）
スイートや道具を足したら、これも走らせて目次を一緒にコミットする。
"""
import ast
import datetime
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.dirname(HERE)


def first_lines_of_doc(path, n=2):
    try:
        src = io.open(path, encoding="utf-8").read()
        doc = ast.get_docstring(ast.parse(src)) or ""
    except Exception as e:  # 構文が壊れていても目次は作る
        doc = "（読めない: %s）" % e
    lines = [l.strip() for l in doc.splitlines() if l.strip()]
    return " ／ ".join(lines[:n]) if lines else "（説明なし）"


def build(dirname, out_name, title, extra_rows=()):
    d = os.path.join(APP, dirname)
    rows = []
    for f in sorted(os.listdir(d)):
        if f.endswith(".py"):
            rows.append((f, first_lines_of_doc(os.path.join(d, f))))
    out = [
        "# %s" % title,
        "",
        "`python3 tools/目次を作る.py` が自動生成（%s）。**手で直さない。**"
        % datetime.date.today().isoformat(),
        "",
        "| ファイル | 説明（docstring の先頭） |",
        "|---|---|",
    ]
    for name, desc in list(extra_rows) + rows:
        out.append("| `%s` | %s |" % (name, desc.replace("|", "／")))
    io.open(os.path.join(d, out_name), "w", encoding="utf-8").write(
        "\n".join(out) + "\n")
    print("%s/%s  %d件" % (dirname, out_name, len(rows) + len(extra_rows)))


build("tests", "テスト一覧.md", "テスト一覧（tests/）", extra_rows=(
    ("run_all.sh", "全スイートをまとめて実行する（§16：単独で走らせる）"),
    ("mock_drive.js", "ドライブ同期のモック（テストが差し込む）"),
))
build("tools", "道具一覧.md", "道具一覧（tools/）")
