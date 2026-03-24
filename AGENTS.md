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
