#!/usr/bin/env python3
"""Assemble a PR review-console artifact from a generated logical graph.

The LLM (generate.js workflow) decides CONTENT — plain-English labels, which
component belongs to which container, edges, before/after, quiz. This script
decides LAYOUT deterministically (row-major grid, so boxes never overlap) and
injects everything into template.html. Keeping layout in code is what makes the
"fully automatic" path reliable.

Input JSON (from the generator), shape:
{
  "title": str, "number": int|null, "subtitle": str,
  "context":   {"system": {"id","label":[..],"sub"}, "actors":[node...], "edges":[edge...]},
  "containers":{"items":[node+cap...], "externals":[node...], "edges":[edge...], "play":[id...]},
  "components":{"<containerId>": {"nodes":[codeNode...], "edges":[edge...]}, ...},
  "quiz":[{q,options[4],answer_index,explanation,difficulty}...],
  "ctxcode":{"<componentId>": "excerpt"}          # unchanged files shown for context
}
node:  {"id","label":[..],"sub"?,"impact":"new|chg|ctx","phase":"both|after"?, ...}
codeNode adds: "code":true,"sym","anchor","file","detail":{text,before?,after?}
edge:  {"from","to","kind":"flow|ref","phase":"both|after"?}
"""
import argparse
import json
import os
import re
import sys

COLS = {"context": 4, "container": 4, "component": 3}


def grid(nodes, cols):
    """Row-major placement; guarantees no two nodes share a cell."""
    for i, n in enumerate(nodes):
        n["col"] = i % cols
        n["row"] = i // cols
    rows = max(1, (len(nodes) + cols - 1) // cols)
    return cols, rows


def _detail(n):
    d = n.get("detail")
    if d:
        return d
    out = {"text": n.get("text", "")}
    if n.get("before"):
        out["before"] = n["before"]
    if n.get("after"):
        out["after"] = n["after"]
    return out


def _label(v):
    """Accept a string ('Front door'), a list of lines, or a 'a\\nb' string."""
    if isinstance(v, list):
        return v
    return str(v).split("\n")


def norm_node(n, *, code=False):
    o = {
        "id": n["id"],
        "label": _label(n["label"]),
        "impact": n.get("impact", "ctx"),
        "phase": n.get("phase", "both"),
        "detail": _detail(n),
    }
    if n.get("sub"):
        o["sub"] = n["sub"]
    if n.get("drill"):
        o["drill"] = n["drill"]
    if code:
        o["code"] = True
        o["sym"] = n.get("sym", "")
        o["anchor"] = n.get("anchor", "")
        o["file"] = n.get("file", "")
    return o


def build_scenes(g):
    scenes = {}

    # ---- L1 context ----
    ctx = g["context"]
    sysn = dict(ctx["system"])
    sysn["impact"] = sysn.get("impact", "chg")
    sysn["phase"] = "both"
    sysn["drill"] = "container"
    nodes = [norm_node(sysn)] + [norm_node(a) for a in ctx.get("actors", [])]
    c, r = grid(nodes, COLS["context"])
    scenes["context"] = {"kind": "context", "level": "L1", "crumb": "Context",
                         "cols": c, "rows": r, "nodes": nodes,
                         "edges": ctx.get("edges", []), "play": [], "caps": {}}

    # ---- L2 containers ----
    cons = g["containers"]
    citems = []
    caps = {}
    for it in cons.get("items", []):
        nn = norm_node(it)
        nn["drill"] = "cmp_" + it["id"]
        nn["impact"] = it.get("impact", "chg")
        citems.append(nn)
        if it.get("cap"):
            caps[it["id"]] = it["cap"]
    exts = [norm_node(e) for e in cons.get("externals", [])]
    nodes = citems + exts
    c, r = grid(nodes, COLS["container"])
    scenes["container"] = {"kind": "container", "level": "L2", "crumb": "Inside",
                           "cols": c, "rows": r, "nodes": nodes,
                           "edges": cons.get("edges", []),
                           "play": cons.get("play", []), "caps": caps}

    # ---- L3 component scenes, one per container ----
    label_by_id = {it["id"]: _label(it["label"])[0] for it in cons.get("items", [])}
    comps = g.get("components", {})
    if isinstance(comps, list):  # [{containerId, nodes, edges}] -> dict
        comps = {c["containerId"]: {"nodes": c.get("nodes", []), "edges": c.get("edges", [])}
                 for c in comps}
    for cid, comp in comps.items():
        nodes = [norm_node(n, code=True) for n in comp.get("nodes", [])]
        c, r = grid(nodes, COLS["component"])
        scenes["cmp_" + cid] = {"kind": "component", "level": "L3",
                                "crumb": label_by_id.get(cid, cid),
                                "cols": c, "rows": r, "nodes": nodes,
                                "edges": comp.get("edges", []), "play": [], "caps": {}}
    return scenes


def collect_diffs(scenes, diffdir):
    """Map each component node's `file` to its per-file diff text, if present."""
    diffs = {}
    if not diffdir or not os.path.isdir(diffdir):
        return diffs
    for sc in scenes.values():
        if sc["kind"] != "component":
            continue
        for n in sc["nodes"]:
            f = n.get("file")
            if not f or f in diffs:
                continue
            fn = os.path.join(diffdir, f.replace("/", "__") + ".diff")
            if os.path.exists(fn):
                diffs[f] = open(fn, encoding="utf-8").read().rstrip("\n")
    return diffs


def inject(template, key, value):
    marker = "/*__%s__*/" % key
    payload = json.dumps(value, ensure_ascii=False).replace("</", "<\\/")
    # placeholder appears as `/*__KEY__*/[]` or `/*__KEY__*/{}`
    return re.sub(re.escape(marker) + r"(\[\]|\{\})", lambda m: payload, template, count=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen", required=True, help="generator output JSON (graph+quiz+ctxcode)")
    ap.add_argument("--diffdir", required=True, help="dir of per-file diffs (path__with__underscores.diff)")
    ap.add_argument("--template", default=os.path.expanduser("~/.valor/pr-console/template.html"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    g = json.load(open(a.gen, encoding="utf-8"))
    scenes = build_scenes(g)
    diffs = collect_diffs(scenes, a.diffdir)
    quiz = g.get("quiz", [])
    ctxcode = g.get("ctxcode", {})

    tpl = open(a.template, encoding="utf-8").read()
    tpl = inject(tpl, "SCENES", scenes)
    tpl = inject(tpl, "QUIZ", quiz)
    tpl = inject(tpl, "DIFFS", diffs)
    tpl = inject(tpl, "CTXCODE", ctxcode)

    # title
    if g.get("title"):
        tpl = re.sub(r"<title>.*?</title>",
                     "<title>%s</title>" % re.sub(r"[<>]", "", g["title"]), tpl, count=1)

    for leftover in ("/*__SCENES__*/", "/*__QUIZ__*/", "/*__DIFFS__*/", "/*__CTXCODE__*/"):
        if leftover in tpl:
            print("WARNING: leftover placeholder %s" % leftover, file=sys.stderr)

    open(a.out, "w", encoding="utf-8").write(tpl)
    print("wrote %s (%d bytes)" % (a.out, len(tpl)))
    print("scenes: %s | components: %d | quiz: %d | diffs: %d | ctxcode: %d" % (
        ",".join(k for k in scenes), sum(1 for k in scenes if k.startswith("cmp_")),
        len(quiz), len(diffs), len(ctxcode)))


if __name__ == "__main__":
    main()
