# DecoPilot 产品体验深度改进计划 V2

## 一、现状评估

### 综合评分：7.2/10
| 维度 | 评分 | 与一线产品差距 |
|------|------|---------------|
| 功能完整性 | 7/10 | 缺少代码高亮、对话导出、历史搜索 |
| 交互体验 | 6/10 | 多个关键交互 Bug + 缺少滚动到底部等基础功能 |
| 视觉细节 | 8/10 | 设计系统完善，但缺少微交互 |
| 移动端适配 | 6/10 | 基础响应式完成，缺少遮罩层和手势 |
| 代码健壮性 | 6/10 | 多个边界情况未处理，状态管理有隐患 |

---

## 二、改进项分类（共 28 项）

### 🔴 P0 — 必须立即修复的 Bug（4 项）

#### P0-1：消息 key 使用 idx 导致状态错乱
- **问题**：`messages.map((msg, idx) => <div key={idx}>` 在消息增删时导致 React 复用错误组件
- **影响**：编辑/删除消息后，展开态、评价态可能错乱
- **修复**：改为 `key={msg.id || idx}`，同时确保所有消息都有唯一 id
- **位置**：App.jsx L910

#### P0-2：点踩反馈浮层无法关闭
- **问题**：点踩后弹出原因选择浮层，但点击外部无法关闭
- **影响**：用户被困在浮层中，只能选择一个原因或刷新页面
- **修复**：添加 click outside 关闭逻辑，或在全局遮罩 onClick 中处理
- **位置**：App.jsx L1102-1115

#### P0-3：停止生成可能丢失已生成内容
- **问题**：`content: msg.content || '（已停止生成）'` — 空字符串 `""` 是 falsy
- **影响**：如果 AI 刚开始生成（content 为 ""），停止后显示"已停止生成"而非保留空白
- **修复**：改为 `content: msg.content !== '' ? msg.content : '（已停止生成）'`
- **位置**：App.jsx L273

#### P0-4：编辑 textarea 不会自动调整高度
- **问题**：`rows` 只在初始渲染时计算，输入时不会动态调整
- **影响**：编辑长文本时 textarea 高度不变，体验差
- **修复**：添加 ref + useEffect 动态设置 scrollHeight
- **位置**：App.jsx L927-942

---

### 🟡 P1 — 体验关键改进（10 项）

#### P1-1：输入框自动扩展高度
- **现状**：固定 `rows={1}`，多行输入时不扩展
- **目标**：随输入内容自动扩展，最大 6 行，超出后滚动（参考 Claude/ChatGPT）
- **方案**：监听 input 变化，动态设置 textarea.style.height = scrollHeight

#### P1-2：添加"滚动到底部"悬浮按钮
- **现状**：向上滚动后，新消息到达时无法快速返回
- **目标**：当用户不在底部时，显示一个 ↓ 按钮（参考 ChatGPT）
- **方案**：利用已有的 `shouldAutoScrollRef`，当 `!isNearBottom` 时显示按钮

#### P1-3：代码块语法高亮 + 独立复制按钮
- **现状**：代码块无高亮，无独立复制
- **目标**：使用 highlight.js/prism 高亮，右上角显示语言标签和复制按钮（参考 ChatGPT/DeepSeek）
- **方案**：在 markdownComponents 中自定义 `code` 和 `pre` 组件

#### P1-4：历史记录时间分组
- **现状**：所有对话平铺显示
- **目标**：按"今天"、"昨天"、"近 7 天"、"更早"分组（参考 ChatGPT）
- **方案**：在 filteredHistory 渲染时按日期分组

#### P1-5：消息时间戳
- **现状**：无法知道消息发送时间
- **目标**：每条消息显示相对时间（如"刚刚"、"3分钟前"），hover 显示完整时间
- **方案**：消息模型添加 `timestamp` 字段

#### P1-6：改进错误提示
- **现状**：所有错误统一显示"网络错误"
- **目标**：区分网络断开、服务器错误、超时、请求被拒等
- **方案**：在 catch 中判断 error 类型，显示不同提示 + 重试按钮

#### P1-7：移动端侧边栏遮罩层
- **现状**：移动端打开侧边栏时，主内容��无遮罩
- **目标**：移动端侧边栏打开时显示半透明遮罩，点击遮罩关闭侧边栏
- **方案**：检测 `window.innerWidth < 768 && isSidebarOpen` 时渲染遮罩

#### P1-8：快速操作按钮防抖
- **现状**：快速点击会发送多条消息
- **目标**：点击后立即禁用，防止重复发送
- **方案**：利用已有的 `isLoading` 状态，在 sendMessage 开头检查

#### P1-9：对话导出功能
- **现状**：无法导出对话
- **目标**：支持导出为 Markdown 文件（参考 Claude）
- **方案**：设置面板添加"导出当前对话"按钮，生成 .md 文件下载

#### P1-10：历史记录搜索
- **现状**：无法搜索历史对话
- **目标**：侧边栏顶部添加搜索框，实时过滤历史记录（参考 ChatGPT）
- **方案**：添加 searchQuery state，在 filteredHistory 中增加关键词过滤

---

### 🟢 P2 — 体验精细打磨（14 项）

#### P2-1：图片点击放大预览
- 用户消息中的图片和输入区预览支持点击放大（lightbox）

#### P2-2：网络状态检测
- 使用 `navigator.onLine` + `online/offline` 事件，断网时显示提示条

#### P2-3：请求超时处理
- fetch 添加 30 秒超时，超时后显示"响应超时，请重试"

#### P2-4：localStorage 超限提示
- 捕获 QuotaExceededError，提示用户清理历史记录

#### P2-5：消息字符数限制
- 输入框添加字符计数器，超过限制时禁用发送

#### P2-6：侧边栏历史记录重命名
- 对话标题支持双击编辑重命名

#### P2-7：Markdown 渲染缓存
- 使用 useMemo 缓存 processContent 结果，避免重复解析

#### P2-8：输入框 Ctrl+Z 撤销支持
- 编辑消息时支持撤销操作

#### P2-9：消息复制格式优化
- AI 回答复制时保留 Markdown 格式，同时提供"复制纯文本"选项

#### P2-10：设置面板动画优化
- 抽屉关闭时添加滑出动画（当前只有打开动画）

#### P2-11：空状态优化
- 历史记录为空时显示更友好的引导（图标 + 文案 + 操作按钮）

#### P2-12：键盘快捷键
- Ctrl+N 新对话、Ctrl+Shift+S 切换搜索、Esc 关闭面板

#### P2-13：消息选中高亮
- 从历史记录加载对话时，高亮最后一条消息

#### P2-14：深色模式（预留）
- 设置面板添加主题切换入口，CSS 变量支持深色模式

---

## 三、实施路线图

### 第一阶段：Bug 修复 + 基础体验（P0 全部 + P1 前 5 项）
**预计改动：App.jsx + index.css**

| 序号 | 改进项 | 改动量 | 依赖 |
|------|--------|--------|------|
| 1 | P0-1 消息 key 修复 | 极小 | 无 |
| 2 | P0-2 点踩浮层关闭 | 小 | 无 |
| 3 | P0-3 停止生成内容保留 | 极小 | 无 |
| 4 | P0-4 编辑 textarea 自动高度 | 小 | 无 |
| 5 | P1-1 输入框自动扩展 | 小 | 无 |
| 6 | P1-2 滚动到底部按钮 | 中 | 无 |
| 7 | P1-4 历史记录时间分组 | 中 | 无 |
| 8 | P1-5 消息时间戳 | 中 | 无 |
| 9 | P1-8 快速操作防抖 | 极小 | 无 |

### 第二阶段：功能增强（P1 后 5 项）
**预计改动：App.jsx + 可能新增组件文件**

| 序号 | 改进项 | 改动量 | 依赖 |
|------|--------|--------|------|
| 10 | P1-3 代码块高亮 + 复制 | 大 | 需安装 highlight.js |
| 11 | P1-6 改进错误提示 | 中 | 无 |
| 12 | P1-7 移动端侧边栏遮罩 | 小 | 无 |
| 13 | P1-9 对话导出 | 中 | 无 |
| 14 | P1-10 历史搜索 | 中 | 无 |

### 第三阶段：精细打磨（P2 选择性实施）
根据用户反馈优先级调整。

---

## 四、关键实现方案

### 4.1 消息 key 修复
```jsx
// 修复前
{messages.map((msg, idx) => (
  <div key={idx}>

// 修复后 — 确保所有消息有唯一 id
{messages.map((msg, idx) => (
  <div key={msg.id || `msg-${idx}`}>
```
同时在创建用户消息时也添加 id：
```jsx
const userMessage = {
  role: 'user',
  content: messageToSend,
  id: `user-${Date.now()}`,
  timestamp: Date.now(),
  // ...
};
```

### 4.2 点踩浮层关闭
```jsx
// 方案：添加 feedbackPopoverId state
const [feedbackPopoverId, setFeedbackPopoverId] = useState(null);

// 点踩时
const rateFeedback = (msgId, rating) => {
  // ...existing logic...
  if (rating === 'bad') {
    setFeedbackPopoverId(msgId);
  } else {
    setFeedbackPopoverId(null);
  }
};

// 浮层显示条件改为
{feedbackPopoverId === msg.id && !msg.feedbackReason && (
  <div className="...">...</div>
)}

// 全局遮罩 onClick 中添加
setFeedbackPopoverId(null);
```

### 4.3 输入框 + 编辑框自动高度
```jsx
// 通用自动高度函数
const autoResize = (el) => {
  if (!el) return;
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 200) + 'px';
};

// 主输入框
<textarea
  ref={inputRef}
  value={input}
  onChange={(e) => {
    setInput(e.target.value);
    autoResize(e.target);
  }}
  style={{ minHeight: '38px', maxHeight: '200px' }}
/>

// 编辑框 — 使用 ref + useEffect
const editTextareaRef = useRef(null);
useEffect(() => {
  autoResize(editTextareaRef.current);
}, [editingContent]);
```

### 4.4 滚动到底部按钮
```jsx
const [showScrollBtn, setShowScrollBtn] = useState(false);

const handleScroll = (e) => {
  const container = e.target;
  const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
  shouldAutoScrollRef.current = isNearBottom;
  setShowScrollBtn(!isNearBottom);
};

const scrollToBottom = () => {
  messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  shouldAutoScrollRef.current = true;
  setShowScrollBtn(false);
};

// JSX — 在消息区域底部
{showScrollBtn && (
  <button
    onClick={scrollToBottom}
    className="absolute bottom-24 right-6 p-2.5 rounded-full bg-white shadow-float-md
               border border-slate-100 text-slate-400 hover:text-slate-600
               transition-all animate-fade-in z-10"
  >
    <ChevronDown size={18} />
  </button>
)}
```

### 4.5 历史记录时间分组
```jsx
const groupHistoryByDate = (items) => {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today - 86400000);
  const weekAgo = new Date(today - 7 * 86400000);

  const groups = { '今天': [], '昨天': [], '近 7 天': [], '更早': [] };

  items.forEach(item => {
    const date = new Date(item.id); // id 是 Date.now() 生成的时间戳
    if (date >= today) groups['今天'].push(item);
    else if (date >= yesterday) groups['昨天'].push(item);
    else if (date >= weekAgo) groups['近 7 天'].push(item);
    else groups['更早'].push(item);
  });

  return Object.entries(groups).filter(([_, items]) => items.length > 0);
};
```

### 4.6 消息时间戳
```jsx
// 消息模型添加 timestamp
const userMessage = {
  role: 'user',
  content: messageToSend,
  id: `user-${Date.now()}`,
  timestamp: Date.now(),
};

// 渲染 — 相对时间
const formatRelativeTime = (ts) => {
  if (!ts) return '';
  const diff = Date.now() - ts;
  if (diff < 60000) return '刚刚';
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
  return new Date(ts).toLocaleDateString('zh-CN');
};
```

### 4.7 代码块高亮 + 复制（第二阶段）
```jsx
// 安装：npm install highlight.js
import hljs from 'highlight.js/lib/core';
import 'highlight.js/styles/github.css';

// markdownComponents 扩展
const markdownComponents = {
  table: ({ children }) => (
    <div className="table-wrapper"><table>{children}</table></div>
  ),
  code: ({ node, inline, className, children, ...props }) => {
    const match = /language-(\w+)/.exec(className || '');
    const lang = match ? match[1] : '';
    const codeStr = String(children).replace(/\n$/, '');

    if (!inline && lang) {
      return (
        <div className="relative group/code">
          <div className="absolute top-2 right-2 flex items-center gap-2">
            <span className="text-[10px] text-slate-400 uppercase">{lang}</span>
            <button
              onClick={() => copyToClipboard(codeStr, `code-${codeStr.slice(0,20)}`)}
              className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-white/10
                         opacity-0 group-hover/code:opacity-100 transition-opacity"
            >
              {copiedId === `code-${codeStr.slice(0,20)}` ? <Check size={14} /> : <Copy size={14} />}
            </button>
          </div>
          <pre className="!mt-0"><code>{codeStr}</code></pre>
        </div>
      );
    }
    return <code className={className} {...props}>{children}</code>;
  },
};
```

---

## 五、不做的事项（避免过度设计）

| 功能 | 原因 |
|------|------|
| 对话分支/版本管理 | 复杂度极高，需要树状数据结构，当前阶段不值得 |
| 虚拟滚动 | 当前消息量不大，过早优化 |
| 深色模式完整��现 | 需要全面改造 CSS 变量，工作量大，可预留入口 |
| 语音输入 | 需要 Web Speech API，兼容性问题多 |
| 多语言 i18n | 当前只面向中文用户 |
| PWA 离线支持 | 需要 Service Worker，复杂度高 |
