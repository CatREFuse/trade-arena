# Trade Arena Skill Landing 与参赛设置流实现计划

> For agentic workers: follow this plan incrementally. Keep edits focused, preserve existing registration and trading behavior, and do not reintroduce landing logic into Python scripts.

**Goal:** 为 `trade-arena` Skill 落地新的 Agent 驱动式 landing 结构：由 `SKILL.md` 负责启动规则，由 `references/landing-outline.md` 负责问答大纲，由 Agent 在自然语言对话中完成策略整理、`strategy.md` 写入和定时任务建议。

**Architecture:** 以 `cocoloop-trade-arena/SKILL.md` 作为规则入口，以 `cocoloop-trade-arena/references/landing-outline.md` 作为 landing 唯一问答大纲；`cocoloop-trade-arena/scripts/quickstart.py` 仅保留手动辅助能力；同步更新 runtime 副本 `skill-runtime/cocoloop-trade-arena/`。

**Tech Stack:** markdown docs, JSON config, Python 3 helper script, hosted skill ZIP packaging

**Spec:** [2026-04-08-trade-arena-setup-flow-design.md](/Users/tanshow/Developer/trade-arena/docs/superpowers/specs/2026-04-08-trade-arena-setup-flow-design.md)

---

## 实现原则

- landing 过程完全不写进 Python 脚本
- 启动守门由 Skill 规则层描述，不在辅助脚本里实现并行主入口
- `landing-outline.md` 是 landing 的唯一问答大纲来源
- `strategy.md` 是唯一策略正文文件，位置与 `config.json` 同级
- `config.json` 只存轻量状态，不存长文本策略
- 用户主入口始终是 Skill 自然语言，不要求用户直接运行 Python 脚本
- 定时任务建议只生成建议，并把创建决定交回给用户
- `cocoloop-trade-arena/` 与 `skill-runtime/cocoloop-trade-arena/` 必须保持一致

---

## Task 1: 规则入口收口到 `SKILL.md`

**Files:**
- Update: `cocoloop-trade-arena/SKILL.md`
- Update: `skill-runtime/cocoloop-trade-arena/SKILL.md`

- [ ] **Step 1: 明确启动守门规则**

在 `SKILL.md` 顶部写清楚：

- 每次主动运行 Skill 都先静默检查更新
- 每次主动运行都检查 `strategy.md`
- 缺失或损坏时必须进入 landing
- 命中版本迁移时必须进入 landing

- [ ] **Step 2: 增加 landing 大纲引用**

明确声明：

- 一旦进入 landing，Agent 必须读取 `references/landing-outline.md`
- `landing-outline.md` 是 landing 的唯一问答大纲来源
- 它提供推荐问法、三个常见选项、推荐逻辑和自由输入处理规则

- [ ] **Step 3: 收紧脚本边界说明**

在 `SKILL.md` 中明确写出：

- `scripts/quickstart.py` 只是手动辅助入口
- 不再用它承载 landing、策略整理、定时任务建议和启动守门

---

## Task 2: 新增 landing 大纲文件

**Files:**
- Create: `cocoloop-trade-arena/references/landing-outline.md`
- Create: `skill-runtime/cocoloop-trade-arena/references/landing-outline.md`

- [ ] **Step 1: 写开场规则**

包含：

- landing 要先介绍什么能力
- 首次安装和升级迁移如何区分开场
- 三个入口如何给出

- [ ] **Step 2: 写策略采集主线**

为每个问题定义：

- 为什么要问
- 三个常见选项
- 推荐逻辑
- 自由输入如何处理

最少覆盖：

- 总体目标
- 关注市场
- 出手条件
- 加减仓方式
- 风险底线
- 观察重点
- 调度偏好

- [ ] **Step 3: 写策略确认与写入规则**

明确：

- 用户确认前不写文件
- 用户确认后写入 `strategy.md`
- 若存在 `strategy.MD`，统一迁为小写
- 不把策略正文写入 `config.json`

- [ ] **Step 4: 写定时任务建议规则**

明确：

- 先结合当前策略和宿主环境给出建议
- 先给基础版，再给相关市场增强版
- 给出“可以直接拿去创建任务的描述”
- 是否创建必须由用户自己决定

- [ ] **Step 5: 写逃逸与重入规则**

明确：

- 任意节点都允许“我自己定义”
- 已有 `strategy.md` 时先总结当前策略，再决定微调、重写或只重生成定时任务建议
- 文件损坏时进入修复或重建分支

---

## Task 3: 收缩 `quickstart.py` 为手动辅助脚本

**Files:**
- Update: `cocoloop-trade-arena/scripts/quickstart.py`
- Update: `skill-runtime/cocoloop-trade-arena/scripts/quickstart.py`

- [ ] **Step 1: 移除 landing 主流程**

删除或下线：

- landing 入口判断
- landing 提问流程
- 策略采集状态机
- 定时任务建议状态机
- landing 专用 CLI 参数

- [ ] **Step 2: 保留辅助能力**

保留：

- 手动检查更新
- 托管包覆盖更新
- 手动辅助注册
- 刷新账户信息
- 查看单只股票行情
- 查看三地持仓汇总

- [ ] **Step 3: 输出正确 handoff 提示**

默认运行脚本时要明确告诉用户：

- landing 和设置流在 Skill 对话里完成
- 普通使用者应回到宿主说“配置 trade arena”之类的话
- 脚本只适合做手动辅助动作

- [ ] **Step 4: 继续保护更新覆盖边界**

确认更新包覆盖时继续保护：

- `config.json`
- `strategy.md`
- `strategy.MD`

---

## Task 4: 轻量状态与配置模板同步

**Files:**
- Update: `cocoloop-trade-arena/config.json`
- Update if needed: `skill-runtime/cocoloop-trade-arena/config.json`

- [ ] **Step 1: 收口 `setup_state` 字段**

配置模板中保留最少状态：

- `landing_last_seen_version`
- `landing_last_completed_version`
- `strategy_last_updated_at`
- `schedule_last_generated_at`
- `runtime_capability`
- `last_update_error`

- [ ] **Step 2: 移除已不再需要的脚本侧字段**

例如脚本实现遗留的：

- `strategy_capture_mode`

若字段仍有业务意义，再在 Skill 规则层重新定义；否则从模板中移除。

---

## Task 5: 参考文档与版本示例同步

**Files:**
- Update: `cocoloop-trade-arena/references/api.md`
- Update if needed: `cocoloop-trade-arena/references/errors.md`
- Update runtime mirrors accordingly

- [ ] **Step 1: 同步版本示例**

把 API 示例里的 Skill 版本号同步到当前版本。

- [ ] **Step 2: 保持 runtime 镜像一致**

确认源码包和 runtime 副本的下列文件一致：

- `SKILL.md`
- `references/landing-outline.md`
- `references/api.md`
- `scripts/quickstart.py`

---

## Task 6: 测试与回归

**Files:**
- Update: `cocoloop-trade-arena/tests/test_quickstart.py`
- Update docs only if test commands change materially

- [ ] **Step 1: 以新边界重写 helper 测试**

测试重点改成：

- 配置模板兼容读取
- 更新覆盖时保护 `config.json` 和 `strategy.md`
- 手动更新检查能返回远端版本信息
- 遗留 `strategy.MD` 可兼容读取
- helper 启动会正确把用户引导回 Skill 对话

- [ ] **Step 2: 跑 focused 验证**

至少执行：

```bash
python3 -m py_compile cocoloop-trade-arena/scripts/quickstart.py skill-runtime/cocoloop-trade-arena/scripts/quickstart.py cocoloop-trade-arena/tests/test_quickstart.py
pytest -q cocoloop-trade-arena/tests/test_quickstart.py
python3 skill-runtime/cocoloop-trade-arena/scripts/quickstart.py
```

- [ ] **Step 3: 保留项目级回归边界**

如果本轮没有改后端和前端业务逻辑，不强制重跑整套网站回归。  
如果后续又改到站内文案或服务端接口，再补：

```bash
cd /Users/tanshow/Developer/trade-arena/backend && pytest -q
cd /Users/tanshow/Developer/trade-arena && bash scripts/dev_self_check.sh
cd /Users/tanshow/Developer/trade-arena && BASE_URL=http://localhost:3000 bash scripts/online_regression.sh
```

---

## Task 7: 交付与收尾

**Files:**
- Update: `docs/superpowers/specs/2026-04-08-trade-arena-setup-flow-design.md` only if needed
- Update: this plan file
- Update any runtime mirror files affected

- [ ] **Step 1: 检查工作区残留**

提交前只纳入实现文件，不要误带：

- runtime 本地运行态 `config.json`
- 临时产物目录
- 用户本地策略文件

- [ ] **Step 2: 记录验证结果**

交付说明中固定包含：

- 修改文件
- 验证命令
- 结果摘要
- 未提交的本地状态文件

---

## 推荐实施顺序

- [ ] Phase A: Task 1 规则入口收口到 `SKILL.md`
- [ ] Phase B: Task 2 新增 landing 大纲文件
- [ ] Phase C: Task 3 收缩 `quickstart.py`
- [ ] Phase D: Task 4 轻量状态与配置模板同步
- [ ] Phase E: Task 5 参考文档与版本示例同步
- [ ] Phase F: Task 6 测试与回归
- [ ] Phase G: Task 7 交付与收尾

---

## 风险与注意事项

- 旧脚本式 landing 逻辑如果没有完全移除，后续维护者很容易再次沿脚本路径迭代
- runtime 镜像如果不同步，用户本地体验会和源码包设计不一致
- `strategy.md` 与 `strategy.MD` 在大小写不敏感文件系统上可能映射到同一文件，测试时要避免写死断言
- about 页面和站内说明如果后续再提 landing，需要继续保持和 `SKILL.md` 的边界一致
