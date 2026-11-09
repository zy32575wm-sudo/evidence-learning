# 有据学习 · Evidence Learning

**让 AI 像良师一样带你学会任何东西，并且用外部标准证明你真的学会了。**

大多数"AI 学习法"止步于让 AI 出计划、出题、打分。问题在于：出题的是 AI，打分的也是 AI，你可能只是**以为自己学会了**。
这个技能把学习当成一个闭环：

> 定目标 → **先定评价标准** → 诊断现状 → 练习和反馈 → **外部验证**

学习记录以本地文件的形式保存，变成你自己的资产：用得越久，AI 越了解你，下一个目标学得越快。

*English: An Agent Skill that turns an AI into an evidence-driven learning mentor — goals → rubrics first → diagnosis → practice with feedback → external validation — with a local, portable learning vault that compounds over time. Docs are in Chinese.*

---

## 能做什么
| 模式 | 你说 | 它做 |
|---|---|---|
| 深化 | "深化一下这个任务 / 提示词" | 回答专家会多做什么、新手常错什么、原始材料、标准方法、外行能核对的验收标准，再给一版不变长的改写提示词 |
| 建档 | 第一次使用 | 用两轮小问题了解你的目标和条件，建立学习库 |
| 新目标 | "我想学… / 备考 / 转行 / 刚入职" | 分阶段：可行性 → 拆解 → 评价标准 → 诊断 → 计划 → 外部验证 |
| 日常学习 | "今天学什么" | 20–30 分钟：回忆 → 示范 → 练习 → 带把握度的测验 → 你自己总结 |
| 复盘 | "复盘" | 统计正确率、校准偏差、错因；按证据更新你的"学习说明书" |

内置 4 个场景配置：**课程考试、技能习得、求职转岗、入职适应**。

## 设计原则
1. **AI 打分不算证明**：只有没见过的真题、真人评审、平台数据、真实任务结果才算
2. **原始材料优先，不编造**：结论标注 `[原文]` `[归纳]` `[推断]`，查不到就说查不到
3. **深而不大**：不堆工具和功能；一个 AI 工具 + 本地 Markdown 就能用
4. **说真话**：计划不合理、进度落后、高估自己时，直接指出
5. **数据归你**：纯文本，换任何 AI 工具都能接着用

## 安装
**Claude Code**
```bash
git clone https://github.com/zy32575wm-sudo/evidence-learning.git
# macOS / Linux
cp -r evidence-learning/skills/evidence-learning ~/.claude/skills/
# Windows（PowerShell）
Copy-Item -Recurse evidence-learning\skills\evidence-learning $HOME\.claude\skills\
```
**其他支持 Agent Skills（`SKILL.md`）格式的工具**：把 `skills/evidence-learning/` 文件夹放进该工具的技能目录。

**网页聊天（ChatGPT、豆包、DeepSeek 等）**：复制 [`prompts/单文件版.md`](prompts/单文件版.md) 里的内容粘贴到对话开头。

## 快速开始
在装好技能的工具里说：
- "我想在 3 个月内通过英语四级，每天 40 分钟。"
- "深化一下这个任务：做一份给家长看的小学数学周报。"
- "今天学什么？"

第一次使用时会在当前目录创建 `vault/` 学习库。**学习库是个人数据，不要提交到公开仓库**（本仓库的 `.gitignore` 已排除 `vault/`）。

可选：每周运行统计脚本（只需 Python 3，无第三方依赖）
```bash
python skills/evidence-learning/scripts/learn_stats.py vault
python skills/evidence-learning/scripts/learn_stats.py kappa 打分.csv 甲 乙   # 两人评分一致性
```

## 目录
```
skills/evidence-learning/
├─ SKILL.md              # 核心协议：规则 + 模式
├─ references/
│  ├─ deepen.md          # 深化任务的步骤
│  ├─ profiles.md        # 4 个场景配置
│  ├─ methods.md         # 按知识类型选方法 + 方法标准名称（标注确定性）
│  └─ vault.md           # 学习库结构、文件格式、复盘节奏、阶段转换
├─ templates/vault/      # 学习库模板
└─ scripts/learn_stats.py
prompts/单文件版.md       # 网页聊天用
```

## 现状与验证
v0.1，**还没有经过多人实测**。这个项目本身也按自己的原则验证：
- 收集真实使用案例：学习前后在**留出测验或真实结果**上的变化
- 检验换一个 AI 工具后能否直接接着用
- 收集"哪一步卡住了、哪一步没用"，删掉没用的步骤

欢迎在 Issues 里分享你的真实案例（请先去掉个人信息）。**`examples/` 只收真实跑过的案例。**

## 免责声明
本技能不承诺"包会""包通过""包就业"。涉及医疗、法律、心理、重大财务决定的问题，请咨询专业人士。

## License
MIT
