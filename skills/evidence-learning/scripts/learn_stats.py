"""有据学习 · 学习统计与无水印交互看板生成（只用 Python 3 标准库）

用法：
  python learn_stats.py <vault目录>                 # 生成 <vault>/统计.md 与 <vault>/看板.html
  python learn_stats.py board <vault目录>           # 仅刷新离线交互网页 <vault>/看板.html
  python learn_stats.py demo [输出HTML路径]         # 生成一份带完整交互样例的独立看板 HTML（默认 ./看板_预览.html）
  python learn_stats.py kappa <文件.csv> <列A> <列B>  # 两人独立评分一致性（Cohen's κ）

核心原则：
  1. AI 出题与真题/外部测验严格分列：AI 练习达标仅标「🔵练习达标·待外验」，唯有外部证据达标才标「🟢外部已验证」。
  2. 原始数据（data/*.csv）只追加不修改；统计.md 与 看板.html 随时可从本地纯文本重新生成。
  3. 零第三方依赖、零外部 CDN、零平台水印，生成的单文件 HTML 在电脑和手机浏览器均可离线秒开。
"""
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

INTERVALS = [1, 3, 7, 14, 30]  # 连续答对次数 → 下次复习间隔（天）
EXTERNAL = {"真题", "外部测验", "真人盲评", "线上数据", "实际交付"}


def read_text(path):
    if not os.path.exists(path):
        return ""
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return ""


def read_csv(path, allow_missing=False):
    if not os.path.exists(path):
        if allow_missing:
            return []
        raise SystemExit(f"找不到文件：{path}")
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return [r for r in csv.DictReader(f) if any((v or "").strip() for v in r.values())]
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"无法识别编码：{path}")


def score(v):
    v = (v or "").strip()
    if v in ("对", "正确", "√", "达标", "通过"):
        return 1.0
    if v in ("错", "错误", "×", "未达", "未达标"):
        return 0.0
    if v in ("部分", "半对"):
        return 0.5
    try:
        x = float(v)
        return x if 0 <= x <= 1 else None
    except ValueError:
        return None


def parse_date(s):
    try:
        y, m, d = map(int, (s or "").strip().replace("/", "-").split("-")[:3])
        return date(y, m, d)
    except Exception:
        return None


def parse_md_tables(text):
    tables = []
    lines = [ln.strip() for ln in text.splitlines()]
    i = 0
    while i < len(lines) - 1:
        if lines[i].startswith("|") and re.match(r"^\|[\s\-:|]+\|$", lines[i + 1]):
            headers = [c.strip() for c in lines[i].strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                cells = [c.strip() for c in lines[i].strip("|").split("|")]
                if any(cells):
                    row = {headers[idx]: (cells[idx] if idx < len(cells) else "") for idx in range(len(headers))}
                    rows.append(row)
                i += 1
            tables.append(rows)
        else:
            i += 1
    return tables


def extract_kv_bullet(text, key_prefix):
    for ln in text.splitlines():
        s = ln.strip().lstrip("-*").strip()
        if s.startswith(key_prefix):
            rest = s[len(key_prefix):]
            if "：" in rest:
                return rest.split("：", 1)[1].strip()
            if ":" in rest:
                return rest.split(":", 1)[1].strip()
            return rest.strip()
    return ""


def parse_float_in_text(s):
    m = re.search(r"[-+]?\d+(?:\.\d+)?", (s or "").replace(",", ""))
    return float(m.group(0)) if m else None


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
    if k is None:
        return "-"
    return "很差" if k <= .2 else "一般" if k <= .4 else "中等" if k <= .6 else "较好" if k <= .8 else "非常好"


def parse_attempts(vault):
    rows = read_csv(os.path.join(vault, "data", "attempts.csv"), allow_missing=True)
    recs = []
    for r in rows:
        s = score(r.get("结果"))
        if s is None:
            continue
        c = (r.get("把握度") or "").strip()
        conf = None
        if c:
            try:
                cv = float(c.rstrip("%"))
                conf = cv / 100.0 if cv > 1 else cv
                if not (0 <= conf <= 1):
                    conf = None
            except ValueError:
                conf = None
        src = (r.get("题目来源") or "").strip()
        recs.append({
            **r,
            "_s": s,
            "_c": conf,
            "_d": parse_date(r.get("日期", "")),
            "_ext": src in EXTERNAL,
        })
    return recs


def collect_vault_model(vault):
    today = date.today()
    recs = parse_attempts(vault) if vault and os.path.isdir(vault) else []
    sessions = read_csv(os.path.join(vault, "data", "sessions.csv"), allow_missing=True) if vault and os.path.isdir(vault) else []
    feedbacks = read_csv(os.path.join(vault, "data", "feedback.csv"), allow_missing=True) if vault and os.path.isdir(vault) else []

    ctx_txt = read_text(os.path.join(vault, "00-我", "当前处境.md")) if vault else ""
    manual_txt = read_text(os.path.join(vault, "00-我", "学习说明书.md")) if vault else ""
    cap_txt = read_text(os.path.join(vault, "01-能力地图.md")) if vault else ""

    stage = extract_kv_bullet(ctx_txt, "所处阶段")
    cur_goal = extract_kv_bullet(ctx_txt, "当前目标")
    deadline_str = extract_kv_bullet(ctx_txt, "截止日期")
    daily_min_str = extract_kv_bullet(ctx_txt, "每天可投入")
    worry = extract_kv_bullet(ctx_txt, "当前最担心的事")

    deadline_d = parse_date(deadline_str)
    daily_min = parse_float_in_text(daily_min_str)
    days_left = (deadline_d - today).days if deadline_d and deadline_d >= today else None
    calc_avail_hours = round(days_left * daily_min / 60.0 * 0.8, 1) if (days_left is not None and daily_min) else None

    rules = []
    in_verified_rules = False
    for ln in manual_txt.splitlines():
        st = ln.strip()
        if st.startswith("## "):
            in_verified_rules = "已验证" in st
            continue
        if in_verified_rules and st.startswith("- 规则"):
            val = st.split("：", 1)[-1].split(":", 1)[-1].strip()
            if val:
                rules.append(val)

    verified_map_items = {}
    for tbl in parse_md_tables(cap_txt):
        for r in tbl:
            nm = (r.get("条目") or "").strip()
            ev = (r.get("外部证据（链接 / 文件）") or r.get("外部证据") or "").strip()
            recheck_d = parse_date(r.get("复验日期", ""))
            if nm and ev:
                verified_map_items[nm] = recheck_d

    goals_root = os.path.join(vault, "02-目标") if vault else ""
    goal_dirs = []
    if goals_root and os.path.isdir(goals_root):
        subs = sorted(d for d in os.listdir(goals_root) if os.path.isdir(os.path.join(goals_root, d)))
        real_subs = [d for d in subs if d != "_模板" and not d.startswith(".")]
        goal_dirs = real_subs if real_subs else ([d for d in subs if d == "_模板"])

    active_goal_dir = os.path.join(goals_root, goal_dirs[-1]) if goal_dirs else ""
    active_goal_id = os.path.basename(active_goal_dir) if active_goal_dir and os.path.basename(active_goal_dir) != "_模板" else ""

    plan_txt = read_text(os.path.join(active_goal_dir, "计划.md")) if active_goal_dir else ""
    rubric_txt = read_text(os.path.join(active_goal_dir, "评价标准.md")) if active_goal_dir else ""
    diag_txt = read_text(os.path.join(active_goal_dir, "诊断.md")) if active_goal_dir else ""
    role_map_path = os.path.join(active_goal_dir, "岗位地图.json") if active_goal_dir else ""

    plan_title = ""
    for ln in plan_txt.splitlines():
        if ln.startswith("# 目标"):
            plan_title = ln.split("：", 1)[-1].split(":", 1)[-1].strip()
            break
    goal_name = cur_goal or plan_title or active_goal_id or "尚未设定具体目标"

    req_hours = parse_float_in_text(extract_kv_bullet(plan_txt, "标准路径预计总学时"))
    plan_avail_hours = parse_float_in_text(extract_kv_bullet(plan_txt, "截止日前可用总学时"))
    avail_hours = plan_avail_hours if plan_avail_hours is not None else calc_avail_hours
    first_loop = extract_kv_bullet(plan_txt, "**第 1 周首站最小闭环任务**") or extract_kv_bullet(plan_txt, "第 1 周首站最小闭环任务") or extract_kv_bullet(plan_txt, "每周完整任务")
    stop_loss = extract_kv_bullet(plan_txt, "**止损条件**") or extract_kv_bullet(plan_txt, "止损条件")
    if stop_loss in ("到　　月　　日，若　　　　未达到　　　　，就", ""):
        stop_loss = ""

    plan_tiers = []
    for ln in plan_txt.splitlines():
        st = ln.strip()
        if st.startswith("- [x]") or st.startswith("- [X]") or st.startswith("- [ ]"):
            checked = st[3].lower() == "x"
            label = st[5:].strip()
            if label:
                plan_tiers.append({"label": label, "selected": checked})

    rubrics = {}
    for tbl in parse_md_tables(rubric_txt):
        for r in tbl:
            nm = (r.get("条目") or "").strip()
            if nm:
                rubrics[nm] = {
                    "优秀": r.get("优秀", ""),
                    "达标": r.get("达标", ""),
                    "入门": r.get("入门", ""),
                    "未达": r.get("未达", ""),
                }

    dims = []
    for dname in ("概念理解", "操作熟练", "实战产出", "学习习惯"):
        raw = extract_kv_bullet(diag_txt, dname)
        m = re.match(r"^(\d+(?:\.\d+)?)\s*/\s*5", raw)
        val = float(m.group(1)) if m else None
        note = ""
        nm_match = re.search(r"（依据[：:](.*?)）", raw)
        if nm_match:
            note = nm_match.group(1).strip()
        dims.append({"name": dname, "score": val, "note": note})

    diag_sections = {"stock": [], "gaps": [], "first": []}
    cur_sec = None
    for ln in diag_txt.splitlines():
        st = ln.strip()
        if st.startswith("### "):
            if "存量" in st:
                cur_sec = "stock"
            elif "缺口" in st:
                cur_sec = "gaps"
            elif "首站" in st or "闭环" in st:
                cur_sec = "first"
            else:
                cur_sec = None
        elif cur_sec and (st.startswith("-") or re.match(r"^\d+\.", st)):
            cleaned = re.sub(r"^(?:[-*]|\d+\.)\s*", "", st).strip()
            if cleaned:
                diag_sections[cur_sec].append(cleaned)

    items_dict = {}
    for tbl in parse_md_tables(plan_txt):
        for r in tbl:
            nm = ""
            for k, v in r.items():
                if k.startswith("条目") and v.strip():
                    nm = v.strip()
                    break
            if nm:
                items_dict[nm] = {
                    "name": nm,
                    "module": r.get("所属模块", "").strip() or "阶段一 · 核心主线",
                    "importance": r.get("重要性", "").strip(),
                    "frequency": r.get("频率", "").strip(),
                    "difficulty": r.get("难度", "").strip(),
                    "ktype": r.get("知识类型", "").strip(),
                    "est_hours": parse_float_in_text(r.get("预计学时", "")),
                }

    for r in recs:
        nm = (r.get("条目") or "").strip()
        if nm and nm not in items_dict:
            items_dict[nm] = {
                "name": nm,
                "module": "练习记录条目",
                "importance": "",
                "frequency": "",
                "difficulty": "",
                "ktype": "",
                "est_hours": None,
            }

    fb_verified_text = []
    for fb in feedbacks:
        concl = (fb.get("结论") or "").strip()
        if concl in ("达标", "通过", "合格"):
            fb_verified_text.append(" ".join(str(v or "") for v in fb.values()))

    by_item_recs = defaultdict(list)
    for r in recs:
        nm = (r.get("条目") or "").strip() or "(未填条目)"
        by_item_recs[nm].append(r)

    nodes = []
    due_items = []
    blindspot_items = []

    all_item_names = list(items_dict.keys())
    for nm in by_item_recs:
        if nm not in items_dict:
            all_item_names.append(nm)

    for nm in all_item_names:
        meta = items_dict.get(nm, {"name": nm, "module": "其他", "importance": "", "frequency": "", "difficulty": "", "ktype": "", "est_hours": None})
        irecs = by_item_recs.get(nm, [])
        irecs_sorted = sorted(irecs, key=lambda x: (x["_d"] or date(1970, 1, 1)))

        ai_scores = [x["_s"] for x in irecs_sorted if not x["_ext"]]
        ext_scores = [x["_s"] for x in irecs_sorted if x["_ext"]]

        streak = 0
        last_d = None
        for x in irecs_sorted:
            if x["_d"]:
                last_d = x["_d"]
            streak = streak + 1 if x["_s"] >= 1.0 else 0

        nxt_due = None
        is_due = False
        map_recheck = verified_map_items.get(nm)
        if map_recheck:
            nxt_due = map_recheck
            is_due = nxt_due <= today
            if is_due:
                due_items.append((nxt_due, nm, streak))
        elif last_d:
            nxt_due = last_d + timedelta(days=INTERVALS[min(streak, len(INTERVALS)) - 1] if streak else 1)
            is_due = nxt_due <= today
            due_items.append((nxt_due, nm, streak))

        has_high_conf_err = any((x["_c"] is not None and x["_c"] >= 0.75 and x["_s"] < 0.5) for x in irecs_sorted[-3:])
        if has_high_conf_err:
            blindspot_items.append(nm)

        in_fb = any(nm in t for t in fb_verified_text)
        ext_passed = (nm in verified_map_items) or in_fb or (len(ext_scores) >= 2 and (sum(ext_scores) / len(ext_scores)) >= 0.8)
        recent_all = [x["_s"] for x in irecs_sorted[-3:]]
        ai_passed = (len(irecs_sorted) >= 2 and (sum(recent_all) / len(recent_all)) >= 0.8)

        if has_high_conf_err or (is_due and irecs_sorted):
            status = "due_or_blocked"
        elif ext_passed:
            status = "verified"
        elif ai_passed:
            status = "ai_passed"
        elif irecs_sorted:
            status = "practicing"
        else:
            status = "todo"

        nodes.append({
            **meta,
            "status": status,
            "ever_verified": ext_passed,
            "is_due": is_due,
            "high_conf_err": has_high_conf_err,
            "next_due": str(nxt_due) if nxt_due else "",
            "streak": streak,
            "ai_count": len(ai_scores),
            "ai_acc": round(sum(ai_scores) / len(ai_scores), 3) if ai_scores else None,
            "ext_count": len(ext_scores),
            "ext_acc": round(sum(ext_scores) / len(ext_scores), 3) if ext_scores else None,
            "rubric": rubrics.get(nm, {}),
            "recent": [
                {
                    "date": x.get("日期", ""),
                    "q": x.get("题目", ""),
                    "ans": x.get("作答", ""),
                    "res": x.get("结果", ""),
                    "conf": round(x["_c"] * 100) if x["_c"] is not None else None,
                    "err": x.get("错因", ""),
                    "src": x.get("题目来源", "") or "AI出题",
                }
                for x in irecs_sorted[-5:]
            ],
        })

    cal = [r for r in recs if r["_c"] is not None]
    cal_bins = []
    brier = None
    over_bias = None
    if cal:
        bins = [(0, .2), (.2, .4), (.4, .6), (.6, .8), (.8, 1.01)]
        for lo, hi in bins:
            g = [r for r in cal if lo <= r["_c"] < hi]
            if g:
                mc = sum(r["_c"] for r in g) / len(g)
                acc = sum(r["_s"] for r in g) / len(g)
                cal_bins.append({
                    "label": f"{lo:.0%}–{min(hi, 1):.0%}",
                    "count": len(g),
                    "mean_conf": round(mc, 3),
                    "acc": round(acc, 3),
                    "diff": round(mc - acc, 3),
                })
        brier = round(sum((r["_c"] - r["_s"]) ** 2 for r in cal) / len(cal), 3)
        over_bias = round(sum(r["_c"] - r["_s"] for r in cal) / len(cal), 3)

    errs = Counter((r.get("错因") or "").strip() for r in recs if r["_s"] < 1 and (r.get("错因") or "").strip())
    err_list = [{"reason": k, "count": v} for k, v in errs.most_common()]

    total_mins = 0.0
    session_dates = set()
    recent_sessions = []
    for s in sessions:
        m = parse_float_in_text(s.get("分钟", ""))
        if m:
            total_mins += m
        d = parse_date(s.get("日期", ""))
        if d:
            session_dates.add(d)
        recent_sessions.append({
            "date": s.get("日期", ""),
            "mode": s.get("模式", ""),
            "mins": s.get("分钟", ""),
            "done": s.get("完成内容", ""),
        })
    for r in recs:
        if r["_d"]:
            session_dates.add(r["_d"])

    active_streak_days = 0
    cursor = today if today in session_dates else (today - timedelta(days=1) if (today - timedelta(days=1)) in session_dates else None)
    while cursor and cursor in session_dates:
        active_streak_days += 1
        cursor -= timedelta(days=1)

    role_map = None
    if role_map_path and os.path.exists(role_map_path):
        try:
            raw_rm = json.loads(read_text(role_map_path))
            has_role = bool((raw_rm.get("role_name") or "").strip()) or any(
                (m.get("name") or "").strip() for m in raw_rm.get("modules", [])
            )
            if has_role:
                role_map = raw_rm
        except Exception:
            role_map = None

    due_ready = [
        {"date": str(nxt), "item": nm, "streak": st}
        for nxt, nm, st in sorted(due_items)
        if nxt <= today + timedelta(days=1)
    ]

    return {
        "generated_at": str(today),
        "goal_id": active_goal_id,
        "goal_name": goal_name,
        "stage": stage or "未填写阶段",
        "deadline": deadline_str,
        "days_left": days_left,
        "daily_min": daily_min,
        "worry": worry,
        "time_budget": {
            "required_hours": req_hours,
            "available_hours": avail_hours,
            "surplus_hours": round(avail_hours - req_hours, 1) if (avail_hours is not None and req_hours is not None) else None,
        },
        "first_loop": first_loop or (diag_sections["first"][0] if diag_sections["first"] else ""),
        "stop_loss": stop_loss,
        "plan_tiers": plan_tiers,
        "rules": rules,
        "dims": dims,
        "diag": diag_sections,
        "nodes": nodes,
        "total_attempts": len(recs),
        "total_mins": round(total_mins),
        "active_streak_days": active_streak_days,
        "recent_sessions": recent_sessions[-5:],
        "calibration": {
            "bins": cal_bins,
            "brier": brier,
            "over_bias": over_bias,
        },
        "errors": err_list,
        "due": due_ready,
        "blindspots": blindspot_items,
        "feedbacks": [
            {
                "date": fb.get("日期", ""),
                "method": fb.get("验证方式", ""),
                "source": fb.get("评价人或来源", ""),
                "result": fb.get("结果", ""),
                "conclusion": fb.get("结论", ""),
            }
            for fb in feedbacks
        ],
        "role_map": role_map,
    }


def build_demo_model():
    """通用教学演示数据集（零个人信息，完整展示五态路线图、岗位六瓣关系网与四维校准雷达）"""
    today_s = str(date.today())
    return {
        "generated_at": today_s,
        "goal_id": "demo_video_editor",
        "goal_name": "短视频剪辑师 · 求职转岗实战",
        "stage": "求职转岗（样例演示）",
        "deadline": "2026-12-30",
        "days_left": 36,
        "daily_min": 60,
        "worry": "软件按钮都认识，但没独立交付过一条前3秒留得住人的成片",
        "time_budget": {
            "required_hours": 18.0,
            "available_hours": 28.8,
            "surplus_hours": 10.8,
        },
        "first_loop": "第 1 周独立剪完一条 60 秒知识口播成片（清理气口重录 + 响度达标 -14 LUFS + 零跳切导出）",
        "stop_loss": "若第 2 周末仍未产出第 1 条外部盲评达标成片，暂停调色与特效支线，集中攻克粗剪节奏与钩子结构",
        "plan_tiers": [
            {"label": "保底最小闭环版（约 10h）：只抓单机位口播粗剪、字幕与导出交付主线", "selected": False},
            {"label": "标准求职达标版（约 18h）：主线必做 + 声音画质统一 + 2 件可盲评作品集", "selected": True},
            {"label": "深入拓展版（约 26h）：标准版 + 多机位色彩匹配与风格化动态包装挑战站", "selected": False},
        ],
        "rules": [
            "先做出一条 60 秒粗糙但完整的成片，再回头抠转场和调色（实测留出任务完成率从 40% 提升至 85%）",
            "涉及概念辨析时先看 1 个正例 + 1 个翻车反例，比直接背定义快一倍",
        ],
        "dims": [
            {"name": "概念理解", "score": 3.8, "note": "能分清粗剪/精剪与跳切成因，但钩子留存误判过一次"},
            {"name": "操作熟练", "score": 3.2, "note": "时间线快捷键已顺手，多机位调色仍生疏"},
            {"name": "实战产出", "score": 2.5, "note": "刚跑通首条 60 秒练习片，尚缺第 2 件作品"},
            {"name": "学习习惯", "score": 3.5, "note": "连续 4 天按时做主动回忆与把握度记录"},
        ],
        "diag": {
            "stock": [
                "时间线新建工程与帧率序列匹配（实测 25fps/30fps 混排排查全对）",
                "基础素材分轨入库与代理剪辑设置",
            ],
            "gaps": [
                "前3秒钩子与留存叙事结构（高把握度答错盲区，优先排雷）",
                "多机位色彩与画质统一（手机片与相机片混剪色温偏差）",
                "人声降噪与 -14 LUFS 响度标准化",
            ],
            "first": [
                "先把第一站 60 秒口播闭环走完并拿给从业者盲评，比单看 10 节调色课更有效",
            ],
        },
        "nodes": [
            {
                "name": "工程帧率序列与代理规范",
                "module": "阶段一 · 起步最小闭环",
                "importance": "高", "frequency": "高频", "difficulty": "低", "ktype": "动作", "est_hours": 1.0,
                "status": "verified", "ever_verified": True, "is_due": False, "high_conf_err": False,
                "next_due": "", "streak": 3, "ai_count": 1, "ai_acc": 1.0, "ext_count": 2, "ext_acc": 1.0,
                "rubric": {
                    "优秀": "3分钟内建好标准分轨工程，混帧率素材零丢帧零黑边",
                    "达标": "序列帧率与主素材一致，音画轨命名清晰无散落文件",
                    "入门": "能导入剪辑但偶发帧率不匹配抽帧",
                    "未达": "直接把不同比例/帧率素材硬拖进默认序列导致变形",
                },
                "recent": [
                    {"date": today_s, "q": "25fps口播混60fps空镜建序实测", "ans": "以25fps建主序列，60fps按需升格", "res": "对", "conf": 90, "err": "", "src": "真题"},
                ],
            },
            {
                "name": "粗剪清理重录口癖与自然气口",
                "module": "阶段一 · 起步最小闭环",
                "importance": "高", "frequency": "高频", "difficulty": "中", "ktype": "动作", "est_hours": 2.5,
                "status": "verified", "ever_verified": True, "is_due": False, "high_conf_err": False,
                "next_due": "", "streak": 2, "ai_count": 2, "ai_acc": 1.0, "ext_count": 2, "ext_acc": 0.9,
                "rubric": {
                    "优秀": "重录废话零残留，句间气口保留 3–6 帧自然呼吸感，闭眼听无断字",
                    "达标": "无重复句与密集口癖，偶有 1 处气口略紧但不吃字",
                    "入门": "删完废话后尾音被切碎或停顿超过 1 秒拖沓",
                    "未达": "重录句未删净或满屏生硬跳切",
                },
                "recent": [
                    {"date": today_s, "q": "8分钟原片粗剪成90秒口播盲评", "ans": "零重录残留，从业者盲评通过", "res": "对", "conf": 85, "err": "", "src": "实际交付"},
                ],
            },
            {
                "name": "字幕层级排版与导出码率规范",
                "module": "阶段一 · 起步最小闭环",
                "importance": "中", "frequency": "高频", "difficulty": "低", "ktype": "事实", "est_hours": 1.5,
                "status": "ai_passed", "ever_verified": False, "is_due": False, "high_conf_err": False,
                "next_due": "", "streak": 2, "ai_count": 3, "ai_acc": 1.0, "ext_count": 0, "ext_acc": None,
                "rubric": {
                    "优秀": "主字幕避开平台底部遮挡安全框，每行≤13字，无错别字，H.264推荐码率导出",
                    "达标": "位置统一在安全区内，断句符合语义，码率正常",
                    "入门": "偶有长句超宽或被平台点赞图标遮挡",
                    "未达": "错字频出、压边遮挡或盲目拉高码率导致体积暴涨",
                },
                "recent": [
                    {"date": today_s, "q": "竖屏口播安全框与码率测验", "ans": "底部留白避开文案区，1080p 12-16Mbps", "res": "对", "conf": 85, "err": "", "src": "AI出题"},
                ],
            },
            {
                "name": "景别切换、J-Cut与消除硬跳切",
                "module": "阶段二 · 视听流畅度",
                "importance": "高", "frequency": "高频", "difficulty": "中", "ktype": "动作", "est_hours": 2.5,
                "status": "ai_passed", "ever_verified": False, "is_due": False, "high_conf_err": False,
                "next_due": "", "streak": 2, "ai_count": 2, "ai_acc": 0.85, "ext_count": 0, "ext_acc": None,
                "rubric": {
                    "优秀": "声音先行 4–8 帧引导画面（J-Cut），同机位切气口借助B-roll或无感推拉消除跳切",
                    "达标": "关键气口无突兀人像瞬移感，声音过渡平顺",
                    "入门": "全片一刀切到底，偶尔靠花哨转场硬盖跳切",
                    "未达": "滥用旋转缩放转场，视觉眩晕",
                },
                "recent": [
                    {"date": today_s, "q": "同机位删词跳切补救方案", "ans": "切中近景115%无感裁切或铺贴切B-roll", "res": "对", "conf": 80, "err": "", "src": "AI出题"},
                ],
            },
            {
                "name": "人声降噪与响度标准化(-14 LUFS)",
                "module": "阶段二 · 视听流畅度",
                "importance": "高", "frequency": "高频", "difficulty": "中", "ktype": "解题", "est_hours": 2.0,
                "status": "practicing", "ever_verified": False, "is_due": False, "high_conf_err": False,
                "next_due": "", "streak": 0, "ai_count": 2, "ai_acc": 0.5, "ext_count": 0, "ext_acc": None,
                "rubric": {
                    "优秀": "人声清晰通透无金属电音感，BGM自动闪避低人声 12–18dB，整体响度稳定 -14 LUFS",
                    "达标": "人声不被BGM盖住，无爆音削波（Peak ≤ -1dBTP）",
                    "入门": "降噪过度导致人声发闷，或前后音量忽大忽小",
                    "未达": "BGM盖过台词或出现破音刺耳",
                },
                "recent": [
                    {"date": today_s, "q": "空调底噪素材处理练习", "ans": "降噪拉满导致齿音像机器人", "res": "部分", "conf": 60, "err": "步骤错", "src": "AI出题"},
                ],
            },
            {
                "name": "多机位色彩与画质统一",
                "module": "阶段二 · 视听流畅度",
                "importance": "中（支线）", "frequency": "中频", "difficulty": "高", "ktype": "动作", "est_hours": 2.5,
                "status": "practicing", "ever_verified": False, "is_due": False, "high_conf_err": False,
                "next_due": "", "streak": 0, "ai_count": 1, "ai_acc": 0.5, "ext_count": 0, "ext_acc": None,
                "rubric": {
                    "优秀": "借助示波器对齐手机与相机白平衡、肤色线与反差，切镜看不出设备断层",
                    "达标": "肉眼观看无明显偏绿偏黄跳色，降噪不抹成蜡像脸",
                    "入门": "直接套LUT导致高光死白或肤色发橘",
                    "未达": "两台设备切镜亮度和色温剧烈跳变",
                },
                "recent": [],
            },
            {
                "name": "前3秒钩子与留存叙事结构",
                "module": "阶段三 · 叙事与完播留存",
                "importance": "高", "frequency": "高频", "difficulty": "高", "ktype": "判断", "est_hours": 3.0,
                "status": "due_or_blocked", "ever_verified": False, "is_due": True, "high_conf_err": True,
                "next_due": today_s, "streak": 0, "ai_count": 2, "ai_acc": 0.25, "ext_count": 0, "ext_acc": None,
                "rubric": {
                    "优秀": "前3秒直接抛出反常识结果或高痛点冲突画面，每15秒有信息增量，无废话铺垫",
                    "达标": "前3秒点明观众利益点，主干逻辑顺畅不绕弯",
                    "入门": "开头还在慢吞吞自我介绍或寒暄铺垫",
                    "未达": "看了10秒仍不知视频主旨，3秒划走率极高",
                },
                "recent": [
                    {"date": today_s, "q": "挑出原片最具留存力的开场3秒", "ans": "保留了原片按时间顺序的寒暄开头", "res": "错", "conf": 85, "err": "概念不懂", "src": "AI出题"},
                ],
            },
            {
                "name": "音乐情绪曲线与卡点克制",
                "module": "阶段三 · 叙事与完播留存",
                "importance": "中", "frequency": "中频", "difficulty": "中", "ktype": "判断", "est_hours": 2.0,
                "status": "todo", "ever_verified": False, "is_due": False, "high_conf_err": False,
                "next_due": "", "streak": 0, "ai_count": 0, "ai_acc": None, "ext_count": 0, "ext_acc": None,
                "rubric": {
                    "优秀": "转折处断BGM留白突出金句，情绪递进自然不抢戏",
                    "达标": "配乐气质贴合题材，起止有淡入淡出不生切",
                    "入门": "一条热门BGM从头铺到尾毫无起伏",
                    "未达": "悲伤/严肃内容乱配欢快网红神曲",
                },
                "recent": [],
            },
            {
                "name": "真实求职样片全链路盲评交付",
                "module": "阶段四 · 外部验收交付",
                "importance": "高", "frequency": "必做", "difficulty": "高", "ktype": "判断", "est_hours": 3.0,
                "status": "todo", "ever_verified": False, "is_due": False, "high_conf_err": False,
                "next_due": "", "streak": 0, "ai_count": 0, "ai_acc": None, "ext_count": 0, "ext_acc": None,
                "rubric": {
                    "优秀": "限时独立完成2条不同类型成片，经在职剪辑师盲评达标或公开发布完播率超基准线",
                    "达标": "独立按需求单限时交片，无硬伤返工，能讲清每处删留理由",
                    "入门": "超时交付或仍需他人逐处指出跳切与音量问题",
                    "未达": "只能跟着教程临摹，换一份陌生素材无从下手",
                },
                "recent": [],
            },
        ],
        "total_attempts": 11,
        "total_mins": 145,
        "active_streak_days": 4,
        "recent_sessions": [
            {"date": today_s, "mode": "D 日常学习", "mins": "35", "done": "完成粗剪外部盲评复核 + 钩子结构错题诊断"},
        ],
        "calibration": {
            "bins": [
                {"label": "40%–60%", "count": 2, "mean_conf": 0.55, "acc": 0.50, "diff": 0.05},
                {"label": "60%–80%", "count": 3, "mean_conf": 0.75, "acc": 0.83, "diff": -0.08},
                {"label": "80%–100%", "count": 6, "mean_conf": 0.87, "acc": 0.75, "diff": 0.12},
            ],
            "brier": 0.142,
            "over_bias": 0.06,
        },
        "errors": [
            {"reason": "概念不懂", "count": 2},
            {"reason": "步骤错", "count": 2},
        ],
        "due": [
            {"date": today_s, "item": "前3秒钩子与留存叙事结构", "streak": 0},
        ],
        "blindspots": ["前3秒钩子与留存叙事结构"],
        "feedbacks": [
            {"date": today_s, "method": "从业者盲评", "source": "3年经验短视频编导", "result": "90秒口播气口顺畅零跳切", "conclusion": "达标"},
        ],
        "role_map": {
            "role_name": "短视频剪辑师",
            "industry_city_level": "内容制作 · 泛知识/口播/Vlog方向 · 初中级",
            "sample_count": None,
            "collected_at": "",
            "is_verified_sample": False,
            "salary_range_k": {"low": None, "mid": None, "high": None},
            "summary": "把原始素材与脚本意图重组成一条前3秒留人、中段信息紧凑、音画达标的成片——核心决定留下什么、删掉什么、按什么节奏给出去。",
            "modules": [
                {
                    "name": "素材与前期",
                    "tasks": [
                        {
                            "name": "素材分轨入库与代理建序",
                            "weight": 6, "frequency": "每片必做",
                            "chain": ["01 核查主机位帧率与分辨率建序列", "02 按A-roll/B-roll/音效/音乐分轨归档", "03 4K高码率素材挂代理防卡顿"],
                            "input": "原始拍摄卡素材 + 录音文件", "output": "标准化可秒开剪辑工程",
                            "collaborators": "对接摄像 / 独立完成",
                            "skills": ["工程帧率序列与代理规范"], "tools": ["Premiere Pro", "剪映专业版"],
                        },
                        {
                            "name": "粗剪剔除废片与气口顺片",
                            "weight": 9, "frequency": "高频核心",
                            "chain": ["01 通听标记重录句、口癖与卡壳", "02 保留句间3-6帧自然呼吸气口", "03 对照文稿核查核心论点无遗漏"],
                            "input": "几十条NG口播原始长素材", "output": "逻辑顺畅无废话的粗剪主干轨",
                            "collaborators": "对接编导审主干",
                            "skills": ["粗剪清理重录口癖与自然气口"], "tools": ["剪映专业版", "Premiere Pro"],
                        },
                    ],
                },
                {
                    "name": "画面与声音",
                    "tasks": [
                        {
                            "name": "人声净化与响度配平",
                            "weight": 8, "frequency": "每片必做",
                            "chain": ["01 轻度降噪避免损伤人声高频", "02 压限器拉平忽大忽小音量", "03 BGM自动闪避并校准整体至 -14 LUFS"],
                            "input": "带环境底噪的同期声轨", "output": "清晰不刺耳的混音成品轨",
                            "collaborators": "独立完成",
                            "skills": ["人声降噪与响度标准化(-14 LUFS)"], "tools": ["Audition", "DaVinci Fairlight"],
                        },
                        {
                            "name": "画质修复与多机位色彩统一",
                            "weight": 5, "frequency": "中频",
                            "chain": ["01 去噪与适度锐化（严禁抹成蜡像脸）", "02 对齐手机与相机色温及肤色线", "03 必要时补帧消除卡顿"],
                            "input": "手机片与相机片混合素材", "output": "色调质感统一的画面轨",
                            "collaborators": "独立完成",
                            "skills": ["多机位色彩与画质统一"], "tools": ["DaVinci Resolve"],
                            "jd_quote": "能处理不同拍摄设备混合素材，统一画面质感与肤色观感。",
                        },
                    ],
                },
                {
                    "name": "叙事与留存",
                    "tasks": [
                        {
                            "name": "前3秒钩子提炼与结构重排",
                            "weight": 10, "frequency": "核心竞争力",
                            "chain": ["01 从全片最炸裂结论或反常识冲突句倒提开场", "02 砍掉前10秒一切自我介绍与套话", "03 每15-20秒埋一个视觉或信息变化点"],
                            "input": "平铺直叙的原片与脚本", "output": "高3秒留存率成片结构",
                            "collaborators": "与编导/运营对齐完播数据",
                            "skills": ["前3秒钩子与留存叙事结构"], "tools": ["拉片拆解表"],
                            "jd_quote": "懂平台完播逻辑，具备二次重构叙事与提炼黄金前3秒的能力。",
                        },
                    ],
                },
                {
                    "name": "节奏与包装",
                    "tasks": [
                        {
                            "name": "J-Cut视听衔接与B-roll铺设",
                            "weight": 8, "frequency": "高频",
                            "chain": ["01 声音提前4-8帧切入消除硬切生硬感", "02 删词跳切处覆盖强相关实拍B-roll", "03 情绪转折处断BGM留白"],
                            "input": "粗剪主干轨 + 补充空镜素材", "output": "无跳切破绽的精剪时间线",
                            "collaborators": "独立完成",
                            "skills": ["景别切换、J-Cut与消除硬跳切", "音乐情绪曲线与卡点克制"], "tools": ["Premiere Pro", "剪映专业版"],
                        },
                        {
                            "name": "安全框花字层级与多端导出",
                            "weight": 7, "frequency": "每片必做",
                            "chain": ["01 校准竖屏安全区避开底部文案遮挡", "02 仅对核心金句做克制视觉强调", "03 按平台推荐码率导出并回看成片音画同步"],
                            "input": "精剪定稿工程", "output": "零错字零遮挡上线成片MP4",
                            "collaborators": "交付账号运营发布",
                            "skills": ["字幕层级排版与导出码率规范", "真实求职样片全链路盲评交付"], "tools": ["剪映专业版", "FFmpeg"],
                        },
                    ],
                },
            ],
        },
    }


def format_stats_md(model):
    out = [f"# 学习统计（{model['generated_at']}，共 {model['total_attempts']} 题）\n"]
    tb = model["time_budget"]
    if tb["required_hours"] is not None or tb["available_hours"] is not None:
        req_s = f"{tb['required_hours']} 小时" if tb["required_hours"] is not None else "待估算"
        av_s = f"{tb['available_hours']} 小时" if tb["available_hours"] is not None else "待核算"
        diff_s = f"{tb['surplus_hours']:+.1f} 小时" if tb["surplus_hours"] is not None else "-"
        out.append(f"- **当前目标**：{model['goal_name']}｜**时间对账**：标准路径需 {req_s} / 容错后可用 {av_s}（富余/缺口：{diff_s}）\n")

    out.append("## 1. 各条目正确率与证据状态\n")
    if model["nodes"]:
        out.append("| 条目 | 当前状态 | AI出题 正确率（题数） | 真题/外部 正确率（题数） |")
        out.append("|---|---|---|---|")
        status_label = {
            "verified": "🟢 外部验证已掌握",
            "ai_passed": "🔵 练习通过·待外部验证",
            "practicing": "🟡 学习/练习中",
            "due_or_blocked": "🟠 到期复习/高估盲区",
            "todo": "⚪ 未开始",
        }
        fmt = lambda acc, n: f"{acc:.0%}（{n}）" if (acc is not None and n) else "-"
        for nd in model["nodes"]:
            out.append(f"| {nd['name']} | {status_label.get(nd['status'], nd['status'])} | {fmt(nd['ai_acc'], nd['ai_count'])} | {fmt(nd['ext_acc'], nd['ext_count'])} |")
        out.append("\n> 只有「真题/外部」一列或 `feedback.csv` 外部验收能将条目晋升为 🟢；AI 出题达标最多标为 🔵。")
    else:
        out.append("（尚未拆解条目或录入作答记录）")

    out.append("\n## 2. 校准：把握度 vs 实际正确率\n")
    cal = model["calibration"]
    if cal["bins"]:
        out.append("| 把握度区间 | 题数 | 平均把握度 | 实际正确率 | 偏差 |")
        out.append("|---|---|---|---|---|")
        for b in cal["bins"]:
            out.append(f"| {b['label']} | {b['count']} | {b['mean_conf']:.0%} | {b['acc']:.0%} | {b['diff']:+.0%} |")
        bias_word = "高估" if cal["over_bias"] > 0 else ("低估" if cal["over_bias"] < 0 else "持平")
        out.append(f"\nBrier 分数 {cal['brier']:.3f}（越低越好，总是报 50% 得 0.25）；整体{bias_word}自己 {abs(cal['over_bias']):.0%}。")
    else:
        out.append("（没有把握度数据：每题作答前请先报 0–100 的把握度）")

    out.append("\n## 3. 错因分布\n")
    if model["errors"]:
        out.append("| 错因 | 次数 |")
        out.append("|---|---|")
        for e in model["errors"]:
            out.append(f"| {e['reason']} | {e['count']} |")
    else:
        out.append("（暂无错因记录）")

    out.append("\n## 4. 到期复习与高估盲区\n")
    if model["due"]:
        out.append("| 条目 | 应复习日期 | 连续答对次数 |")
        out.append("|---|---|---|")
        for d in model["due"]:
            out.append(f"| {d['item']} | {d['date']} | {d['streak']} |")
    else:
        out.append("（今天和明天没有到期的条目）")
    if model["blindspots"]:
        out.append(f"\n- **高把握度答错盲区（优先排查）**：{'、'.join(model['blindspots'])}")

    return "\n".join(out)


def load_board_template():
    skill_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tmpl_path = os.path.join(skill_root, "assets", "board_template.html")
    if not os.path.exists(tmpl_path):
        raise SystemExit(f"找不到看板前端模板：{tmpl_path}")
    return read_text(tmpl_path)


def render_board_html(vault_model, demo_model=None):
    if demo_model is None:
        demo_model = build_demo_model()
    tmpl = load_board_template()
    v_json = json.dumps(vault_model, ensure_ascii=False).replace("</", "<\\/")
    d_json = json.dumps(demo_model, ensure_ascii=False).replace("</", "<\\/")
    return tmpl.replace("__VAULT_JSON__", v_json).replace("__DEMO_JSON__", d_json)


def write_board(vault, model=None):
    if model is None:
        model = collect_vault_model(vault)
    html = render_board_html(model)
    out_path = os.path.join(vault, "看板.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def demo_cmd(out_path):
    empty_vault = collect_vault_model("")
    html = render_board_html(empty_vault, build_demo_model())
    parent = os.path.dirname(os.path.abspath(out_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"已生成独立无水印交互看板预览：{os.path.abspath(out_path)}")


def stats_cmd(vault):
    if not os.path.isdir(vault):
        raise SystemExit(f"找不到学习库目录：{vault}")
    model = collect_vault_model(vault)
    md_text = format_stats_md(model)
    print(md_text)
    stats_path = os.path.join(vault, "统计.md")
    with open(stats_path, "w", encoding="utf-8") as f:
        f.write(md_text + "\n")
    board_path = write_board(vault, model)
    print(f"\n已更新：{stats_path} 与 无水印交互看板 {board_path}")


def board_cmd(vault):
    if not os.path.isdir(vault):
        raise SystemExit(f"找不到学习库目录：{vault}")
    board_path = write_board(vault)
    print(f"已生成无水印交互学习看板：{board_path}")


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
    elif len(sys.argv) in (2, 3) and sys.argv[1] == "demo":
        target = sys.argv[2] if len(sys.argv) == 3 else "看板_预览.html"
        demo_cmd(target)
    elif len(sys.argv) == 3 and sys.argv[1] == "board":
        board_cmd(sys.argv[2])
    elif len(sys.argv) == 2 and sys.argv[1] not in ("-h", "--help"):
        stats_cmd(sys.argv[1])
    else:
        print(__doc__)
