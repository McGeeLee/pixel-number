# Pixel Number 网页版

线上地址：**https://pixels.mcgeelee.com**

静态前端使用 Canvas、Web Worker 和任意精度 BigInt。Cloudflare Worker 只提供 HTML、CSS、JavaScript 和图标；不接收、记录或保存用户图片与编号。所有图片转换及文件生成都在浏览器本地执行。在线站点面向公众开放。

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

开发与自动部署固定使用 Node.js 24.19.0、pnpm 11.25.0（见 `.node-version` 和 `package.json`）。纯前端及测试不依赖 npm 包；Cloudflare 开发工具在 devDependencies 中。

```sh
pnpm install
pnpm dev
# 浏览 http://127.0.0.1:8788

pnpm test
pnpm build
pnpm exec wrangler types
pnpm exec wrangler deploy --dry-run
```

没有构建框架。`scripts/build.mjs` 将 `public/` 中六个公开文件嵌入只读 Worker 模块，生成 `dist/worker.mjs`。发布包约 49 KB。响应包含 MIME、ETag、重新验证缓存和内容安全策略。

## 部署

- Cloudflare Worker：`pixel-number`
- 自定义域名：`pixels.mcgeelee.com`
- 兼容日期：`2026-10-23`
- `workers.dev` 和预览子域名均关闭。
- 网站原有首页及其他应用未被替换。

### GitHub 自动部署

Cloudflare Workers Builds 已连接 [McGeeLee/pixel-number](https://github.com/McGeeLee/pixel-number)。推送到 `main`（包括合并 PR）会触发构建，测试通过后自动更新线上网站。

| 设置 | 值 |
| --- | --- |
| 生产分支 | `main` |
| 构建目录 | `web` |
| 构建命令 | `pnpm install --frozen-lockfile && pnpm test` |
| 部署命令 | `pnpm exec wrangler deploy` |
| 监听路径 | 全部路径 |
| Node.js / pnpm | `24.19.0` / `11.25.0` |

Cloudflare 构建变量设置 `NODE_VERSION=24.19.0`、`PNPM_VERSION=11.25.0`、`SKIP_DEPENDENCY_INSTALL=1`，由上面的构建命令按锁文件安装依赖。构建失败时不会执行部署，线上继续提供上一版。其他分支不触发生产部署。

在 Cloudflare 的 **Workers & Pages → pixel-number → Deployments / Settings → Builds** 中查看构建结果、日志及连接配置。部署使用 Cloudflare 内保存的构建凭证，仓库中不存放令牌。

### 手动部署

首次发布通过已连接的 Cloudflare 插件完成。需要手动部署时，可以使用本人已经认证的 Wrangler：

```sh
pnpm build
pnpm exec wrangler deploy
```

`wrangler.jsonc` 是目标账户与自定义域名的配置来源。首次部署记录见 `deployment.json`。不需要数据库、图片上传接口或存储桶。

## 验证证据

- 9 项 Node 测试：全部 65,536 色、1080p 双向映射、进位与边界、大数解析、PNG 元数据、ZIP、Python 兼容 JSON，以及 Worker 响应和公开文件范围。
- Wrangler 类型生成和部署 dry-run 通过。
- 实际浏览器：编号 65535 → 65536，滑条 → 65537；1080p 色谱示例；PNG 和 JSON 下载；390 像素宽手机布局，无横向溢出。
- 下载的 1080p PNG 与 JSON 经 Python 桌面版核对：尺寸、顺序和 33,177,589 位二进制编号完全一致。
- 正式域名已通过 HTTPS 打开并运行本地图片引擎，重新导入生成的 PNG 后得到相同编号摘要，浏览器无错误日志。

项目只有公开应用源码会发布；`.venv`、Python 程序、测试结果与本地文件不会被打包。
