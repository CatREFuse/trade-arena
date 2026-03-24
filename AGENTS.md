不要把功能说明写到 UI 文案里！我求你了！

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
