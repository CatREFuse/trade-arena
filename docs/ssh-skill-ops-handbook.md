# Trade Arena SSH Skill 运维入口

最后更新：2026-04-02（Asia/Shanghai）

本文档用于接手本项目线上服务器运维的 Agent。  
本项目线上服务器操作强烈推荐优先使用 `ssh-skill`，不要直接手写裸 `ssh`、`scp`、`sftp` 流程。

当前线上仓库路径按项目约定使用：

```bash
/etc/nginx/website/trade-arena
```

## 1. 本地敏感文件

线上服务器凭据不要写进版本库。  
本仓库统一使用下面两个文件：

- `.env.ssh.trade-arena.example`：示例模板，可提交
- `.env.ssh.trade-arena.local`：本地实际凭据文件，已加入 `.gitignore`

推荐把账号、主机、端口、密码都放在 `.env.ssh.trade-arena.local` 里，通过环境变量注入脚本，不要把明文凭据写进文档。

## 2. ssh-skill 安装与检查

当前仓库默认按 Codex 目录约定查找：

```bash
${CODEX_HOME:-$HOME/.codex}/skills/ssh-skill
```

至少确认下面两件事：

```bash
test -f "${CODEX_HOME:-$HOME/.codex}/skills/ssh-skill/SKILL.md"
test -f "${CODEX_HOME:-$HOME/.codex}/skills/ssh-skill/scripts/ssh_execute.py"
```

`ssh-skill` 依赖 `paramiko`，缺失时先安装：

```bash
pip3 install paramiko
```

如果当前 Codex 环境里还没有 `ssh-skill`，先把该 skill 目录安装到：

```bash
${CODEX_HOME:-$HOME/.codex}/skills/ssh-skill
```

安装或补齐后，重启 Codex，再继续后面的配置步骤。

## 3. 推荐工作流

统一按下面两段走：

1. 首次接手时，用密码认证完成一次引导
2. 引导完成后，长期运维全部切到密钥认证和复用连接

这样做的目标很直接：

- 首次接入成本低
- 后续命令更快
- 远程命令不再依赖密码守护进程
- 接手 Agent 的行为更稳定

## 4. 生成本项目线上服务器配置

先复制模板：

```bash
cp .env.ssh.trade-arena.example .env.ssh.trade-arena.local
```

再把本地凭据文件补全，然后执行：

```bash
bash scripts/setup_trade_arena_ssh_skill.sh
```

这个脚本会做三件事：

1. 从 `.env.ssh.trade-arena.local` 读取服务器信息
2. 调用 `ssh_config_manager_v3.py` 创建或更新 `~/.ssh/config` 中的别名
3. 把密码作为 ssh-skill 可识别的注释元数据写入该别名块

默认别名：

```bash
trade-arena-prod
```

## 5. 性能优化到位的做法

密码认证只用于第一次把公钥送上服务器。  
完成后，统一执行：

```bash
bash scripts/bootstrap_trade_arena_ssh_key_auth.sh
```

这个脚本会完成下面几件事：

1. 在本地生成专用 `ed25519` 密钥 `~/.ssh/trade_arena_ops`
2. 用当前密码认证别名把公钥部署到线上服务器
3. 把 `trade-arena-prod` 别名切到密钥认证
4. 为该别名补齐连接复用参数

最终别名会固定包含这些优化项：

- `IdentityFile ~/.ssh/trade_arena_ops`
- `IdentitiesOnly yes`
- `PreferredAuthentications publickey`
- `ControlMaster auto`
- `ControlPath ~/.ssh/cm-%C`
- `ControlPersist 600`

这样后续走的是原生 SSH 快线，不再依赖密码认证。

## 6. 验证方式

列出或查找配置：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/ssh-skill/scripts/ssh_config_manager_v3.py" find "trade-arena-prod"
```

执行远程命令：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/ssh-skill/scripts/ssh_execute.py" "trade-arena-prod" "hostname && whoami"
```

查看运维状态：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/ssh-skill/scripts/ssh_execute.py" "trade-arena-prod" "cd /etc/nginx/website/trade-arena && bash scripts/opsctl.sh status"
```

查看线上日志：

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/ssh-skill/scripts/ssh_execute.py" "trade-arena-prod" "tail -n 200 /var/log/trade-arena-deploy.log"
```

直接走最快的原生 SSH 包装脚本：

```bash
bash scripts/trade_arena_ssh.sh "cd /etc/nginx/website/trade-arena && bash scripts/opsctl.sh status"
```

预热复用连接：

```bash
bash scripts/trade_arena_ssh_master.sh start
```

检查复用连接状态：

```bash
bash scripts/trade_arena_ssh_master.sh status
```

## 7. 推荐用法

接手线上问题时，优先按这个顺序：

1. 先执行 `bash scripts/setup_trade_arena_ssh_skill.sh`
2. 第一次接手或本机没有密钥时，执行 `bash scripts/bootstrap_trade_arena_ssh_key_auth.sh`
3. 执行 `bash scripts/trade_arena_ssh_master.sh start`
4. 再执行 `bash scripts/trade_arena_ssh.sh "cd /etc/nginx/website/trade-arena && bash scripts/opsctl.sh status"`
5. 再看 `/var/log/trade-arena-deploy.log` 与 `webhook/DEPLOY_LOG.md`
6. 需要回归时执行 `bash scripts/trade_arena_ssh.sh "cd /etc/nginx/website/trade-arena && bash scripts/opsctl.sh smoke --profile prod"`

常用切换目录方式：

```bash
cd /etc/nginx/website/trade-arena
```

## 8. 安全约束

- 不要把 `.env.ssh.trade-arena.local` 提交到版本库
- 不要把密码直接写进 `AGENTS.md`、`README.md` 或 `docs/`
- 密钥引导完成后，长期运维优先使用 `~/.ssh/trade_arena_ops`
- 不要再把密码重新写回 `~/.ssh/config` 的注释元数据
