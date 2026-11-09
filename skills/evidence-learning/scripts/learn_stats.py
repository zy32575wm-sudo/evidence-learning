"""有据学习 · 学习统计（只用 Python 标准库）

用法：
  python learn_stats.py <vault目录>                 # 学习统计，结果同时写入 <vault>/统计.md
  python learn_stats.py kappa <文件.csv> <列A> <列B>  # 两人评分一致性（Cohen's κ）

学习统计读取 <vault>/data/attempts.csv，输出：
  1. 各条目正确率（AI 出题 与 真题/外部测验 分开算）
  2. 校准：把握度分段 vs 实际正确率，以及 Brier 分数
  3. 错因分布
  4. 到期复习（简化间隔规则；需要精确间隔请用 Anki 的 FSRS）
"""
import csv, os, sys
from collections import defaultdict, Counter
from datetime import date, timedelta

INTERVALS = [1, 3, 7, 14, 30]  # 连续答对次数 → 下次复习间隔（天）
EXTERNAL = {"真题", "外部测验"}


def read_csv(path):
    if not os.path.exists(path):
        raise SystemExit(f"找不到文件：{path}")
    for enc in ("utf-8-sig", "gbk"):  # Excel 另存的 CSV 常是 GBK
        try:
            with open(path, encoding=enc, newline="") as f:
                return [r for r in csv.DictReader(f) if any((v or "").strip() for v in r.values())]
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"无法识别编码：{path}")


def score(v):
    v = (v or "").strip()
    if v in ("对", "正确", "√"): return 1.0
    if v in ("错", "错误", "×"): return 0.0
    if v in ("部分", "半对"): return 0.5
    try:
        x = float(v)
        return x if 0 <= x <= 1 else None
    except ValueError:
        return None


def parse_date(s):
    try:
        y, m, d = map(int, s.strip().replace("/", "-").split("-")[:3])
        return date(y, m, d)
    except Exception:
        return None


def cohen_kappa(a, b):
    n = len(a)
    if n == 0:
        return None, None
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] / n * cb[k] / n for k in set(a) | set(b))
    k = (1.0 if po == 1 else 0.0) if pe == 1 else (po - pe) / (1 - pe)
    return k, po


def kappa_level(k):
    if k is None: return "-"
    return "很差" if k <= .2 else "一般" if k <= .4 else "中等" if k <= .6 else "较好" if k <= .8 else "非常好"


def stats(vault):
    rows = read_csv(os.path.join(vault, "data", "attempts.csv"))
    recs = []
    for r in rows:
        s = score(r.get("结果"))
        if s is None:
            continue
        c = (r.get("把握度") or "").strip()
        recs.append({**r, "_s": s, "_c": float(c) / 100 if c.replace(".", "", 1).isdigit() else None,
                     "_d": parse_date(r.get("日期", "")), "_ext": (r.get("题目来源") or "").strip() in EXTERNAL})
    out = [f"# 学习统计（{date.today()}，共 {len(recs)} 题）\n"]

    # 1. 条目正确率
    out.append("## 1. 各条目正确率\n")
    out.append("| 条目 | AI出题 正确率（题数） | 真题/外部 正确率（题数） |")
    out.append("|---|---|---|")
    by_item = defaultdict(lambda: {"ai": [], "ext": []})
    for r in recs:
        by_item[r.get("条目", "").strip() or "(未填)"]["ext" if r["_ext"] else "ai"].append(r["_s"])
    fmt = lambda v: f"{sum(v)/len(v):.0%}（{len(v)}）" if v else "-"
    for item, g in sorted(by_item.items(), key=lambda kv: (sum(kv[1]["ai"] + kv[1]["ext"]) / max(1, len(kv[1]["ai"] + kv[1]["ext"])))):
        out.append(f"| {item} | {fmt(g['ai'])} | {fmt(g['ext'])} |")
    out.append("\n> 只有「真题/外部」一列能当证据；AI 出题的正确率只反映练习情况。")

    # 2. 校准
    out.append("\n## 2. 校准：把握度 vs 实际正确率\n")
    cal = [r for r in recs if r["_c"] is not None]
    if cal:
        out.append("| 把握度区间 | 题数 | 平均把握度 | 实际正确率 | 偏差 |")
        out.append("|---|---|---|---|---|")
        bins = [(0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01)]
        for lo, hi in bins:
            g = [r for r in cal if lo <= r["_c"] < hi]
            if not g:
                continue
            mc = sum(r["_c"] for r in g) / len(g)
            acc = sum(r["_s"] for r in g) / len(g)
            out.append(f"| {lo:.0%}–{min(hi, 1):.0%} | {len(g)} | {mc:.0%} | {acc:.0%} | {mc - acc:+.0%} |")
        brier = sum((r["_c"] - r["_s"]) ** 2 for r in cal) / len(cal)
        over = sum(r["_c"] - r["_s"] for r in cal) / len(cal)
        out.append(f"\nBrier 分数 {brier:.3f}（越低越好，总是报 50% 得 0.25）；整体{'高估' if over > 0 else '低估'}自己 {abs(over):.0%}。")
    else:
        out.append("（没有把握度数据：每题作答前请先报 0–100 的把握度）")

    # 3. 错因
    out.append("\n## 3. 错因分布\n")
    errs = Counter((r.get("错因") or "").strip() for r in recs if r["_s"] < 1 and (r.get("错因") or "").strip())
    if errs:
        out.append("| 错因 | 次数 |")
        out.append("|---|---|")
        for k, v in errs.most_common():
            out.append(f"| {k} | {v} |")
    else:
        out.append("（暂无错因记录）")

    # 4. 到期复习
    out.append("\n## 4. 到期复习（按条目）\n")
    hist = defaultdict(list)
    for r in recs:
        if r["_d"]:
            hist[r.get("条目", "").strip() or "(未填)"].append((r["_d"], r["_s"]))
    due = []
    for item, h in hist.items():
        h.sort()
        streak = 0
        for _, s in h:
            streak = streak + 1 if s >= 1 else 0
        last = h[-1][0]
        nxt = last + timedelta(days=INTERVALS[min(streak, len(INTERVALS)) - 1] if streak else 1)
        due.append((nxt, item, streak))
    today = date.today()
    lines = [f"| {item} | {nxt} | {streak} |" for nxt, item, streak in sorted(due) if nxt <= today + timedelta(days=1)]
    if lines:
        out.append("| 条目 | 应复习日期 | 连续答对次数 |")
        out.append("|---|---|---|")
        out.extend(lines)
    else:
        out.append("（今天和明天没有到期的条目）")

    text = "\n".join(out)
    print(text)
    with open(os.path.join(vault, "统计.md"), "w", encoding="utf-8") as f:
        f.write(text + "\n")


def kappa_cmd(path, ca, cb):
    rows = read_csv(path)
    pairs = [((r.get(ca) or "").strip(), (r.get(cb) or "").strip()) for r in rows]
    pairs = [(a, b) for a, b in pairs if a and b]
    k, po = cohen_kappa([a for a, _ in pairs], [b for _, b in pairs])
    if k is None:
        raise SystemExit("没有可比较的数据")
    print(f"样本 {len(pairs)} 条｜一致率 {po:.0%}｜κ = {k:.2f}（{kappa_level(k)}）")
    if len(pairs) < 10:
        print("样本少于 10 条，仅供参考。")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "kappa":
        if len(sys.argv) != 5:
            raise SystemExit("用法：python learn_stats.py kappa <文件.csv> <列A> <列B>")
        kappa_cmd(*sys.argv[2:5])
    elif len(sys.argv) == 2:
        stats(sys.argv[1])
    else:
        print(__doc__)
