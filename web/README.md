# Pixel Number 网页版

线上地址：**https://pixels.mcgeelee.com**

静态前端使用 Canvas、Web Worker 和任意精度 BigInt。Cloudflare Pages 直接托管 HTML、CSS、JavaScript 和图标，没有 Worker 服务端代码或 Pages Functions；不接收、记录或保存用户图片与编号。所有图片转换及文件生成都在浏览器本地执行。在线站点面向公众开放。

## 功能

- 默认 1920 × 1080、RGB565；支持自定义尺寸、两种像素顺序。
- 十进制 / 十六进制输入；滑条只传递整数偏移，编号计算保持任意精度。
- 可调步长、前后翻页、全黑、全白、色谱示例和随机跳转。
- 适应窗口 / 100% / 200% / 400% 预览，像素放大镜。
- PNG、完整数字 TXT 和可恢复编号 JSON 下载；JSON 与 Python 桌面版兼容。
- 导入 PNG / JPEG / WebP / BMP。普通图片量化为 RGB565，透明像素合成到黑色；本工具导出的 PNG 会保留像素顺序，能够恢复相同编号。
- 按范围导出 ZIP，包含图片和 `plan.json`。每批最多 100 张，原始 RGBA 像素总量最多 256 MiB；取消会丢弃本次尚未完成的 ZIP，保留最近成功的预览。
- 超过 4096 字符的编号请用 TXT / JSON 文件载入。超大数只在输入框展示十六进制摘要，导出文件仍包含完整数字。

需要支持 BigInt、Web Worker、OffscreenCanvas 和 createImageBitmap 的现代浏览器。十进制超大数转换可能需要时间，可取消并恢复上一次画面。没有云端存档，关闭页面后请使用已下载的 PNG / JSON 继续。

## 本地开发

开发环境使用 Node.js 24.19.0、pnpm 11.25.0（见 `.node-version` 和 `package.json`）。纯前端、构建及测试不依赖 npm 包；Cloudflare 开发工具在 devDependencies 中。

```sh
pnpm install
pnpm dev
# 浏览 http://127.0.0.1:8788
pnpm test
pnpm build
# 本地按 Pages 的响应头和路由规则验证
pnpm exec wrangler pages dev dist-pages
```

默认构建将 `public/` 中六个公开文件原样复制到 `dist-pages/`，并加入 `pages/_headers` 和 `pages/404.html`，合计八个文件。产物没有 `_worker.js`、Functions、服务端依赖或数据库绑定。图片转换、浏览器 Web Worker 和下载逻辑均未改变。

`_headers` 保留 `connect-src 'none'`、仅同源脚本和 Web Worker、禁止摄像头/麦克风/定位、无 Referrer，以及每次重新验证的浏览器缓存策略。Pages 自动提供 MIME、ETag、HEAD 和条件缓存响应；显式 `404.html` 保证未知路径返回 404，避免回退到首页。参考 [Pages 响应头](https://developers.cloudflare.com/pages/configuration/headers/) 和 [静态文件及 404 行为](https://developers.cloudflare.com/pages/configuration/serving-pages/)。

## Pages 部署

- 目标 Pages 项目：`pixel-number`
- 正式自定义域名：`pixels.mcgeelee.com`
- 构建目录：`web`
- 静态输出目录：`dist-pages`（相对 `web`）
- 本仓库配置不等于远端已部署；域名迁移及远端验证完成后才能确认切换成功。

```sh
cd web
pnpm test
pnpm exec wrangler pages deploy dist-pages --project-name pixel-number --branch main
# 或 pnpm deploy（会先重新构建）
```

`wrangler.jsonc` 只声明 Pages 项目、输出目录及兼容日期。如需明确账户，在运行命令的环境中设置 `CLOUDFLARE_ACCOUNT_ID=9c7a68cd84c8ea891bf7a28ac1f167bf`。域名在 Pages 项目中关联，不使用 Worker 的 `routes` 配置。无需数据库、图片上传接口、R2 或其他后端。

### 自动部署配置

旧站使用 Cloudflare Workers Builds 连接 [McGeeLee/pixel-number](https://github.com/McGeeLee/pixel-number) 的 `main` 分支。迁移时需要关闭旧 Worker 的构建触发器，防止后续提交恢复旧部署。仓库没有 GitHub Actions 工作流。

如为 Pages 配置 Git 集成，使用生产分支 `main`、根目录 `web`、构建命令 `pnpm install --frozen-lockfile && pnpm test`、输出目录 `dist-pages`。若使用 Direct Upload，应在 CI 中运行上面的明确项目及分支的 `wrangler pages deploy` 命令。自动部署是否启用以远端项目配置为准。

Node.js / pnpm 版本保持 `24.19.0` / `11.25.0`。自动构建可设置 `NODE_VERSION=24.19.0`、`PNPM_VERSION=11.25.0`、`SKIP_DEPENDENCY_INSTALL=1`；认证凭证仅留在平台或 CI 的受保护变量中。

### 旧 Worker 回滚材料

原始 Worker 构建保留为 `scripts/build-worker.mjs`，配置保留为 `wrangler.worker.jsonc`，不会进入 Pages 产物。`pnpm build:worker` 仍可生成 `dist/worker.mjs`。旧部署记录 `deployment.json` 仅为历史记录。

如需回滚，先协调 Pages 域名绑定，再显式使用 `pnpm exec wrangler deploy --config wrangler.worker.jsonc`；这不是默认部署流程。迁移期间保留回滚材料，不删除六个应用资源。

## Pages 迁移验证

- 2026-10-24：六个本地公开文件的 SHA-256 前 24 位与当时线上 Worker 源码中的六个 ETag 全部一致，确保保留当前 UI。
- `pnpm test` 包括纯静态产物文件范围、逐字节内容一致性、安全策略、404 文件，以及既有编解码和回滚 Worker 测试。
- 本地产物与测试只能证明构建结果；正式域名的响应头、404、浏览器运算及下载需要在 Pages 部署后验证。

## 既有功能验证证据（迁移前）

- 9 项 Node 测试：全部 65,536 色、1080p 双向映射、进位与边界、大数解析、PNG 元数据、ZIP、Python 兼容 JSON，以及 Worker 响应和公开文件范围。
- Wrangler 类型生成和部署 dry-run 通过。
- 实际浏览器：编号 65535 → 65536，滑条 → 65537；1080p 色谱示例；PNG 和 JSON 下载；390 像素宽手机布局，无横向溢出。
- 下载的 1080p PNG 与 JSON 经 Python 桌面版核对：尺寸、顺序和 33,177,589 位二进制编号完全一致。
- 正式域名已通过 HTTPS 打开并运行本地图片引擎，重新导入生成的 PNG 后得到相同编号摘要，浏览器无错误日志。

项目只有公开应用源码会发布；`.venv`、Python 程序、测试结果与本地文件不会被打包。
