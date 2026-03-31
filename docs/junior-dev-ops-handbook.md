# Trade Arena 初级开发者运维手册

最后更新：2026-03-31（Asia/Shanghai）

这份手册是给刚接手项目、对运维不熟的人看的。

目标很简单：

1. 把项目跑起来
2. 改完代码后知道该点哪几步
3. 出问题时先查最常见的地方

如果你只想记最少的命令，先记下面这 7 条。

## 1. 先记这 7 条命令

启动开发环境：

```bash
bash scripts/dev_up.sh
```

重启开发环境：

```bash
bash scripts/dev_restart.sh
```

停止开发环境：

```bash
bash scripts/dev_down.sh
```

停止开发环境并关闭 Docker：

```bash
STOP_DOCKER=1 bash scripts/dev_down.sh
```

查看服务状态：

```bash
bash scripts/service_ctl.sh status
```

做一次本地检查：

```bash
bash scripts/dev_check.sh
```

做一次更完整的检查：

```bash
RUN_PYTEST=1 RUN_REGRESSION=1 bash scripts/dev_check.sh
```

## 2. 我今天只想把项目跑起来

推荐顺序：

```bash
bash scripts/dev_up.sh
bash scripts/dev_check.sh
```

正常情况下你会得到这些结果：

- 前端地址：`http://localhost:3000`
- 后端地址：`http://localhost:8000`
- `dev_check.sh` 不报失败

如果 `bash scripts/dev_up.sh` 提示 `docker command not found`，说明你电脑没有可用的 Docker 命令。

这时可以先试：

```bash
START_DOCKER=0 bash scripts/dev_up.sh
```

前提是你的 PostgreSQL 和 Redis 已经在别处启动好了。

## 3. 我改完代码后该做什么

最推荐的顺序是：

```bash
bash scripts/dev_check.sh
cd backend && pytest -q
RUN_REGISTER=0 BASE_URL=http://127.0.0.1:3000 bash scripts/online_regression.sh
```

如果你不想记这么多，可以直接用：

```bash
RUN_PYTEST=1 RUN_REGRESSION=1 bash scripts/dev_check.sh
```

这条命令会做三件事：

1. 看服务状态
2. 跑本地自检
3. 可选地跑后端测试和页面/API 回归

## 4. 我要重启服务该用什么

平时不要手动分别敲 `uvicorn`、`npm run dev`、`npm run start`。

优先用这几条：

```bash
bash scripts/dev_restart.sh
bash scripts/dev_down.sh
bash scripts/dev_up.sh
```

如果你只是想看当前状态：

```bash
bash scripts/service_ctl.sh status
```

## 5. 我要构建该用什么

如果你只是想确认“现在这份代码能不能正常构建”，优先用：

```bash
bash scripts/prod_build_check.sh
```

这条命令会做两件事：

1. 先跑一次基础环境检查
2. 再执行前端生产构建

如果你要以生产模式启动整套服务，用：

```bash
MODE=prod START_DOCKER=1 BUILD_FRONTEND=1 bash scripts/service_ctl.sh start
```

这个命令更偏运维，不建议你每天都用。

## 6. Docker 什么时候要用

这个项目常见的 Docker 用途只有一个：拉起依赖服务。

通常是：

- PostgreSQL
- Redis

最简单的命令：

```bash
bash scripts/docker_up.sh
bash scripts/docker_down.sh
```

如果你只想靠 `service_ctl.sh` 自动处理，也可以：

```bash
START_DOCKER=1 bash scripts/dev_up.sh
STOP_DOCKER=1 bash scripts/dev_down.sh
```

## 7. 已经打包好的一键命令

最适合你日常使用的：

- `bash scripts/dev_up.sh`
- `bash scripts/dev_restart.sh`
- `bash scripts/dev_down.sh`
- `bash scripts/dev_check.sh`
- `bash scripts/prod_build_check.sh`
- `bash scripts/docker_up.sh`
- `bash scripts/docker_down.sh`

稍微进阶一点的：

- `bash scripts/service_ctl.sh status`
- `bash scripts/opsctl.sh doctor`
- `bash scripts/opsctl.sh status`
- `bash scripts/opsctl.sh logs --scope deploy --tail 200`

先不要直接碰的：

- `bash scripts/ops_http.sh ...`
- `bash webhook/deploy.sh ...`
- `bash scripts/ops/deploy.sh ...`
- 手动改 `.runtime/`、锁文件、队列文件

## 8. 还能继续打包什么

现在已经够你日常用了，但后面还可以继续加：

- `scripts/dev_logs.sh`
  作用：一次看前后端日志
- `scripts/dev_reset.sh`
  作用：停止服务、清理缓存、重新启动
- `scripts/dev_bootstrap.sh`
  作用：首次安装依赖并启动
- `scripts/prod_smoke.sh`
  作用：固定跑生产回归，不用再记参数

## 9. 页面打不开时先查什么

第一步先看状态：

```bash
bash scripts/service_ctl.sh status
```

第二步跑自检：

```bash
bash scripts/dev_check.sh
```

第三步再看这两个地址：

```bash
curl --noproxy '*' -sS http://localhost:8000/api/health
curl --noproxy '*' -I http://localhost:3000
```

如果命令行看到 `502`，不要马上判断服务挂了。先确认你是不是被本机代理影响了，所以命令里尽量保留 `--noproxy '*'`。

## 10. 需要更详细时再看哪里

如果这份手册不够，再继续看：

- `docs/ops-runbook-local-development-and-test-server.md`
- `docs/ops-automation-manual.md`
- `docs/ops-reference-manual.md`
