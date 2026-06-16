# AI 浏览器自动化助手 — 开发复盘

## 项目概述

一个 AI 驱动的浏览器自动化助手。用户用自然语言描述任务（如"帮我对比京东和淘宝的机械键盘价格"），系统自动操控浏览器完成搜索、点击、翻页、数据提取，最后返回结构化结果。

核心技术栈：**FastAPI + LangGraph + Playwright + DeepSeek/Qwen-VL + React**

---

## 一、浏览器操作的底层机制

### 问题：怎么让代码像人一样操作浏览器？

最初方案是 **DOM 注入编号**——注入 JS 给每个可交互元素贴一个编号，截图给 VL 模型，VL 选编号，用 `window.__dom_elements[15].click()` 点击。

**翻车**：现代网站（B站、京东）大量使用 React/Vue，按钮是 `<span>` `<div>` 没有 `href`、没有 `onclick` 属性，DOM 注入扫不到。

### 解决：角色推断 + 文字匹配

不再依赖 HTML 属性，改为 7 种信号综合推断：

1. ARIA `role` 属性
2. HTML 标签（`<a href>`, `<button>`, `<input>`）
3. `cursor:pointer` CSS 属性
4. `tabindex` 属性
5. `onclick` 属性
6. header/nav 容器位置（导航栏里的短文本大概率是链接）
7. `data-url/href/link` 属性

点击用 `page.getByRole()` 或 CSS `:has-text()`，不依赖编号。

### 问题：React 事件代理拦截点击

即使在元素上调用 `.click()`，React 也不响应。因为 React 在 document 层监听事件，DOM 级别的 `.click()` 不触发 React 的合成事件。

**解决**：用 `page.mouse.click(x, y)` 发送完整鼠标事件序列（mousedown → mouseup → click），React 能正确拦截。

### 问题：点击后页面"看起来变了"但代码认为没变

B站等网站所有页面共享同一个导航栏。`innerText` 的前 2000 字符全是导航栏，新旧页面的文字几乎一样。

**解决**：用 URL 变化来判断页面是否跳转，不依赖文字对比。

---

## 二、数据提取的演进

### 第一代：CSS 选择器 + 正则

写死 `article.product_pod` 找商品卡片，`h3` 找标题，`p.price_color` 找价格。在 books.toscrape.com 上完美，换一个网站就失效。

**翻车**：正则和选择器缺乏通用性。京东的商品在 `div.gl-item` 里，淘宝在 `div.item` 里——每换一个网站都要重新写规则。

### 第二代：全量 innerText + LLM 解析

放弃在 JS 层面做结构化——直接把 `document.body.innerText` 全文发给 LLM（DeepSeek），让它自己找书名、价格、作者。

**优点**：通用性强，换网站不需要改代码。**缺点**：无法做"名价配对"，LLM 可能张冠李戴。

### 第三代：产品卡片配对提取

JS 遍历商品容器（`<article>`, `[class*=product]`），在每个容器内配对提取标题+价格，输出 `书名 | £47.82` 格式。再发给 LLM，LLM 直接引用现有配对。

### 最终方案：角色分工

- **VL 模型**：负责导航（点哪里、翻页、滚动）
- **文本 LLM**（DeepSeek）：负责从页面文本中提取结构化数据
- 两者各司其职，不互相干扰

---

## 三、反爬虫对抗

### 问题：京东搜索触发"访问频繁"，B站 type 动作触发 error 103

Playwright 默认暴露了大量自动化特征：`navigator.webdriver=true`、缺失 Chrome 插件、Canvas 指纹异常。

### 解决：多层反检测

| 层级 | 措施 |
|------|------|
| 浏览器启动参数 | `--disable-blink-features=AutomationControlled`，隐藏自动化标记 |
| JS 指纹伪装 | 覆盖 `navigator.webdriver`、伪造 `plugins` 数组、随机化 Canvas 指纹 |
| WebGL 混淆 | 覆盖 `getParameter` 返回真实 GPU 信息 |
| 人类行为模拟 | 贝塞尔曲线鼠标移动（非直线瞬移）、逐字打字（30-120ms 间隔）、随机停顿（5% 思考概率） |
| 操作节奏 | 每步间隔 1.5-3.5 秒随机，模拟人类浏览速度 |

**效果**：淘宝从封禁变为正常访问。

### 局限性

京东、拼多多风控极严——检测维度远超浏览器指纹（IP 信誉、行为模式、设备指纹）。真正的解决方案是 Claude Computer Use（像素级操作），但需要 Anthropic 原生 API。

---

## 四、VL Agent 的 JSON 解析

### 问题：千问 VL 返回的 JSON 不稳定

VL 模型经常返回：
- ` ```json\n{...}\n``` `（带 markdown 标记）
- `{...} 额外文字`（后面跟废话）
- `{..."thinking":"价格有 {高,中,低}"...}`（JSON 值里有大括号）
- 残缺 JSON

### 解决：四层 fallback 解析器

1. 去 markdown 标记 → 直接 `json.loads()`
2. 字符串感知大括号匹配（忽略引号内的括号）
3. 正则修复（去尾随逗号、单引号替换）
4. 逐字段正则提取（`thinking`、`action`、`done`）

解析失败自动重试一次，第二次附带格式纠正提示。

---

## 五、VL Agent 的死循环问题

### 问题：VL 在同一页面反复执行相同操作

- 点一个被封禁的 B站账号 → 看到"账号已封禁" → 继续点 → 死循环
- 搜索框输入后页面没跳转 → 继续输入 → 死循环

### 解决：卡住检测 + 自动终止

- `detect_stuck()`：连续 3 次相同操作 → 注入警告提示词
- 连续 5 次同一页面无进展 → 强制终止
- 最大步数上限 20 → 超出自动返回已有数据

---

## 六、京东搜索的特殊问题

### 问题：搜索触发登录跳转

京东搜索框的类型动作触发登录页面跳转——即使已有登录 cookie。搜索 URL（`search.jd.com/Search?keyword=...`）也返回"访问频繁"。

### 解决：DeepSeek 预飞直接生成搜索 URL

在 VL Agent 启动前，先用 DeepSeek 分析任务，生成最优起始 URL。对于 B站搜索"Agent开发"，直接生成 `search.bilibili.com/all?keyword=Agent开发`，绕过首页搜索的 React 事件拦截。

### 局限性

京东的风控在 URL 层面也拦截，这是我们的能力上限。

---

## 七、聊天界面的设计反思

### 第一版：独立运行标签

独立的"运行"标签页——输入任务 → 看进度 → 看结果。和聊天完全分离。

**问题**：用户要先判断"这是聊天还是浏览器任务"，然后切到不同标签。

### 最终版：统一聊天界面

```
所有消息都在聊天里：
  "你好"             → LLM 回复
  "帮我查豆瓣三体"    → 自动识别为浏览器任务 → 后台执行 → 结果放入聊天
```

- 自动意图检测：超过 1 个浏览器关键词 → 启动 VL Agent
- 纯聊天 → DeepSeek 直接回复
- 浏览器任务进行中显示"操作浏览器"，可展开看实时截图+步骤

---

## 八、定时任务系统

### 设计

调度器每 10 分钟轮询一次 → 检查哪些任务到时间 → 调用 VL Agent 执行 → 结果存入历史。

数据存储：`memory.json`（调度任务+历史），`chat_data/`（对话记录），`browser_profile/`（浏览器登录态）。

### 踩坑

- **失败更新 last_run**：第一次运行失败也更新了时间戳 → 要等一小时才重试。修复：失败不更新时间。
- **线程中子进程路径错误**：调度器后台线程启动 Playwright 子进程时，cwd 不对。修复：`subprocess.Popen` 加 `cwd` 参数。
- **时区显示**：UTC 时间显示为"08:35"而不是"16:35"。修复：前端 `new Date(ts).toLocaleString()`。

---

## 九、开发中的"小"问题

虽然是细节，但每一个都会让系统瘫痪。

### 前端

| 问题 | 根因 | 修复 |
|------|------|------|
| 对话框不能删除 | 前端没调 DELETE API | 加 `fetch(..., {method:'DELETE'})` + 确认弹窗 |
| 点击任务卡只创建空对话 | `onSelect` 只建 session 不发消息 | 改为建 session → sendFirstMessage |
| 聊天详情面板空白 | SSE 事件无人接收 | `_run_browser_for_chat` 注册 progress handler |
| 任务完成转圈不停 | SSE "done" 没清 `loading` 状态 | done/error 事件清理 `loading` + `browserTaskId` |
| 浏览器结果不显示 | SSE done 后没刷新消息列表 | done 后重新 fetch messages |
| "暂未运行"但其实运行了 | `history` 新字段，旧数据没有 | `mark_schedule_run` 补 `history` append |
| `--reload` 没加载新代码 | 8080 被旧进程占着 | `taskkill //F //IM python.exe` 强制清理 |
| Welcome 位置对不齐 | `flex:1` 撑满空间 | 去掉 flex:1，用 `margin` 负值微调 |
| 卡片比例反复调 | aspect-ratio 太大太小 | 最终 3:2 |
| 渐变条不显示 | opacity 设成了 0.6 太淡 | hover 时才显示，默认隐藏 |
| 对话时间显示 UTC | 存的 UTC 时间直接显示 | `new Date().toLocaleString()` 转本地时区 |
| 结果太长被截断 | 历史存 200 字，前端显 100 字 | 存 2000，前端完整显示+换行 |
| 页面整体可滚动 | `min-height:100vh` | 改 `height:100vh; overflow:hidden`，各区域独立滚动 |
| 布局两边太空 | `max-width:1200px` | 改 `1600px` |

### 后端

| 问题 | 根因 | 修复 |
|------|------|------|
| `verified_data` 未定义 | 跳过 `_verify_and_extract` 后删了变量但引用还在 | `state["extracted_data"]` 替换 |
| `_needs_browser` 返回 coroutine | 写成了 `async def` 但没 await，永远是 truthy | 改 `def` + 阈值从 2 降到 1 |
| 调用处还在 `await` 同步函数 | 函数改同步了但调用处没改 | 去掉 `await` |
| 豆瓣 `[图书]三体` 点不中 | `[]` 是 CSS 选择器特殊字符 | 提取纯文字部分单独匹配 |
| B站搜索框识别不到 | `<input>` 没有 `textContent` | 改用 `placeholder/value/aria-label` |
| 无属性 input 完全跳过 | 5 个文字来源全为空 | 位置推断：页面顶部空 input=搜索框 |
| B站 type 触发 error 103 | React 拦截键盘事件 | DeepSeek 预飞直接生成搜索 URL |
| 导航到 about:blank | `wait_until="domcontentloaded"` 太早 | 改 `networkidle` + blank 自动重试 |
| GitHub 定时任务超时 | `--no-proxy-server` 禁用代理 | 去掉该参数走系统代理 |
| 163 行缩进错误 | `await` 语句放错位置 | 缩进进 elif 块 |
| dashscope/openai 包缺失 | requirements.txt 没写 | 补上 |
| Docker Hub 被墙 | Docker 默认连 docker.io | 配 DaoCloud 镜像加速 |

### 设计迭代

| 版本 | 主题 | 问题 |
|------|------|------|
| v1 | Swiss Minimalism 暗色 | "太简陋了" |
| v2 | Dark Vibrant + 锯齿渐变 | "没有色彩" |
| v3 | Playful Dark + 动画 + blob 背景 | 用户满意 |
| v4 | 亮色模式适配 | `data-theme="light"` + localStorage 记忆 |

### 进程管理

开发过程中最头疼的问题：每次重启后端，8080 端口被占用。原因是用 `--reload` 启动的 uvicorn 在后台持续运行，新的启动命令无法绑定端口。

解决方法：`netstat -ano | grep :8080` → 找 PID → `taskkill //F //PID xxx`。后来发现一次杀掉所有 Python/Chrome 进程最干净：`taskkill //F //IM python.exe //IM chrome.exe`。

Docker 环境下就没这问题了——容器网络隔离，端口不会冲突。

---

## 十、最终功能清单

| 大类 | 功能 |
|------|------|
| 浏览器自动化 | 导航、点击、输入、滚动、截图、翻页 |
| 数据提取 | 全量文本+结构化配对+LLM解析 |
| 跨网页对比 | 多网站访问+观点差异汇总 |
| 聊天交互 | 消息气泡、历史对话、意图自动识别 |
| 实时进度 | SSE推送、截图、Agent思考、步骤列表 |
| 定时任务 | 每小时/每天/每周，历史记录+复制下载 |
| 主题切换 | 暗色/亮色+渐变气泡背景 |
| 反爬对抗 | 鼠标贝塞尔轨迹、慢输入、Canvas/WebGL混淆 |
| Docker部署 | 前后端容器化、nginx代理、健康检查 |
| 多网站适配 | 13个网站验证通过 |

## 十一、核心教训

1. **DOM 注入不够通用**——现代SPA的交互元素没有HTML属性标记，要用角色推断+文字匹配
2. **LLM 比正则更擅长解析**——放弃手写提取规则，把数据扔给LLM更可靠
3. **URL 比文字更准确**——判断页面跳转不要依赖 innerText，导航栏的文字在所有页面都一样
4. **反爬不只是改 webdriver**——鼠标轨迹、打字速度、浏览节奏都会被检测
5. **解析失败要重试**——VL模型第一次返回格式不对，第二次给纠正提示大概率成功
6. **文件也算数据库**——只要存了数据就是"数据库"，不一定要 MySQL/Redis
