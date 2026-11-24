# 有据学习 · Evidence Learning

**让 AI 像良师一样带你学会任何东西，并且用外部标准证明你真的学会了。**

大多数"AI 学习法"止步于让 AI 出计划、出题、打分，甚至在网页里答对两道 AI 出的单选题就把节点标成"绿色已学会"。问题在于：出题的是 AI，打分的也是 AI，你可能只是**以为自己学会了**。
这个技能把学习做成一个证据闭环：

> 人定方向 → **先定评价标准与时间对账** → 诊断存量与缺口 → **跑通首站最小闭环** + 刻意练习 → **外部验证才算学会**

所有记录以本地纯文本保存，既能用纯命令行统计，也能**一键生成零依赖单文件交互看板（`看板.html`）**，电脑与手机浏览器离线通用，越用越懂你。

*English: An Agent Skill that turns an AI into an evidence-driven learning mentor — user-directed goals → rubrics & time-budgeting first → baseline diagnosis & first complete loop → deliberate practice with guided questioning → external validation (strictly separating AI practice pass from real-world proof) — backed by a portable local Markdown/CSV vault and a zero-dependency single-file HTML dashboard (`看板.html`). Docs are in Chinese.*

---

## 能做什么
| 模式 | 你说 | 它做 |
|---|---|---|
| 深化 | "深化一下这个任务 / 提示词" | 回答专家多做的 3 件事、新手 3 个错、原始材料、中英文标准方法、A 自查 + B 外部验收标准，再给一版不注水的改写提示词 |
| 建档 | 第一次使用 | 用两轮小问题摸清你想学到什么程度与现实约束，建立本地学习库 |
| 新目标 | "我想学… / 备考 / 转行 / 梳理某岗位 / 刚入职" | 可行性与时间对账 → 任务链拆解 → 评价标准先行 → 诊断（存量·缺口·首站最小闭环）→ 三档方案拍板 → 外部验证 |
| 日常学习 | "今天学什么" | 20–30 分钟：主动回忆 → 示范 + 2 个专家追问线索 → 独立练习 → 带把握度的交错测验 → 你自己写 3 行总结 |
| 碎片续接 | "手机快测 / 只有 5 分钟" | 不在电脑前时，5–10 分钟做完到期复习快测并输出可复制 CSV 记录块，回电脑无缝合并 |
| 复盘与看板 | "复盘 / 生成学习看板" | 一键生成 `统计.md` 与离线交互网页 `看板.html`（五色证据路线图、岗位任务链图谱、时间对账、把握度校准雷达） |

内置 4 个场景配置：**课程考试、技能习得、求职转岗（含岗位任务链地图）、入职适应**。

## 核心设计原则
1. **双轨状态，AI 打分不算学会**：AI 练习达标最多标为「🔵 练习通过·待外部验证」；只有未见真题限时测、真人盲评、平台真实数据或实际任务交付通过，才晋升为「🟢 外部验证已掌握」
2. **人定方向，先算时间账**：需求模糊先反问澄清，路线提供保底/标准/深入三档方案由你拍板；可用学时预留容错余量，防计划烂尾
3. **首站最小闭环 + 岗位任务链挂钩**：拒绝孤立背概念——第 1 周先走通一次最小完整产出；求职与实战按「模块 → 动作链 → 输入/产出物 → 对接角色 → 能力与工具」拆解
4. **原始材料优先，零伪造数据**：结论标注 `[原文]` `[归纳]` `[推断]`；未采集真实招聘样本时强制标 `待采集 / null`，绝不编造行业数字
5. **独立作答铁律**：在你提交独立作答与把握度前，AI 绝不代写答案或总结
6. **深而不大，数据归你**：纯文本 Markdown/CSV/JSON + Python 标准库单脚本，换任何 AI 工具都能 5 分钟接着用

## 安装
**Claude Code / Antigravity / Codex 等支持 `SKILL.md` 的工具**
```bash
git clone https://github.com/zy32575wm-sudo/evidence-learning.git

# macOS / Linux（以 Claude Code 为例，其他工具替换为对应 skills 目录）
cp -r evidence-learning/skills/evidence-learning ~/.claude/skills/

# Windows（PowerShell）
Copy-Item -Recurse -Force evidence-learning\skills\evidence-learning $HOME\.claude\skills\
```

**网页聊天与手机端（ChatGPT、豆包、DeepSeek、Claude 网页版等）**：复制 [`prompts/单文件版.md`](prompts/单文件版.md) 里的提示词粘贴到对话开头。

## 快速开始
在装好技能的工具里说：
- "我想在 3 个月内通过英语四级，每天 40 分钟。"
- "我想转岗做短视频剪辑 / 产品经理，先帮我按真实招聘原文梳理岗位任务链和学习路线。"
- "深化一下这个任务：做一份给家长看的小学数学周报。"
- "今天学什么？" / "手机快测" / "帮我生成学习看板"

第一次使用时会在当前目录创建 `vault/` 学习库。**学习库是个人数据，不要提交到公开仓库**（`.gitignore` 已默认排除 `vault/`）。

生成统计报告与离线可视化看板（只需 Python 3 标准库，无任何第三方依赖）：
```bash
python skills/evidence-learning/scripts/learn_stats.py vault              # 同时生成 vault/统计.md 与 vault/看板.html
python skills/evidence-learning/scripts/learn_stats.py board vault        # 仅刷新离线交互网页 vault/看板.html
python skills/evidence-learning/scripts/learn_stats.py demo               # 一键生成带完整交互样例的独立 看板_预览.html
python skills/evidence-learning/scripts/learn_stats.py kappa 打分.csv 甲 乙 # 计算两人独立评分一致性（Cohen's κ）
```

## 目录结构
```
skills/evidence-learning/
├─ SKILL.md                  # 核心协议：全程铁律 + 6 种工作模式
├─ assets/
│  └─ board_template.html    # 无水印交互看板模板（有向路线画布 + 六瓣岗位关系网 + 四维雷达）
├─ references/
│  ├─ deepen.md              # 深化任务五步法
│  ├─ profiles.md            # 4 个场景配置（含岗位任务链拆解规范）
│  ├─ methods.md             # 学习科学、提问引导、任务链分析与验证方法库
│  └─ vault.md               # 学习库结构、五色证据状态机、岗位地图 JSON 与跨端续接
├─ templates/vault/          # 学习库初始模板（含时间对账计划、三栏诊断、岗位地图空骨架）
└─ scripts/learn_stats.py    # 纯标准库：双轨统计 + Brier 校准 + Cohen's κ + 单页交互看板生成
prompts/单文件版.md           # 网页聊天与手机端即粘即用版
```

## 现状与验证
当前版本 **v0.2**。本项目本身也按自己的原则迭代验证：
- 收集真实使用案例：学习前后在**留出真题或真实交付结果**上的变化
- 检验换一个 AI 工具、或在电脑与手机之间切换时能否零损耗接着用
- 收集"哪一步卡住了、哪一步没用"，持续删减冗余步骤

欢迎在 Issues 里分享你的真实案例（请先去掉个人信息）。**`examples/` 只收真实跑过的案例。**

## 免责声明
本技能不承诺"包会""包通过""包就业"。涉及医疗、法律、心理、重大财务决定的问题，请咨询专业人士。

## License
MIT
