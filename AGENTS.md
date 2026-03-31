不要把功能说明写到 UI 文案里！我求你了！

## Docs First（强制）

所有 Agent 在执行任何改动、测试、部署前，先阅读 `docs/README.md`，并按其中“强制阅读顺序”完成文档对齐。

最低要求：

1. 先读 `docs/developer-handbook.md`，再开始改代码。
2. 涉及部署、Webhook、迁移、日志时，必须读 `docs/ops-reference-manual.md`。
3. 执行测试前，必须先读 `docs/testing-process-manual.md`，按标准流程执行。
4. 执行测试项时，必须结合 `docs/testing-checklist.md` 落具体检查。
5. 若代码改动导致流程变化，提交中同步更新 `docs/` 对应文档。

## 服务启停规范（强制）

统一使用 `scripts/service_ctl.sh` 管理服务，不要手动分散执行 `uvicorn`、`npm run dev`、`npm run start` 做长期启停。

标准命令：

1. 启动开发环境：`MODE=dev START_DOCKER=1 BUILD_FRONTEND=0 bash scripts/service_ctl.sh start`
2. 启动生产模式：`MODE=prod START_DOCKER=1 BUILD_FRONTEND=1 bash scripts/service_ctl.sh start`
3. 查看状态：`bash scripts/service_ctl.sh status`
4. 重启：`bash scripts/service_ctl.sh restart`
5. 停止：`bash scripts/service_ctl.sh stop`
6. 停止并关闭 docker 依赖：`STOP_DOCKER=1 bash scripts/service_ctl.sh stop`

## 运维入口规范（强制）

涉及部署、迁移、回归、运行状态、日志读取时，优先使用 `scripts/opsctl.sh`，避免直接调用分散脚本。

标准命令：

1. 部署：`bash scripts/opsctl.sh deploy --branch main`
2. 迁移：`bash scripts/opsctl.sh migrate`
3. 状态：`bash scripts/opsctl.sh status`
4. 日志：`bash scripts/opsctl.sh logs --scope deploy --tail 200`
5. 回归：`bash scripts/opsctl.sh smoke --profile local`
6. 自检：`bash scripts/opsctl.sh doctor`
7. 生成密钥文件：`bash scripts/opsctl.sh init-secrets --output .env.ops.local`
8. 远程 HTTP 运维：`OPS_API_BASE=http://127.0.0.1:9000 OPS_API_KEY=<key> bash scripts/ops_http.sh <command>`

约束：

- 保留 `POST /webhook` 兼容入口，同时支持 `POST /hooks/github/push`
- `GET /webhook/logs` 必须带 `Authorization: Bearer <OPS_API_KEY>`
- 远程运维动作统一走 `/ops/jobs/*` 与 `/ops/status`、`/ops/logs`
- `/ops/jobs/service` 的 `target` 允许 `all|backend|frontend`
- 不开放远程 rollback 与 gateway 自重启动作
- 生产和 staging 必须显式设置 `WEBHOOK_SECRET` 与 `OPS_API_KEY`

## Nuxt Build / Repair SOP

当 Nuxt 报出下面这类错误时：

```text
Package import specifier "#internal/nuxt/paths" is not defined in package .../frontend/package.json imported from .../.nuxt/dist/server/server.mjs
```

先判定错误特征：

1. 报错栈里如果出现 `.nuxt/dist/server/server.mjs`
2. 同时出现 `#internal/nuxt/paths`

这通常不是业务代码错误，而是“生产环境跑错了产物”：

- `.nuxt/` 是 Nuxt 的内部构建目录
- 正式生产入口应该是 `.output/server/index.mjs`

检测顺序：

1. 在 `frontend/` 执行 `npm run build`
2. 执行 `node .output/server/index.mjs` 或 `npm run start`
3. 不要把 `nuxt preview` 当成生产常驻进程
4. 搜索仓库和部署脚本里是否有人在运行：
   - `node .nuxt/dist/server/server.mjs`
   - `nuxt preview`
   - 任何 `.nuxt/dist/*` 入口

修复步骤：

1. 清理旧产物：`rm -rf .nuxt .output`
2. 重装依赖：`npm ci`
3. 重建：`npm run build`
4. 生产启动：`HOST=127.0.0.1 PORT=3000 npm run start`
5. 验证：
   - 进程正常监听端口
   - `curl --noproxy '*' -I http://127.0.0.1:3000`
   - 页面可访问

仓库约定：

- `frontend/package.json` 里的正式生产启动脚本是 `npm run start`
- 生产部署和 systemd 只允许跑 `.output/server/index.mjs`
- `nuxt preview` 只用于本地短时预览，不作为线上常驻方案

## Nuxt Dev Mode SOP

如果是本地 `npm run dev` 报错，并且先出现：

```text
Failed to resolve import "#app-manifest" from "node_modules/nuxt/dist/app/composables/manifest.js"
```

随后页面再掉成：

```text
Package import specifier "#internal/nuxt/paths" is not defined in package .../frontend/package.json imported from .../.nuxt/dist/server/server.mjs
```

优先按下面顺序处理：

1. 先确认这是 dev 态，不是生产态：端口一般由 `nuxt dev` 监听。
2. 关闭所有残留的 `npm run dev` / `nuxt dev` 进程，只保留一条。
3. 清掉旧的 `.nuxt` 目录后重启 `npm run dev`。
4. 如果日志里持续出现 `#app-manifest` 预处理错误，在 `frontend/nuxt.config.ts` 中显式设置：
   - `experimental: { appManifest: false }`
5. 再用浏览器和 `curl --noproxy '*' -I http://localhost:3000/` 验证是否恢复 `200 OK`。

补充说明：

- `npm run build` 会重建 `.nuxt/dist`，如果它和 `npm run dev` 同时跑，dev 服务会自动重启。
- 单纯看到 `.nuxt/dist directory has been removed. Restarting Nuxt...` 不一定是故障；关键是后续是否恢复到可访问状态。
