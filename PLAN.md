# DecoPilot 基础交互功能增强计划

## 一、现状分析

### 当前代码结构
- **单文件应用**：所有逻辑在 `frontend/src/App.jsx`（~998 行）
- **技术栈**：React 18 + Tailwind CSS 3 + Vite + lucide-react 图标库
- **消息模型**：`{ role, content, id, thinking, expertInfo, structuredBlocks, isComplete, image }`
- **流式响应**：通过 `processStream` 读取 SSE，用 `AbortController` 可中断（当前未实现）
- **历史存储**：纯 localStorage，无后端持久化

### 当前缺失的功能
1. ❌ 用户消息：无编辑、无复制
2. ❌ AI 回答：无复制、无重新生成、无评价
3. ❌ 终止回答：无停止生成按钮
4. ❌ 设置面板：sidebar 底部有设置按钮但无功能

---

## 二、功能设计（参考 Claude / ChatGPT / DeepSeek 交互模式）

### 功能 1：终止回答（Stop Generation）

**交互设计：**
- 位置：输入框右侧发送按钮位置，生成时替换为停止按钮（与 Claude/DeepSeek 一致）
- 样式：`Square`（方形停止图标），主题色背景，圆形按钮
- 出现时机：`isLoading === true` 时显示
- 点击效果：立即中断流式请求，保留已生成的内容，标记消息为 `isComplete`

**技术方案：**
- 新增 `abortControllerRef = useRef(null)`
- 在 `sendMessage` 中创建 `new AbortController()`，传入 `fetch` 的 `signal`
- 新增 `stopGeneration()` 函数：调用 `abortControllerRef.current.abort()`
- 发送按钮区域：`isLoading ? <StopButton> : <SendButton>`

**改动文件：** `App.jsx`
- 新增 state/ref：`abortControllerRef`
- 修改 `sendMessage`：创建 AbortController 并传入 fetch
- 修改 `processStream`：接收 signal 参数
- 新增 `stopGeneration` 函数
- 修改发送按钮 JSX：条件渲染停止/发送

---

### 功能 2：用户消息操作（编辑 + 复制）

**交互设计：**
- 触发方式：Hover 时在用户消息气泡左侧显示操作按钮组（与 Claude 一致）
- 按钮：`Pencil`（编辑）+ `Copy`（复制），小图标，灰色，hover 变深
- 编辑流程：
  1. 点击编辑 → 消息气泡变为可编辑的 textarea
  2. 显示"取消"和"重新发送"两个按钮
  3. 点击"重新发送" → 截断该消息之后的所有消息 → 用编辑后的内容重新发送
- 复制：点击后复制纯文本到剪贴板，图标短暂变为 `Check`（✓）表示成功

**技术方案：**
- 新增 state：`editingMsgIdx`（正在编辑的消息索引）、`editingContent`（编辑中的文本）
- 新增 `copyToClipboard(text)` 工具函数 + `copiedId` state（控制复制成功提示）
- 新增 `startEdit(idx, content)` / `cancelEdit()` / `submitEdit(idx)` 函数
- `submitEdit`：截断 messages 到 idx 位置，用新内容调用 `sendMessage`
- 用户消息 JSX：增加 hover 操作栏 + 编辑态条件渲染

**改动文件：** `App.jsx`

---

### 功能 3：AI 回答操作（复制 + 重新回答）

**交互设计：**
- 位置：每条 AI 回答底部，水平工具栏（与 Claude/ChatGPT 一致）
- 显示时机：消息 `isComplete === true` 时显示（流式生成中不显示）
- 按钮从左到右：`Copy`（复制）、`RefreshCw`（重新回答）
- 复制：复制 Markdown 原文，图标变 `Check`
- 重新回答：删除该条 AI 回答，用其上方的用户消息重新发送请求

**技术方案：**
- 复用 `copyToClipboard` 函数
- 新增 `regenerateAnswer(msgIdx)` 函数：
  1. 找到该 AI 消息上方最近的 user 消息
  2. 截断 messages 到该 user 消息（含）
  3. 用该 user 消息的 content 重新调用发送逻辑
- AI 消息 JSX：在 `isComplete` 时渲染底部工具栏

**改动文件：** `App.jsx`

---

### 功能 4：评价回答（👍 / 👎）

**交互设计：**
- 位置：AI 回答底部工具栏，在复制和重新回答按钮右侧
- 样式：`ThumbsUp` + `ThumbsDown` 图标，默认灰色
- 点击效果：
  - 点赞：图标填充主题色，短暂显示"感谢反馈"toast
  - 点踩：图标填充红色，弹出简单反馈选项（不准确 / 不实用 / 不够详细 / 其他）
- 状态持久化：存储在消息对象的 `feedback` 字段中，随 localStorage 持久化

**技术方案：**
- 消息模型扩展：`{ ...msg, feedback: 'good' | 'bad' | null, feedbackReason: string | null }`
- 新增 `rateFeedback(msgId, rating)` 函数：更新消息的 feedback 字段
- 新增 `FeedbackPopover` 组件：点踩时弹出的原因选择浮层
- 新增 `toast` state + 简单 Toast 组件（固定在底部中央，2秒自动消失）

**改动文件：** `App.jsx`、`index.css`（toast 动画）

---

### 功能 5：设置面板

**交互设计：**
- 入口：sidebar 底部已有的"设置"按钮
- 面板形式：右侧抽屉（从右侧滑入，宽度 360px，半透明遮罩）
- 设置项分组：

**对话设置：**
| 设置项 | 控件 | 默认值 | 说明 |
|--------|------|--------|------|
| 联网搜索 | Toggle | 开启 | 同当前 enableSearch |
| 深度思考 | Toggle | 开启 | 同当前 showThinking |
| 发送快捷键 | 选择器 | Enter | Enter 发送 / Ctrl+Enter 发送 |

**显示设置：**
| 设置项 | 控件 | 默认值 | 说明 |
|--------|------|--------|------|
| 字体大小 | 滑块/选择 | 中 | 小/中/大 三档 |

**数据管理：**
| 设置项 | 控件 | 说明 |
|--------|------|------|
| 清除所有对话 | 危险按钮 | 清空 localStorage 中的历史记录 |

**关于：**
- 版本号、技术支持链接

**技术方案：**
- 新增 `showSettings` state
- 新增 `settings` state（持久化到 localStorage）：
  ```js
  { sendKey: 'enter', fontSize: 'medium' }
  ```
- 将当前 `enableSearch`、`showThinking` 整合进 settings
- 新增 `SettingsDrawer` 组件（内联在 App.jsx 中或独立文件）
- 抽屉 JSX：fixed 定位 + 右侧滑入动画 + 遮罩层

**改动文件：** `App.jsx`、`index.css`（抽屉动画）、`tailwind.config.js`（如需新动画）

---

## 三、实施顺序与优先级

按依赖关系和用户价值排序：

| 步骤 | 功能 | 优先级 | 预计改动量 | 依赖 |
|------|------|--------|-----------|------|
| 1 | 终止回答 | P0 | 小 | 无 |
| 2 | 复制功能（用户+AI） | P0 | 小 | 无 |
| 3 | 重新回答 | P0 | 中 | 终止回答（需先停止当前生成） |
| 4 | 编辑用户消息 | P1 | 中 | 重新回答（编辑后需重新发送） |
| 5 | 评价回答 | P1 | 中 | 无 |
| 6 | 设置面板 | P2 | 大 | 无 |

---

## 四、新增 lucide-react 图标

```js
import {
  // 新增
  Square,        // 停止生成
  Pencil,        // 编辑消息
  Copy,          // 复制
  Check,         // 复制成功
  RefreshCw,     // 重新生成
  ThumbsUp,      // 点赞
  ThumbsDown,    // 点踩
  // 设置面板
  Moon, Sun,     // 主题（预留）
  Type,          // 字体大小
  Keyboard,      // 快捷键
  AlertTriangle, // 危险操作
} from 'lucide-react';
```

---

## 五、消息模型变更

```js
// 当前
{ role, content, id, thinking, expertInfo, structuredBlocks, isComplete, image }

// 新增字段
{
  ...existing,
  feedback: null,        // 'good' | 'bad' | null
  feedbackReason: null,  // string | null（点踩原因）
}
```

---

## 六、关键实现细节

### 6.1 终止回答 — AbortController
```js
const abortControllerRef = useRef(null);

// sendMessage 中
const controller = new AbortController();
abortControllerRef.current = controller;
const response = await fetch(endpoint, { ..., signal: controller.signal });

// stopGeneration
const stopGeneration = () => {
  if (abortControllerRef.current) {
    abortControllerRef.current.abort();
    abortControllerRef.current = null;
  }
  setIsLoading(false);
  // 标记当前正在生成的消息为 isComplete
  setMessages(prev => prev.map(msg =>
    msg.role === 'assistant' && !msg.isComplete ? { ...msg, isComplete: true } : msg
  ));
};
```

### 6.2 编辑消息 — 截断重发
```js
const submitEdit = (msgIdx) => {
  // 截断到编辑的消息位置（不含该消息）
  const truncated = messages.slice(0, msgIdx);
  setMessages(truncated);
  setEditingMsgIdx(null);
  // 用编辑后的内容发送
  sendMessage(editingContent);
};
```

### 6.3 重新回答 — 找到上一条用户消息
```js
const regenerateAnswer = (aiMsgIdx) => {
  // 找到该 AI 消息前面最近的 user 消息
  let userMsgIdx = aiMsgIdx - 1;
  while (userMsgIdx >= 0 && messages[userMsgIdx].role !== 'user') {
    userMsgIdx--;
  }
  if (userMsgIdx < 0) return;

  const userContent = messages[userMsgIdx].content;
  // 截断到 user 消息（含）
  const truncated = messages.slice(0, userMsgIdx + 1);
  setMessages(truncated);
  // 重新发送
  sendMessage(userContent);
};
```

### 6.4 复制到剪贴板
```js
const [copiedId, setCopiedId] = useState(null);

const copyToClipboard = async (text, id) => {
  try {
    await navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  } catch {
    // fallback
    const ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  }
};
```

---

## 七、UI 布局示意

### 用户消息（hover 态）
```
                    [✏️] [📋]
    ┌──────────────────────────┐
    │  用户的问题内容...        │  ← 右对齐药丸
    └──────────────────────────┘
```

### 用户消息（编辑态）
```
    ┌──────────────────────────┐
    │  [textarea 可编辑]        │
    │                          │
    │  [取消]  [重新发送 ▶]     │
    └──────────────────────────┘
```

### AI 回答（完成态）
```
    🤖  AI 的回答内容...
        blah blah blah...

        [📋 复制] [🔄 重新回答] [👍] [👎]   ← 底部工具栏
```

### 生成中 — 输入框区域
```
    ┌─────────────────────────────────┐
    │  [输入框 disabled]    [⏹ 停止]  │
    └─────────────────────────────────┘
```

### 设置抽屉
```
    ┌──────────────────┬──────────────┐
    │                  │  ⚙️ 设置      │
    │   主聊天区域      │              │
    │                  │  对话设置     │
    │                  │  · 联网搜索 ○ │
    │                  │  · 深度思考 ○ │
    │                  │  · 快捷键  ▼  │
    │                  │              │
    │                  │  显示设置     │
    │                  │  · 字体大小 ▼ │
    │                  │              │
    │                  │  数据管理     │
    │                  │  [清除所有]   │
    │                  │              │
    │                  │  关于         │
    │                  │  v1.0.0      │
    └──────────────────┴──────────────┘
```
