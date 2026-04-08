# Trade Arena Skill 安装落地与参赛设置流实现计划

> For agentic workers: follow this plan incrementally. Keep edits focused, preserve existing registration and trading behavior, and do not skip docs or tests.

**Goal:** 为 `trade-arena` Skill 实现统一启动守门流程、安装与升级 landing、投资策略沉淀、宿主环境探测与定时任务建议，让用户在首次安装、版本升级和后续任意时刻都能完成或重进参赛设置。

**Architecture:** 以 Skill 自然语言说明和宿主对话为用户主入口，以 `cocoloop-trade-arena/scripts/quickstart.py` 作为包内辅助入口，扩展启动守门逻辑、策略文件读写、landing 与 setup flow 编排；同步更新 `cocoloop-trade-arena/SKILL.md`、托管 runtime 副本 `skill-runtime/cocoloop-trade-arena/` 和相关说明页。

**Tech Stack:** Python 3, markdown docs, JSON config, hosted skill ZIP packaging, existing Nuxt about page copy sync

**Spec:** [2026-04-08-trade-arena-setup-flow-design.md](/Users/tanshow/Developer/trade-arena/docs/superpowers/specs/2026-04-08-trade-arena-setup-flow-design.md)

---

## 实现原则

- 先收口启动守门逻辑，再加对话式 setup flow，避免入口分裂
- `strategy.md` 是唯一策略正文文件，位置与 `config.json` 同级
- `config.json` 只存轻量状态，不存长文本策略
- landing 文案先讲能力，再进入设置流
- 用户主入口始终是 Skill 自然语言，不要求用户具备直接运行 Python 脚本的能力
- 向导和自定义模式都必须能用，且任意节点都能切换
- 定时任务建议只生成建议表达，不直接创建宿主调度实体
- `cocoloop-trade-arena/` 与 `skill-runtime/cocoloop-trade-arena/` 必须保持一致

---

## Task 1: 启动守门与状态模型收口

**Files:**
- Update: `cocoloop-trade-arena/scripts/quickstart.py`
- Update: `cocoloop-trade-arena/config.json`
- Update: `skill-runtime/cocoloop-trade-arena/scripts/quickstart.py`
- Update: `skill-runtime/cocoloop-trade-arena/config.json`

- [ ] **Step 1: 增加 setup 状态结构**

在默认配置和保存逻辑中加入轻量 `setup_state`，至少覆盖：

- `landing_last_seen_version`
- `landing_last_completed_version`
- `strategy_last_updated_at`
- `strategy_capture_mode`
- `schedule_last_generated_at`
- `runtime_capability`
- `last_update_error`

- [ ] **Step 2: 统一版本读取与迁移标记**

补一个“当前版本是否需要 landing 迁移”的判断入口。建议由代码内常量或轻量配置声明，不要把规则散落在分支里。

- [ ] **Step 3: 重写更新检查逻辑**

把“每天最多一次自动检查”改成“每次主动运行都静默检查”。要求：

- 检查到新版本时直接自动更新
- 更新成功后继续后续守门流程
- 更新失败不阻断使用
- 更新成功时只输出简短提示，不再打印旧版整段使用说明

- [ ] **Step 4: 增加策略文件守门**

实现 Skill 根目录下 `strategy.md` / `strategy.MD` 的检测、加载和损坏判断。要求：

- 无文件时返回“必须启动 landing”
- 有文件时返回策略正文
- 文件损坏时返回“修复或重建策略”

- [ ] **Step 5: 统一守门入口函数**

在 `quickstart.py` 里抽一个单一入口，例如：

`run_startup_gate() -> StartupGateResult`

统一给出：

- 是否更新成功
- 当前本地版本
- 是否需要 landing
- 是否缺失策略
- 是否策略损坏
- 当前策略正文
- 是否命中版本迁移 landing

- [ ] **Step 6: 保护更新覆盖边界**

确认自更新逻辑继续保留 `config.json`，同时显式保护 `strategy.md` 不被更新包覆盖。

---

## Task 2: Landing 与 setup flow 主干实现

**Files:**
- Update: `cocoloop-trade-arena/scripts/quickstart.py`
- Update: `skill-runtime/cocoloop-trade-arena/scripts/quickstart.py`

- [ ] **Step 1: 新增 landing 能力介绍输出**

安装后或版本迁移触发时，landing 第一屏要清楚说明 Trade Arena Skill 能做什么：

- 看账户和三地持仓
- 看个股、指数和市场
- 买入卖出
- 看排行榜和资产变化
- 保存投资策略
- 生成定时任务建议

- [ ] **Step 2: 区分首次安装与升级用户开场**

实现两种开场语义：

- 首次安装：强调已经可以参赛，建议补齐策略和自动运行准备
- 升级用户：强调本版本新增策略与定时任务设置能力

- [ ] **Step 3: 增加三路入口**

landing 统一提供三路入口：

- 开始引导
- 我自己定义
- 稍后再说

并为“稍后再说”提供统一召回语句。

- [ ] **Step 4: 实现 setup flow 状态机**

至少支持以下主状态：

- `entry_confirm`
- `strategy_capture`
- `strategy_confirm`
- `schedule_generation`
- `done`

要求状态之间可以中断、恢复和重进。

- [ ] **Step 5: 任意节点支持逃逸**

在策略采集和定时任务建议阶段都允许用户切到自定义模式。自定义模式必须回到统一的“解析 -> 回显 -> 确认”闭环。

---

## Task 3: `strategy.md` 读写与策略整理

**Files:**
- Update: `cocoloop-trade-arena/scripts/quickstart.py`
- Update: `skill-runtime/cocoloop-trade-arena/scripts/quickstart.py`
- Create if needed: `cocoloop-trade-arena/templates/strategy.md.tmpl`
- Create if needed: `skill-runtime/cocoloop-trade-arena/templates/strategy.md.tmpl`

- [ ] **Step 1: 设计策略采集的最小字段**

为轻量模板模式定义最少问题集。建议包含：

- 主要关注市场
- 投资风格
- 仓位偏好
- 建仓 / 减仓规则
- 风险控制
- 观察触发条件
- 调度偏好

- [ ] **Step 2: 实现半结构化整理**

支持用户先给自然语言描述，再由系统补最少缺口，最后整理成策略草稿。

- [ ] **Step 3: 统一策略草稿输出**

无论来源是模板、向导还是自定义输入，都整理成同一种连续正文，不输出工程注释式文本。

- [ ] **Step 4: 写入 `strategy.md`**

确认后落盘到 Skill 根目录 `strategy.md`，并回写：

- `strategy_last_updated_at`
- `strategy_capture_mode`

- [ ] **Step 5: 支持重载与微调**

已有 `strategy.md` 时，允许：

- 先总结当前策略
- 选择微调
- 选择整体重写
- 跳过策略阶段直接重生成定时建议

---

## Task 4: 宿主环境探测与定时任务建议

**Files:**
- Update: `cocoloop-trade-arena/scripts/quickstart.py`
- Update: `skill-runtime/cocoloop-trade-arena/scripts/quickstart.py`
- Update if needed: `cocoloop-trade-arena/SKILL.md`
- Update if needed: `skill-runtime/cocoloop-trade-arena/SKILL.md`

- [ ] **Step 1: 定义能力层级**

先实现稳定的能力层级判断，而不是平台品牌判断。至少输出：

- `automation`
- `external_schedule`
- `unknown`

- [ ] **Step 2: 设计基础版建议**

输出一套低负担的统一运行节奏，适合作为首次配置默认建议。

- [ ] **Step 3: 设计市场增强版建议**

按 A 股、港股、美股给增强建议，但不强迫三个市场一起开启。建议生成要参考 `strategy.md` 的风格和用户偏好。

- [ ] **Step 4: 输出宿主可执行表达**

每次生成结果都包含：

- 识别到的环境类型
- 推荐节奏
- 一段当前用户可以直接采用的设置语句或配置草案

- [ ] **Step 5: 支持自定义调度输入**

如果用户直接给自己的运行节奏，就不要继续强推系统建议，而是整理、确认并输出适合宿主的表达版本。

- [ ] **Step 6: 回写调度状态**

生成建议后更新：

- `schedule_last_generated_at`
- `runtime_capability`

---

## Task 5: Skill 文案与说明同步

**Files:**
- Update: `cocoloop-trade-arena/SKILL.md`
- Update: `skill-runtime/cocoloop-trade-arena/SKILL.md`
- Update: `frontend/pages/about.vue`
- Update if needed: `frontend/composables/useParticipationCommand.ts`

- [ ] **Step 1: 更新 SKILL 顶部说明**

把当前“参赛流程及操作说明”改成新版结构，要求：

- 先介绍 Skill 能做什么
- 再介绍策略和定时任务设置能力
- 再给出安装后和升级后的下一步

- [ ] **Step 2: 删除与新版行为冲突的旧说明**

例如“每天最多自动检查一次更新”等旧规则，必须同步改掉。

- [ ] **Step 3: 同步 about 页面**

`frontend/pages/about.vue` 的“参赛流程及操作说明”要与新版 Skill 逻辑一致，但文案仍然面向用户，不出现工程式解释。

- [ ] **Step 4: 校准 copy 内容**

复查所有新增文案，确保：

- 不把功能说明写进用户最终文案
- 不出现工程 comment 风格的句子
- 不使用被项目约束拒绝的表达方式

---

## Task 6: 测试覆盖与回归

**Files:**
- Create or Update: `backend/tests/` only if server API affected
- Create: `cocoloop-trade-arena/tests/` if skill test layout is introduced
- Or create lightweight verification script under `cocoloop-trade-arena/scripts/`
- Update docs if test command changes

- [ ] **Step 1: 设计启动守门测试样例**

覆盖：

- 无更新 + 无策略文件
- 无更新 + 有策略文件
- 有更新 + 更新成功
- 有更新 + 更新失败
- 旧版升级命中 landing 迁移

- [ ] **Step 2: 设计策略文件测试样例**

覆盖：

- `strategy.md` 缺失
- `strategy.md` 可读
- `strategy.md` 损坏
- `strategy.MD` 兼容读取

- [ ] **Step 3: 设计 flow 测试样例**

覆盖：

- 向导模式
- 自定义模式
- 中途逃逸
- 只改策略
- 只重生成调度建议

- [ ] **Step 4: 跑项目要求的回归命令**

执行前先按要求阅读测试手册，然后至少计划运行：

```bash
cd /Users/tanshow/Developer/trade-arena/backend && pytest -q
cd /Users/tanshow/Developer/trade-arena && bash scripts/dev_self_check.sh
cd /Users/tanshow/Developer/trade-arena && BASE_URL=http://localhost:3000 bash scripts/online_regression.sh
```

若本轮实现主要在 Skill 包内部，还应补一组本地脚本级 smoke 验证，确保安装、更新、landing、策略写入、定时建议生成路径通畅。

---

## Task 7: 文档与托管副本收尾

**Files:**
- Update: `docs/developer-handbook.md` if file map changes materially
- Update: `docs/testing-process-manual.md` if testing flow changes
- Update: `docs/testing-checklist.md` if regression checklist changes
- Update any hosted runtime mirror files affected

- [ ] **Step 1: 同步文档入口**

如果启动方式、验证方式或关键文件地图变化明显，更新开发与测试文档。

- [ ] **Step 2: 检查托管 Skill 包一致性**

确认 `cocoloop-trade-arena/` 与 `skill-runtime/cocoloop-trade-arena/` 的关键文件一致，避免下载包与源码行为不一致。

- [ ] **Step 3: 记录验证结果**

整理实现交付记录，包含：

- 修改文件
- 验证命令
- 结果摘要
- 风险与后续

---

## 推荐实施顺序

- [ ] Phase A: Task 1 启动守门与状态模型
- [ ] Phase B: Task 2 Landing 与 setup flow 主干
- [ ] Phase C: Task 3 `strategy.md` 读写与策略整理
- [ ] Phase D: Task 4 宿主环境探测与定时任务建议
- [ ] Phase E: Task 5 Skill 文案与说明同步
- [ ] Phase F: Task 6 测试覆盖与回归
- [ ] Phase G: Task 7 文档与托管副本收尾

---

## 风险与注意事项

- 现有自更新逻辑会在更新后打印旧版使用说明，实现时要避免旧逻辑残留造成重复或冲突
- 更新包覆盖逻辑当前只保护 `config.json`，实现时必须把 `strategy.md` 也纳入保护范围
- 如果 setup flow 直接堆在 `quickstart.py` 顶层函数里，文件会继续膨胀；实现时应尽量拆出清晰的辅助函数
- about 页面和 Skill 文案必须同步，不然用户会遇到站内说明和实际行为不一致
- 宿主能力探测只需做到稳定可用，不要在第一版过度追求覆盖所有平台
