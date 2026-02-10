import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import {
  Send, Bot, User, Brain, Search, Loader2,
  Plus, MessageSquare, Settings, MoreVertical,
  PanelLeftClose, PanelLeft, Trash2, Home, Store,
  Calculator, TrendingUp, Users, FileText, Sparkles,
  ChevronDown, ChevronRight, Gift, Building2, Zap, X,
  ImagePlus, Target,
  Square, Pencil, Copy, Check, RefreshCw, ThumbsUp, ThumbsDown,
  Type, Keyboard, AlertTriangle, Download
} from 'lucide-react';
import { StructuredDataRenderer } from './components/StructuredData';
import './index.css';

// 思考过程组件 — 极简内联折叠（左边线+展开）
const ThinkingBlock = React.memo(({ thinking, msgId, isExpanded, onToggle }) => {
  if (!thinking || thinking.length === 0) return null;

  return (
    <div className="thinking-inline mb-2">
      <button
        onClick={() => onToggle(msgId)}
        className="thinking-inline-header"
      >
        <Brain size={14} />
        <span className="font-medium">思考过程</span>
        <span className="text-xs text-thinking-400">({thinking.length} 步)</span>
        <ChevronRight
          size={14}
          className={`transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`}
        />
      </button>
      {isExpanded && (
        <div className="thinking-inline-content">
          {thinking.map((step, i) => (
            <div key={i} className="flex gap-2 text-sm">
              <span className="flex-shrink-0 text-xs text-thinking-400 font-mono mt-0.5">{i + 1}.</span>
              <p className="text-slate-500">{step}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

// 专家诊断信息组件 — 极简灰色小文字
const ExpertDebugBlock = React.memo(({ expertInfo, msgId, isExpanded, onToggle }) => {
  if (!expertInfo) return null;

  const confidencePercent = Math.round((expertInfo.stage_confidence || 0) * 100);

  return (
    <div className="mb-2">
      <button
        onClick={() => onToggle(msgId)}
        className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-500 transition-colors"
      >
        <Target size={12} />
        <span>{expertInfo.expert_role || '通用顾问'}</span>
        <span className="text-slate-300">·</span>
        <span>{expertInfo.detected_stage || '未知'}阶段</span>
        <span className="text-slate-300">·</span>
        <span>{confidencePercent}%</span>
        <ChevronRight
          size={12}
          className={`transition-transform duration-200 ${isExpanded ? 'rotate-90' : ''}`}
        />
      </button>
      {isExpanded && (
        <div className="mt-1.5 pl-4 border-l border-slate-100 text-xs text-slate-400 space-y-1">
          {expertInfo.expert_value && (
            <div><span className="text-slate-500">专家价值：</span>{expertInfo.expert_value}</div>
          )}
          {expertInfo.emotional_state && (
            <div><span className="text-slate-500">用户情绪：</span>{expertInfo.emotional_state}</div>
          )}
          {expertInfo.focus_points && expertInfo.focus_points.length > 0 && (
            <div><span className="text-slate-500">关注重点：</span>{expertInfo.focus_points.join('、')}</div>
          )}
          {expertInfo.deep_need && (
            <div><span className="text-slate-500">深层需求：</span>{expertInfo.deep_need}</div>
          )}
          {expertInfo.potential_needs && expertInfo.potential_needs.length > 0 && (
            <div><span className="text-slate-500">潜在需求：</span>{expertInfo.potential_needs.join('、')}</div>
          )}
          {expertInfo.stage_transition && (
            <div className="text-orange-400">
              ⚡ {expertInfo.stage_transition.from_stage} → {expertInfo.stage_transition.to_stage}
              （{Math.round(expertInfo.stage_transition.confidence * 100)}%）
            </div>
          )}
        </div>
      )}
    </div>
  );
});

function App() {
  const [userType, setUserType] = useState('c_end');
  const [showUserTypeMenu, setShowUserTypeMenu] = useState(false);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [enableSearch, setEnableSearch] = useState(true);
  const [showThinking, setShowThinking] = useState(true);
  const [currentChatId, setCurrentChatId] = useState(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [activeMenuId, setActiveMenuId] = useState(null);
  const [expandedThinking, setExpandedThinking] = useState({});
  const [expandedExpert, setExpandedExpert] = useState({});
  const [history, setHistory] = useState(() => {
    try {
      const saved = localStorage.getItem('decopilot_chat_history');
      return saved ? JSON.parse(saved) : [];
    } catch (e) {
      return [];
    }
  });

  const [selectedImage, setSelectedImage] = useState(null);
  const [imagePreview, setImagePreview] = useState(null);
  const [isUploadingImage, setIsUploadingImage] = useState(false);

  // 新增功能 state
  const [copiedId, setCopiedId] = useState(null);           // 复制成功提示
  const [editingMsgIdx, setEditingMsgIdx] = useState(null); // 正在编辑的消息索引
  const [editingContent, setEditingContent] = useState('');  // 编辑中的文本
  const [showSettings, setShowSettings] = useState(false);   // 设置面板
  const [toast, setToast] = useState(null);                  // Toast 提示
  const [feedbackPopoverId, setFeedbackPopoverId] = useState(null); // 点踩反馈浮层
  const [showScrollBtn, setShowScrollBtn] = useState(false);       // 滚动到底部按钮
  const [historySearch, setHistorySearch] = useState('');           // 历史搜索
  const [settings, setSettings] = useState(() => {
    try {
      const saved = localStorage.getItem('decopilot_settings');
      return saved ? JSON.parse(saved) : { sendKey: 'enter', fontSize: 'medium' };
    } catch (e) {
      return { sendKey: 'enter', fontSize: 'medium' };
    }
  });

  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const inputRef = useRef(null);
  const fileInputRef = useRef(null);
  const shouldAutoScrollRef = useRef(true);
  const abortControllerRef = useRef(null);  // 终止回答
  const editTextareaRef = useRef(null);     // 编辑框

  // 通用 textarea 自动高度
  const autoResize = (el, maxHeight = 200) => {
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, maxHeight) + 'px';
  };

  const config = {
    c_end: {
      name: '业主模式',
      shortName: '业主',
      icon: Home,
      theme: 'owner',
      greeting: '你好！我是洞居平台的装修顾问"小洞"，很高兴为您服务。\n\n我可以帮您：\n- 解答装修问题\n- 查询补贴政策\n- 推荐优质商家\n\n请问有什么可以帮您的？',
      quickActions: [
        { icon: Gift, label: '查询补贴', prompt: '装修补贴怎么领取？有什么条件？' },
        { icon: Sparkles, label: '风格推荐', prompt: '现在流行什么装修风格？' },
        { icon: Calculator, label: '预算评估', prompt: '100平米的房子装修大概需要多少钱？' },
        { icon: Store, label: '商家推荐', prompt: '有什么靠谱的家具商家推荐？' },
      ]
    },
    b_end: {
      name: '商家模式',
      shortName: '商家',
      icon: Building2,
      theme: 'merchant',
      greeting: '您好！我是洞居平台的商家助手"洞掌柜"，专门为入驻商家提供服务。\n\n我可以帮您：\n- 解答入驻问题\n- 分析经营数据\n- 优化获客策略\n\n请问有什么可以帮您的？',
      quickActions: [
        { icon: FileText, label: '入驻指南', prompt: '如何入驻洞居平台？需要什么条件？' },
        { icon: TrendingUp, label: 'ROI分析', prompt: '如何提高投放ROI？' },
        { icon: Users, label: '获客策略', prompt: '有什么好的获客方法？' },
        { icon: Zap, label: '话术生成', prompt: '帮我生成一段首次接触客户的话术' },
      ]
    }
  };

  const currentConfig = config[userType];
  const theme = currentConfig.theme;
  const UserIcon = currentConfig.icon;

  // Effects
  useEffect(() => {
    setMessages([{ role: 'assistant', content: currentConfig.greeting }]);
  }, [userType]);

  useEffect(() => {
    if (shouldAutoScrollRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const handleScroll = (e) => {
    const container = e.target;
    const isNearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
    shouldAutoScrollRef.current = isNearBottom;
    setShowScrollBtn(!isNearBottom);
  };

  const enableAutoScroll = () => {
    shouldAutoScrollRef.current = true;
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    shouldAutoScrollRef.current = true;
    setShowScrollBtn(false);
  };

  useEffect(() => {
    if (currentChatId) {
      setHistory(prev => prev.map(item =>
        item.id === currentChatId ? { ...item, messages } : item
      ));
    }
  }, [messages, currentChatId]);

  useEffect(() => {
    try {
      localStorage.setItem('decopilot_chat_history', JSON.stringify(history));
    } catch (e) {}
  }, [history]);

  useEffect(() => {
    try {
      localStorage.setItem('decopilot_settings', JSON.stringify(settings));
    } catch (e) {}
  }, [settings]);

  // 编辑框自动高度
  useEffect(() => {
    autoResize(editTextareaRef.current, 240);
  }, [editingContent]);

  // Handlers
  const startNewChat = () => {
    setMessages([{ role: 'assistant', content: currentConfig.greeting }]);
    setInput('');
    setCurrentChatId(null);
    setActiveMenuId(null);
    setExpandedThinking({});
    setExpandedExpert({});
    clearSelectedImage();
    inputRef.current?.focus();
  };

  const handleImageSelect = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.type.startsWith('image/')) {
      alert('请选择图片文件');
      return;
    }

    if (file.size > 10 * 1024 * 1024) {
      alert('图片大小不能超过 10MB');
      return;
    }

    setSelectedImage(file);
    const reader = new FileReader();
    reader.onload = (e) => setImagePreview(e.target.result);
    reader.readAsDataURL(file);
  };

  const clearSelectedImage = () => {
    setSelectedImage(null);
    setImagePreview(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // ===== 终止回答 =====
  const stopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsLoading(false);
    setIsUploadingImage(false);
    setMessages(prev => prev.map(msg =>
      msg.role === 'assistant' && !msg.isComplete
        ? { ...msg, isComplete: true, content: msg.content !== '' ? msg.content : '（已停止生成）' }
        : msg
    ));
  };

  // ===== 复制到剪贴板 =====
  const copyToClipboard = async (text, id) => {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    }
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  // ===== 编辑用户消息 =====
  const startEdit = (idx, content) => {
    setEditingMsgIdx(idx);
    setEditingContent(content);
  };

  const cancelEdit = () => {
    setEditingMsgIdx(null);
    setEditingContent('');
  };

  const submitEdit = (msgIdx) => {
    const newContent = editingContent.trim();
    if (!newContent) return;
    // 截断到编辑的消息位置（不含该消息及之后的所有消息）
    const truncated = messages.slice(0, msgIdx);
    setMessages(truncated);
    setEditingMsgIdx(null);
    setEditingContent('');
    // 用编辑后的内容重新发送
    setTimeout(() => sendMessage(newContent), 50);
  };

  // ===== 重新回答 =====
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
    setTimeout(() => sendMessage(userContent), 50);
  };

  // ===== 评价回答 =====
  const rateFeedback = (msgId, rating) => {
    setMessages(prev => prev.map(msg => {
      if (msg.id !== msgId) return msg;
      const newRating = msg.feedback === rating ? null : rating;
      return { ...msg, feedback: newRating, feedbackReason: null };
    }));
    if (rating === 'good') {
      setFeedbackPopoverId(null);
      showToast('感谢您的反馈！');
    } else if (rating === 'bad') {
      setFeedbackPopoverId(msgId);
    } else {
      setFeedbackPopoverId(null);
    }
  };

  const rateFeedbackWithReason = (msgId, reason) => {
    setMessages(prev => prev.map(msg =>
      msg.id === msgId ? { ...msg, feedbackReason: reason } : msg
    ));
    setFeedbackPopoverId(null);
    showToast('感谢您的反馈，我们会持续改进！');
  };

  // ===== Toast 提示 =====
  const showToast = (message) => {
    setToast(message);
    setTimeout(() => setToast(null), 2500);
  };

  // ===== 设置更新 =====
  const updateSetting = (key, value) => {
    setSettings(prev => ({ ...prev, [key]: value }));
  };

  const clearAllHistory = () => {
    if (window.confirm('确定要清除所有对话记录吗？此操作不可撤销。')) {
      setHistory([]);
      startNewChat();
      setShowSettings(false);
      showToast('已清除所有对话记录');
    }
  };

  // ===== 对话导出 =====
  const exportCurrentChat = () => {
    if (messages.length <= 1) {
      showToast('当前没有可导出的对话');
      return;
    }
    const lines = ['# DecoPilot 对话记录\n'];
    lines.push(`> 导出时间：${new Date().toLocaleString('zh-CN')}`);
    lines.push(`> 模式：${currentConfig.name}\n`);
    lines.push('---\n');

    messages.forEach(msg => {
      if (msg.role === 'user') {
        lines.push(`## 🧑 用户\n`);
        lines.push(msg.content + '\n');
      } else if (msg.role === 'assistant' && msg.content) {
        lines.push(`## 🤖 ${userType === 'c_end' ? '小洞' : '洞掌柜'}\n`);
        lines.push(msg.content + '\n');
      }
    });

    const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `DecoPilot_${new Date().toISOString().slice(0, 10)}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    showToast('对话已导出');
  };

  const uploadImage = async (file, message = '') => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('message', message);
    formData.append('user_type', userType);
    formData.append('enable_search', enableSearch);
    formData.append('show_thinking', showThinking);

    const response = await fetch('/api/v1/chat/chat-with-media', {
      method: 'POST',
      body: formData
    });

    if (!response.ok) {
      throw new Error('图片上传失败');
    }

    return response;
  };

  const loadChat = (chat) => {
    setCurrentChatId(chat.id);
    setMessages(chat.messages);
    setExpandedThinking({});
    setExpandedExpert({});
    if (window.innerWidth < 768) setIsSidebarOpen(false);
  };

  const deleteChat = (e, chatId) => {
    e.stopPropagation();
    setHistory(prev => prev.filter(item => item.id !== chatId));
    if (currentChatId === chatId) startNewChat();
    setActiveMenuId(null);
  };

  const createHistoryItem = (firstUserMsg, initialMessages) => {
    const newId = Date.now();
    const newItem = {
      id: newId,
      title: firstUserMsg.length > 20 ? firstUserMsg.substring(0, 20) + '...' : firstUserMsg,
      date: new Date().toLocaleDateString('zh-CN'),
      messages: initialMessages,
      userType
    };
    setHistory(prev => [newItem, ...prev]);
    return newId;
  };

  const sendMessage = async (customMessage = null) => {
    const messageToSend = customMessage || input.trim();
    const hasImage = selectedImage !== null;

    if ((!messageToSend && !hasImage) || isLoading) return;

    enableAutoScroll();
    setInput('');
    setEditingMsgIdx(null);
    setEditingContent('');
    // 重置输入框高度
    if (inputRef.current) {
      inputRef.current.style.height = 'auto';
    }

    const userMessage = {
      role: 'user',
      content: messageToSend || '请帮我分析这张图片',
      image: hasImage ? imagePreview : null,
      id: `user-${Date.now()}`,
      timestamp: Date.now()
    };

    let updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    setIsLoading(true);

    // 创建 AbortController 用于终止回答
    const controller = new AbortController();
    abortControllerRef.current = controller;

    const imageToUpload = selectedImage;
    clearSelectedImage();

    let activeId = currentChatId;
    if (!activeId) {
      activeId = createHistoryItem(messageToSend || '[图片]', updatedMessages);
      setCurrentChatId(activeId);
    }

    const newMsgId = Date.now();
    updatedMessages = [...updatedMessages, { role: 'assistant', content: '', thinking: [], expertInfo: null, structuredBlocks: [], id: newMsgId, feedback: null, feedbackReason: null, timestamp: Date.now() }];
    setMessages(updatedMessages);

    try {
      if (hasImage) {
        setIsUploadingImage(true);
        const response = await uploadImage(imageToUpload, messageToSend);
        setIsUploadingImage(false);
        await processStream(response, newMsgId);
      } else {
        const endpoint = userType === 'c_end' ? '/api/v1/chat/c-end' : '/api/v1/chat/b-end';
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            message: messageToSend,
            session_id: `${userType}_${activeId}`,
            enable_search: enableSearch,
            show_thinking: showThinking
          }),
          signal: controller.signal
        });

        if (!response.ok) {
          const legacyResponse = await fetch('/chat_stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: messageToSend, enable_search: enableSearch, show_thinking: showThinking }),
            signal: controller.signal
          });
          if (!legacyResponse.ok) throw new Error('Server error');
          await processStream(legacyResponse, newMsgId);
        } else {
          await processStream(response, newMsgId);
        }
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        // 用户主动终止，不显示错误
        return;
      }
      // 区分错误类型
      let errMsg = '抱歉，发生了未知错误，请稍后重试。';
      if (!navigator.onLine) {
        errMsg = '⚠️ 网络已断开，请检查网络连接后重试。';
      } else if (error.message === 'Server error') {
        errMsg = '⚠️ 服务器繁忙，请稍后重试。';
      } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
        errMsg = '⚠️ 无法连接到服务器，请检查网络连接。';
      } else {
        errMsg = '⚠️ 请求失败，请稍后重试。';
      }
      setMessages(prev => prev.map(msg =>
        msg.id === newMsgId
          ? { ...msg, content: msg.content !== '' ? msg.content + '\n\n' + errMsg : errMsg, isComplete: true }
          : msg
      ));
    } finally {
      setIsLoading(false);
      setIsUploadingImage(false);
      abortControllerRef.current = null;
    }
  };

  const STRUCTURED_TYPES = new Set([
    'table', 'subsidy_calc', 'merchant_card', 'merchant_list',
    'process_steps', 'checklist', 'comparison', 'sources',
    'quick_replies', 'action_buttons',
  ]);

  const processStream = async (response, newMsgId) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');

      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const data = JSON.parse(line);
          setMessages(prev => prev.map(msg => {
            if (msg.id !== newMsgId) return msg;
            if (data.type === 'thinking') {
              return { ...msg, thinking: data.content };
            } else if (data.type === 'answer' || data.type === 'text') {
              return { ...msg, content: msg.content + (data.content || data.data?.content || '') };
            } else if (data.type === 'expert_debug') {
              return { ...msg, expertInfo: data.data };
            } else if (data.type === 'error') {
              const errMsg = data.data?.message || data.message || '发生未知错误';
              return { ...msg, content: msg.content + `\n\n⚠️ ${errMsg}` };
            } else if (STRUCTURED_TYPES.has(data.type)) {
              const block = { type: data.type, data: data.data, id: Date.now() + Math.random() };
              return { ...msg, structuredBlocks: [...(msg.structuredBlocks || []), block] };
            } else if (data.type === 'stream_start' || data.type === 'stream_end' || data.type === 'meta') {
              return msg;
            }
            return msg;
          }));
        } catch (e) {
          if (line.trim().startsWith('{')) {
            buffer = line + '\n' + buffer;
          }
        }
      }
    }

    if (buffer.trim()) {
      try {
        const data = JSON.parse(buffer);
        setMessages(prev => prev.map(msg => {
          if (msg.id !== newMsgId) return msg;
          if (data.type === 'answer' || data.type === 'text') {
            return { ...msg, content: msg.content + (data.content || data.data?.content || '') };
          } else if (STRUCTURED_TYPES.has(data.type)) {
            const block = { type: data.type, data: data.data, id: Date.now() + Math.random() };
            return { ...msg, structuredBlocks: [...(msg.structuredBlocks || []), block] };
          }
          return msg;
        }));
      } catch (e) {}
    }

    setMessages(prev => prev.map(msg =>
      msg.id === newMsgId ? { ...msg, isComplete: true } : msg
    ));
  };

  const switchUserType = (type) => {
    setUserType(type);
    setShowUserTypeMenu(false);
    startNewChat();
  };

  const toggleThinking = (msgId) => {
    setExpandedThinking(prev => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  const toggleExpert = (msgId) => {
    setExpandedExpert(prev => ({ ...prev, [msgId]: !prev[msgId] }));
  };

  // ===== 内容预处理 =====
  //
  // 设计原则：
  // 1. 信任 react-markdown + remark-gfm 的表格解析能力
  // 2. 只做最小化修复：修复 AI 在表格单元格内换行导致的结构破坏
  // 3. 表格的美观通过 CSS 解决（自适应列宽、溢出滚动、合理间距）
  //
  // AI 常见的表格问题：
  //   单元格内写了换行+列表（- xxx），导致 react-markdown 把一行拆成多行
  //   解决：检测到不完整的表格行（以 | 开头但不以 | 结尾），合并续行内容
  //   续行用 <br> 连接，保持单元格内的列表可读性

  /**
   * 修复表格：将被 AI 换行拆散的表格行重新合并
   *
   * 输入示例（AI 实际输出）：
   *   | 阶段 | 内容 |
   *   | --- | --- |
   *   | 硬装 | - 水电改造
   *   - 防水施工
   *   - 瓷砖铺贴 |
   *
   * 输出（修复后，单元格内用 <br> 保持列表换行）：
   *   | 阶段 | 内容 |
   *   | --- | --- |
   *   | 硬装 | - 水电改造<br>- 防水施工<br>- 瓷砖铺贴 |
   */
  const processContent = (content) => {
    if (!content) return content;

    let text = content.replace(/<br\s*\/?>/gi, '\n');

    // 如果内容中没有 | 符号，不可能有表格，直接返回
    if (!text.includes('|')) return text;

    const lines = text.split('\n');
    const result = [];
    let pendingTableRow = null; // 正在拼接的不完整表格行

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];
      const trimmed = line.trim();

      // 判断是否是完整的表格行：以 | 开头且以 | 结尾
      const startsWithPipe = trimmed.startsWith('|');
      const endsWithPipe = trimmed.endsWith('|');
      const isCompleteLine = startsWithPipe && endsWithPipe && trimmed.length > 1;
      const isSeparator = /^\|[\s\-:|]+\|$/.test(trimmed);

      if (pendingTableRow !== null) {
        // 正在拼接一个不完整的表格行
        if (endsWithPipe) {
          // 这一行以 | 结尾 → 拼接完成
          // 如果这行也以 | 开头，说明是续行中包含 | 分隔的内容
          const appendPart = startsWithPipe ? trimmed : trimmed;
          pendingTableRow += '<br>' + appendPart;
          result.push(pendingTableRow);
          pendingTableRow = null;
        } else if (startsWithPipe && !endsWithPipe) {
          // 新的不完整行开头 → 上一个 pending 强制结束，开始新的 pending
          result.push(pendingTableRow + ' |');
          pendingTableRow = trimmed;
        } else if (trimmed === '') {
          // 空行 → pending 强制结束
          result.push(pendingTableRow + ' |');
          pendingTableRow = null;
          result.push(line);
        } else {
          // 普通文本续行（如 "- 防水施工"、"✅ 推荐"）→ 用 <br> 合并到 pending
          pendingTableRow += '<br>' + trimmed;
        }
      } else {
        // 没有 pending
        if (isCompleteLine || isSeparator) {
          // 完整的表格行，直接输出
          result.push(line);
        } else if (startsWithPipe && !endsWithPipe && trimmed.length > 1) {
          // 以 | 开头但不以 | 结尾 → 不完整的表格行，开始拼接
          pendingTableRow = trimmed;
        } else {
          // 普通行
          result.push(line);
        }
      }
    }

    // 如果最后还有 pending，强制结束
    if (pendingTableRow !== null) {
      result.push(pendingTableRow + ' |');
    }

    return result.join('\n');
  };

  // 自定义 Markdown 组件：表格渲染增强 + 代码块复制
  const markdownComponents = {
    table: ({ children }) => (
      <div className="table-wrapper">
        <table>{children}</table>
      </div>
    ),
    pre: ({ children }) => {
      // 提取代码内容用于复制
      const codeEl = React.Children.toArray(children).find(
        child => child?.type === 'code' || child?.props?.className?.includes('language-')
      );
      const codeStr = codeEl?.props?.children
        ? String(codeEl.props.children).replace(/\n$/, '')
        : '';
      const langMatch = codeEl?.props?.className
        ? /language-(\w+)/.exec(codeEl.props.className)
        : null;
      const lang = langMatch ? langMatch[1] : '';
      const codeId = `code-${codeStr.slice(0, 30)}`;

      return (
        <div className="relative group/code my-4">
          <div className="absolute top-2 right-2 flex items-center gap-2 opacity-0 group-hover/code:opacity-100 transition-opacity z-10">
            {lang && (
              <span className="text-[10px] text-slate-400 uppercase font-mono">{lang}</span>
            )}
            <button
              onClick={() => copyToClipboard(codeStr, codeId)}
              className="p-1 rounded text-slate-400 hover:text-slate-200 hover:bg-white/10 transition-colors"
              title="复制代码"
            >
              {copiedId === codeId ? <Check size={14} className="text-green-400" /> : <Copy size={14} />}
            </button>
          </div>
          <pre className="!mt-0 rounded-xl overflow-x-auto bg-slate-800 text-slate-100 p-4">
            {children}
          </pre>
        </div>
      );
    },
  };

  const TypingIndicator = () => (
    <div className="typing-indicator">
      <span className="typing-dot animate-typing-1"></span>
      <span className="typing-dot animate-typing-2"></span>
      <span className="typing-dot animate-typing-3"></span>
    </div>
  );

  const filteredHistory = history.filter(item => {
    if (item.userType !== userType) return false;
    if (historySearch.trim()) {
      const q = historySearch.trim().toLowerCase();
      return item.title.toLowerCase().includes(q);
    }
    return true;
  });

  // P1-4: 历史记录时间分组
  const groupHistoryByDate = (items) => {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today - 86400000);
    const weekAgo = new Date(today - 7 * 86400000);

    const groups = [];
    const buckets = { '今天': [], '昨天': [], '近 7 天': [], '更早': [] };

    items.forEach(item => {
      const date = new Date(item.id); // id 是 Date.now() 生成的时间戳
      if (date >= today) buckets['今天'].push(item);
      else if (date >= yesterday) buckets['昨天'].push(item);
      else if (date >= weekAgo) buckets['近 7 天'].push(item);
      else buckets['更早'].push(item);
    });

    for (const [label, items] of Object.entries(buckets)) {
      if (items.length > 0) groups.push({ label, items });
    }
    return groups;
  };

  const historyGroups = groupHistoryByDate(filteredHistory);

  // P1-5: 消息时间戳格式化
  const formatRelativeTime = (ts) => {
    if (!ts) return '';
    const diff = Date.now() - ts;
    if (diff < 60000) return '刚刚';
    if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
    return new Date(ts).toLocaleDateString('zh-CN');
  };

  const fontSizeClass = settings.fontSize === 'small' ? 'font-size-small' : settings.fontSize === 'large' ? 'font-size-large' : '';

  return (
    <div className={`flex h-screen overflow-hidden bg-white ${fontSizeClass}`}>
      {/* Sidebar */}
      <aside className={`
        ${isSidebarOpen ? 'w-[260px]' : 'w-0'}
        flex-shrink-0 flex flex-col
        sidebar-glass z-50 relative
        transition-all duration-300 ease-smooth overflow-hidden
      `}>
        {/* Logo */}
        <div className="h-14 px-5 flex items-center gap-3">
          <img
            src="/logo.png"
            alt="洞居"
            className="w-7 h-7 rounded-md object-contain flex-shrink-0"
          />
          <div className="min-w-0">
            <h1 className="font-semibold text-[13px] text-slate-800 leading-tight">DecoPilot</h1>
            <p className="text-[10px] text-slate-400 leading-tight mt-0.5">智能装修助手</p>
          </div>
        </div>

        {/* Mode Switcher */}
        <div className="px-3 pb-2.5">
          <div className="relative">
            <button
              onClick={() => setShowUserTypeMenu(!showUserTypeMenu)}
              className={`
                w-full flex items-center justify-between px-3 py-2 rounded-lg text-[13px]
                ${theme === 'owner' ? 'bg-owner-50/60 text-owner-600' : 'bg-merchant-50/60 text-merchant-600'}
                transition-all duration-200 hover:shadow-soft
              `}
            >
              <div className="flex items-center gap-2">
                <UserIcon size={15} />
                <span className="font-medium">{currentConfig.name}</span>
              </div>
              <ChevronDown size={13} className={`transition-transform duration-200 opacity-60 ${showUserTypeMenu ? 'rotate-180' : ''}`} />
            </button>

            {showUserTypeMenu && (
              <div className="absolute top-full left-0 right-0 mt-1 bg-white rounded-lg shadow-float-lg border border-slate-100/80 overflow-hidden z-50 animate-scale-in">
                {Object.entries(config).map(([key, cfg]) => (
                  <button
                    key={key}
                    onClick={() => switchUserType(key)}
                    className={`
                      w-full flex items-center gap-2.5 px-3 py-2.5 text-left text-[13px] transition-colors
                      ${userType === key
                        ? (cfg.theme === 'owner' ? 'bg-owner-50/60 text-owner-600' : 'bg-merchant-50/60 text-merchant-600')
                        : 'hover:bg-slate-50 text-slate-600'
                      }
                    `}
                  >
                    <cfg.icon size={15} />
                    <div>
                      <div className="font-medium">{cfg.name}</div>
                      <div className="text-[10px] text-slate-400 mt-0.5">
                        {key === 'c_end' ? '装修咨询、补贴查询' : '入驻指导、经营分析'}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* New Chat */}
        <div className="px-3 pb-2.5">
          <button
            onClick={startNewChat}
            className={`
              w-full flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg text-[13px] font-medium
              ${theme === 'owner' ? 'btn-owner' : 'btn-merchant'}
            `}
          >
            <Plus size={15} />
            <span>新对话</span>
          </button>
        </div>

        {/* History Search */}
        <div className="px-3 pb-1">
          <div className="relative">
            <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-300" />
            <input
              type="text"
              value={historySearch}
              onChange={(e) => setHistorySearch(e.target.value)}
              placeholder="搜索对话..."
              className="w-full pl-8 pr-3 py-1.5 rounded-lg bg-slate-50 border border-slate-100 text-[12px] text-slate-600 placeholder-slate-300 focus:outline-none focus:border-slate-200 transition-colors"
            />
            {historySearch && (
              <button
                onClick={() => setHistorySearch('')}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500"
              >
                <X size={12} />
              </button>
            )}
          </div>
        </div>

        {/* History */}
        <div className="flex-1 overflow-y-auto px-2 mt-1">
          {historyGroups.map(group => (
            <div key={group.label}>
              <div className="px-2 py-1.5 mt-2 first:mt-0 text-[10px] font-medium text-slate-400 uppercase tracking-widest">
                {group.label}
              </div>
              <div className="space-y-px">
                {group.items.map((item) => (
                  <div key={item.id} className="relative group animate-fade-in">
                    <button
                      onClick={() => loadChat(item)}
                      className={`
                        w-full flex items-center gap-2 px-2.5 py-[7px] rounded-md text-left transition-all duration-150
                        ${currentChatId === item.id
                          ? (theme === 'owner' ? 'bg-owner-50/70 text-owner-600' : 'bg-merchant-50/70 text-merchant-600')
                          : 'text-slate-500 hover:bg-slate-100/50 hover:text-slate-700'
                        }
                      `}
                    >
                      <MessageSquare size={13} className="flex-shrink-0 opacity-40" />
                      <span className="flex-1 truncate text-[13px]">{item.title}</span>
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setActiveMenuId(activeMenuId === item.id ? null : item.id);
                      }}
                      className="absolute right-1 top-1/2 -translate-y-1/2 p-1 rounded opacity-0 group-hover:opacity-100 hover:bg-white/80 transition-all"
                    >
                      <MoreVertical size={11} className="text-slate-400" />
                    </button>
                    {activeMenuId === item.id && (
                      <div className="absolute right-0 top-full mt-0.5 bg-white rounded-lg shadow-float-md border border-slate-100/80 py-0.5 z-50 animate-scale-in">
                        <button
                          onClick={(e) => deleteChat(e, item.id)}
                          className="flex items-center gap-1.5 px-3 py-1.5 text-[13px] text-red-500 hover:bg-red-50 w-full transition-colors"
                        >
                          <Trash2 size={12} />
                          删除
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))}
          {filteredHistory.length === 0 && (
            <div className="text-center py-8 text-slate-300 text-xs">
              暂无历史记录
            </div>
          )}
        </div>

        {/* Settings */}
        <div className="p-2 border-t border-slate-100/60">
          <button
            onClick={() => setShowSettings(true)}
            className="w-full flex items-center gap-2 px-2.5 py-[7px] rounded-md text-slate-400 hover:bg-slate-100/50 hover:text-slate-600 transition-colors text-[13px]"
          >
            <Settings size={15} />
            <span>设置</span>
          </button>
        </div>
      </aside>

      {/* 移动端侧边栏遮罩 */}
      {isSidebarOpen && (
        <div
          className="fixed inset-0 bg-black/30 z-40 md:hidden animate-fade-in"
          onClick={() => setIsSidebarOpen(false)}
        />
      )}

      {/* Main */}
      <main className="flex-1 flex flex-col min-w-0 relative">
        {/* Sidebar toggle */}
        <button
          onClick={() => setIsSidebarOpen(!isSidebarOpen)}
          className={`
            absolute top-3.5 left-3.5 z-20 p-1.5 rounded-lg transition-all duration-200
            ${isSidebarOpen
              ? 'text-slate-400 hover:text-slate-600 hover:bg-slate-100/60'
              : 'bg-white shadow-float text-slate-500 hover:text-slate-700 hover:shadow-float-md'
            }
          `}
        >
          {isSidebarOpen ? <PanelLeftClose size={17} /> : <PanelLeft size={17} />}
        </button>

        {/* Messages */}
        <div
          ref={messagesContainerRef}
          className="flex-1 overflow-y-auto"
          onScroll={handleScroll}
        >
          <div className="max-w-[800px] mx-auto px-6 py-6">
            {/* Welcome — vertically centered */}
            {messages.length === 1 && (
              <div className="flex flex-col items-center justify-center min-h-[60vh] animate-fade-in-up">
                <div className="text-center mb-10">
                  <h2 className={`text-[28px] font-bold mb-2 tracking-tight ${theme === 'owner' ? 'text-gradient-owner' : 'text-gradient-merchant'}`}>
                    {userType === 'c_end' ? '您好，我是小洞' : '您好，我是洞掌柜'}
                  </h2>
                  <p className="text-slate-400 text-[15px] font-light">
                    {userType === 'c_end' ? '您的专属装修顾问' : '您的专属经营助手'}
                  </p>
                </div>

                <div className="flex flex-wrap justify-center gap-2 max-w-md">
                  {currentConfig.quickActions.map((action, idx) => (
                    <button
                      key={idx}
                      onClick={() => !isLoading && sendMessage(action.prompt)}
                      disabled={isLoading}
                      className={`
                        inline-flex items-center gap-2 px-4 py-2 rounded-full text-[13px] font-medium
                        bg-white shadow-soft hover:shadow-float-md border border-slate-100/60
                        transition-all duration-200 hover:-translate-y-px
                        animate-slide-up-fade
                        ${theme === 'owner' ? 'text-slate-600 hover:text-owner-600 hover:border-owner-100' : 'text-slate-600 hover:text-merchant-600 hover:border-merchant-100'}
                      `}
                      style={{ animationDelay: `${idx * 60 + 100}ms` }}
                    >
                      <action.icon size={14} className={theme === 'owner' ? 'text-owner-400' : 'text-merchant-400'} />
                      {action.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Message List */}
            {messages.map((msg, idx) => {
              const prevMsg = idx > 0 ? messages[idx - 1] : null;
              const sameRole = prevMsg && prevMsg.role === msg.role;
              const spacing = sameRole ? 'mt-1.5' : 'mt-8';
              const isFirst = idx === 0;

              return (
                <div
                  key={msg.id || `msg-${idx}`}
                  className={`${isFirst ? '' : spacing} animate-message-in`}
                >
                  {msg.role === 'user' ? (
                    /* 用户消息 — 右对齐药丸 + hover 操作栏 */
                    <div className="flex justify-end pl-12 group/user">
                      {editingMsgIdx === idx ? (
                        /* 编辑态 */
                        <div className="w-full max-w-[75%]">
                          <textarea
                            ref={editTextareaRef}
                            value={editingContent}
                            onChange={(e) => setEditingContent(e.target.value)}
                            className={`w-full p-3 rounded-[20px] border-2 text-[0.9375rem] leading-relaxed resize-none focus:outline-none ${
                              theme === 'owner' ? 'border-owner-300 focus:border-owner-500' : 'border-merchant-300 focus:border-merchant-500'
                            }`}
                            rows={1}
                            style={{ minHeight: '48px', maxHeight: '240px', overflow: 'auto' }}
                            autoFocus
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                submitEdit(idx);
                              }
                              if (e.key === 'Escape') cancelEdit();
                            }}
                          />
                          <div className="flex justify-end gap-2 mt-2">
                            <button
                              onClick={cancelEdit}
                              className="px-3 py-1.5 text-[13px] text-slate-500 hover:bg-slate-100 rounded-lg transition-colors"
                            >
                              取消
                            </button>
                            <button
                              onClick={() => submitEdit(idx)}
                              disabled={!editingContent.trim()}
                              className={`px-3 py-1.5 text-[13px] text-white rounded-lg transition-colors disabled:opacity-50 ${
                                theme === 'owner' ? 'bg-owner-500 hover:bg-owner-600' : 'bg-merchant-500 hover:bg-merchant-600'
                              }`}
                            >
                              重新发送
                            </button>
                          </div>
                        </div>
                      ) : (
                        /* 正常态 */
                        <div className="relative inline-flex flex-col items-end max-w-[75%]">
                          {/* hover 操作栏 — 气泡左侧 */}
                          <div className="absolute -left-16 top-1/2 -translate-y-1/2 flex items-center gap-0.5 opacity-0 group-hover/user:opacity-100 transition-opacity duration-150">
                            <button
                              onClick={() => startEdit(idx, msg.content)}
                              className="p-1.5 rounded-md text-slate-300 hover:text-slate-500 hover:bg-slate-100 transition-colors"
                              title="编辑"
                            >
                              <Pencil size={14} />
                            </button>
                            <button
                              onClick={() => copyToClipboard(msg.content, `user-${idx}`)}
                              className="p-1.5 rounded-md text-slate-300 hover:text-slate-500 hover:bg-slate-100 transition-colors"
                              title="复制"
                            >
                              {copiedId === `user-${idx}` ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
                            </button>
                          </div>
                          <div className={theme === 'owner' ? 'message-user-pill-inner' : 'message-user-pill-merchant-inner'}>
                            {msg.image && (
                              <img
                                src={msg.image}
                                alt="用户上传的图片"
                                className="max-w-full max-h-60 rounded-xl mb-2"
                              />
                            )}
                            <div className="whitespace-pre-wrap">{msg.content}</div>
                          </div>
                          {msg.timestamp && (
                            <div className="text-[10px] text-slate-300 mt-1 pr-1" title={new Date(msg.timestamp).toLocaleString('zh-CN')}>
                              {formatRelativeTime(msg.timestamp)}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    /* 助手消息 — 头像 + 纯排版 + 底部工具栏 */
                    <div className="flex gap-3 pr-12">
                      {/* Avatar — only on role switch */}
                      {!sameRole ? (
                        <div className="flex-shrink-0 mt-0.5">
                          <div className="w-7 h-7 rounded-lg overflow-hidden bg-white shadow-soft ring-1 ring-slate-100">
                            <img
                              src="/logo.png"
                              alt="助手"
                              className="w-full h-full object-contain p-px"
                            />
                          </div>
                        </div>
                      ) : (
                        <div className="w-7 flex-shrink-0" />
                      )}
                      <div className="message-assistant-flow flex-1 min-w-0">
                      {msg.expertInfo && (
                        <ExpertDebugBlock
                          expertInfo={msg.expertInfo}
                          msgId={msg.id}
                          isExpanded={expandedExpert[msg.id]}
                          onToggle={toggleExpert}
                        />
                      )}

                      {msg.thinking && (
                        <ThinkingBlock
                          thinking={msg.thinking}
                          msgId={msg.id}
                          isExpanded={expandedThinking[msg.id]}
                          onToggle={toggleThinking}
                        />
                      )}

                      {msg.content || (msg.structuredBlocks && msg.structuredBlocks.length > 0) ? (
                        <>
                          {msg.content && (
                            <ReactMarkdown
                              className="prose-chat"
                              remarkPlugins={[remarkGfm]}
                              rehypePlugins={[rehypeRaw]}
                              components={markdownComponents}
                            >
                              {processContent(msg.content)}
                            </ReactMarkdown>
                          )}
                          {msg.structuredBlocks && msg.structuredBlocks.map((block) => (
                            <StructuredDataRenderer
                              key={block.id}
                              type={block.type}
                              data={block.data}
                              onAction={(item) => {
                                if (block.type === 'quick_replies' && item?.text) {
                                  sendMessage(item.text);
                                }
                              }}
                            />
                          ))}

                          {/* AI 回答底部工具栏 — 仅完成后显示 */}
                          {msg.isComplete && msg.id && (
                            <div className="flex items-center gap-1 mt-3 -ml-1">
                              {/* 复制 */}
                              <button
                                onClick={() => copyToClipboard(msg.content, `ai-${msg.id}`)}
                                className="p-1.5 rounded-md text-slate-300 hover:text-slate-500 hover:bg-slate-100 transition-colors"
                                title="复制回答"
                              >
                                {copiedId === `ai-${msg.id}` ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
                              </button>
                              {/* 重新回答 */}
                              <button
                                onClick={() => regenerateAnswer(idx)}
                                disabled={isLoading}
                                className="p-1.5 rounded-md text-slate-300 hover:text-slate-500 hover:bg-slate-100 transition-colors disabled:opacity-30"
                                title="重新回答"
                              >
                                <RefreshCw size={14} />
                              </button>
                              {/* 分隔线 */}
                              <div className="w-px h-3.5 bg-slate-150 mx-0.5" />
                              {/* 点赞 */}
                              <button
                                onClick={() => rateFeedback(msg.id, 'good')}
                                className={`p-1.5 rounded-md transition-colors ${
                                  msg.feedback === 'good'
                                    ? (theme === 'owner' ? 'text-owner-500 bg-owner-50' : 'text-merchant-500 bg-merchant-50')
                                    : 'text-slate-300 hover:text-slate-500 hover:bg-slate-100'
                                }`}
                                title="有帮助"
                              >
                                <ThumbsUp size={14} />
                              </button>
                              {/* 点踩 */}
                              <div className="relative">
                                <button
                                  onClick={() => rateFeedback(msg.id, 'bad')}
                                  className={`p-1.5 rounded-md transition-colors ${
                                    msg.feedback === 'bad'
                                      ? 'text-red-500 bg-red-50'
                                      : 'text-slate-300 hover:text-slate-500 hover:bg-slate-100'
                                  }`}
                                  title="没帮助"
                                >
                                  <ThumbsDown size={14} />
                                </button>
                                {/* 点踩反馈浮层 */}
                                {feedbackPopoverId === msg.id && !msg.feedbackReason && (
                                  <div className="absolute bottom-full left-0 mb-2 bg-white rounded-xl shadow-float-lg border border-slate-100 p-2 z-50 animate-scale-in min-w-[160px]">
                                    <p className="text-[11px] text-slate-400 px-2 py-1">请告诉我们原因：</p>
                                    {['不准确', '不实用', '不够详细', '其他'].map(reason => (
                                      <button
                                        key={reason}
                                        onClick={() => rateFeedbackWithReason(msg.id, reason)}
                                        className="w-full text-left px-2 py-1.5 text-[13px] text-slate-600 hover:bg-slate-50 rounded-lg transition-colors"
                                      >
                                        {reason}
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </div>
                            </div>
                          )}
                        </>
                      ) : (
                        <TypingIndicator />
                      )}
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
            <div ref={messagesEndRef} />
          </div>
        </div>

        {/* 滚动到底部按钮 */}
        {showScrollBtn && (
          <button
            onClick={scrollToBottom}
            className={`
              absolute bottom-28 right-6 p-2.5 rounded-full bg-white shadow-float-md
              border border-slate-100 text-slate-400 hover:text-slate-600
              transition-all duration-200 z-10 animate-fade-in
              hover:shadow-float-lg hover:-translate-y-0.5
            `}
          >
            <ChevronDown size={18} />
          </button>
        )}

        {/* Input area */}
        <div className="px-4 pb-4 pt-2 safe-area-bottom">
          <div className="max-w-[800px] mx-auto">
            <div className={`input-floating ${theme === 'merchant' ? 'merchant' : ''} px-1 py-1`}>
              {/* Image preview */}
              {imagePreview && (
                <div className="px-3 pt-1 pb-1.5">
                  <div className="relative inline-block">
                    <img
                      src={imagePreview}
                      alt="预览"
                      className="max-h-24 rounded-lg"
                    />
                    <button
                      onClick={clearSelectedImage}
                      className="absolute -top-1.5 -right-1.5 w-5 h-5 bg-slate-700/90 text-white rounded-full flex items-center justify-center hover:bg-slate-900 transition-colors shadow-sm"
                    >
                      <X size={11} />
                    </button>
                  </div>
                </div>
              )}

              {/* Input */}
              <div className="flex items-end gap-2 px-3 py-1">
                <textarea
                  ref={inputRef}
                  value={input}
                  onChange={(e) => {
                    setInput(e.target.value);
                    autoResize(e.target, 160);
                  }}
                  onKeyDown={(e) => {
                    const sendWithEnter = settings.sendKey === 'enter';
                    if (sendWithEnter && e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      sendMessage();
                    } else if (!sendWithEnter && e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                      e.preventDefault();
                      sendMessage();
                    }
                  }}
                  placeholder={selectedImage ? '描述一下这张图片...' : (userType === 'c_end' ? '问问装修的事...' : '问问经营的事...')}
                  className="flex-1 resize-none bg-transparent border-none focus:ring-0 focus:outline-none text-slate-700 placeholder-slate-400 text-[15px] leading-relaxed overflow-auto"
                  rows={1}
                  style={{ minHeight: '38px', maxHeight: '160px' }}
                />
                {isLoading ? (
                  /* 停止生成按钮 */
                  <button
                    onClick={stopGeneration}
                    className={`
                      p-2 rounded-full transition-all duration-200 flex-shrink-0 mb-0.5
                      bg-slate-700 text-white hover:bg-slate-800 shadow-soft scale-100
                    `}
                    title="停止生成"
                  >
                    <Square size={15} fill="currentColor" />
                  </button>
                ) : (
                  /* 发送按钮 */
                  <button
                    onClick={() => sendMessage()}
                    disabled={!input.trim() && !selectedImage}
                    className={`
                      p-2 rounded-full transition-all duration-200 flex-shrink-0 mb-0.5
                      ${(input.trim() || selectedImage)
                        ? (theme === 'owner'
                          ? 'bg-owner-500 text-white hover:bg-owner-600 shadow-soft hover:shadow-glow-owner scale-100'
                          : 'bg-merchant-500 text-white hover:bg-merchant-600 shadow-soft hover:shadow-glow-merchant scale-100')
                        : 'bg-slate-100 text-slate-300 scale-95'
                      }
                    `}
                  >
                    <Send size={17} />
                  </button>
                )}
              </div>

              {/* Toolbar */}
              <div className="flex items-center gap-0.5 px-3 pb-1 pt-0.5">
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleImageSelect}
                  accept="image/*"
                  className="hidden"
                />
                <div className="tooltip-trigger relative">
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={isLoading}
                    className={`
                      p-1.5 rounded-md transition-all duration-150
                      ${selectedImage
                        ? (theme === 'owner' ? 'bg-owner-50 text-owner-500' : 'bg-merchant-50 text-merchant-500')
                        : 'text-slate-350 hover:bg-slate-50 hover:text-slate-500'
                      }
                      ${isLoading ? 'opacity-40 cursor-not-allowed' : ''}
                    `}
                  >
                    <ImagePlus size={15} />
                  </button>
                  <div className="tooltip -top-8 left-1/2 -translate-x-1/2">上传图片</div>
                </div>
                <div className="tooltip-trigger relative">
                  <button
                    onClick={() => setEnableSearch(!enableSearch)}
                    className={`
                      p-1.5 rounded-md transition-all duration-150
                      ${enableSearch
                        ? (theme === 'owner' ? 'bg-owner-50 text-owner-500' : 'bg-merchant-50 text-merchant-500')
                        : 'text-slate-350 hover:bg-slate-50 hover:text-slate-500'
                      }
                    `}
                  >
                    <Search size={15} />
                  </button>
                  <div className="tooltip -top-8 left-1/2 -translate-x-1/2">联网搜索</div>
                </div>
                <div className="tooltip-trigger relative">
                  <button
                    onClick={() => setShowThinking(!showThinking)}
                    className={`
                      p-1.5 rounded-md transition-all duration-150
                      ${showThinking ? 'bg-thinking-50 text-thinking-500' : 'text-slate-350 hover:bg-slate-50 hover:text-slate-500'}
                    `}
                  >
                    <Brain size={15} />
                  </button>
                  <div className="tooltip -top-8 left-1/2 -translate-x-1/2">深度思考</div>
                </div>
                {isUploadingImage && (
                  <span className="text-[10px] text-slate-400 ml-1.5 flex items-center gap-1">
                    <Loader2 size={11} className="animate-spin" />
                    上传中
                  </span>
                )}
              </div>
            </div>

            <p className="text-center text-[10px] text-slate-300 mt-2 select-none">
              DecoPilot · 洞居智能装修助手
            </p>
          </div>
        </div>
      </main>

      {/* ===== 设置面板抽屉 ===== */}
      {showSettings && (
        <>
          <div
            className="fixed inset-0 bg-black/20 backdrop-blur-sm z-[60] animate-fade-in"
            onClick={() => setShowSettings(false)}
          />
          <div className="fixed top-0 right-0 bottom-0 w-[360px] max-w-[90vw] bg-white shadow-soft-xl z-[61] flex flex-col animate-slide-in-right">
            {/* 头部 */}
            <div className="h-14 px-5 flex items-center justify-between border-b border-slate-100">
              <h2 className="font-semibold text-[15px] text-slate-800">设置</h2>
              <button
                onClick={() => setShowSettings(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors"
              >
                <X size={18} />
              </button>
            </div>

            {/* 内容 */}
            <div className="flex-1 overflow-y-auto p-5 space-y-6">
              {/* 对话设置 */}
              <div>
                <h3 className="text-[13px] font-semibold text-slate-500 uppercase tracking-wider mb-3">对话设置</h3>
                <div className="space-y-3">
                  {/* 联网搜索 */}
                  <div className="flex items-center justify-between py-2">
                    <div className="flex items-center gap-2.5">
                      <Search size={16} className="text-slate-400" />
                      <div>
                        <div className="text-[13px] font-medium text-slate-700">联网搜索</div>
                        <div className="text-[11px] text-slate-400">搜索互联网获取最新信息</div>
                      </div>
                    </div>
                    <button
                      onClick={() => setEnableSearch(!enableSearch)}
                      className={`relative w-10 h-[22px] rounded-full transition-colors duration-200 ${
                        enableSearch
                          ? (theme === 'owner' ? 'bg-owner-500' : 'bg-merchant-500')
                          : 'bg-slate-200'
                      }`}
                    >
                      <div className={`absolute top-[2px] w-[18px] h-[18px] rounded-full bg-white shadow-sm transition-transform duration-200 ${
                        enableSearch ? 'translate-x-[20px]' : 'translate-x-[2px]'
                      }`} />
                    </button>
                  </div>
                  {/* 深度思考 */}
                  <div className="flex items-center justify-between py-2">
                    <div className="flex items-center gap-2.5">
                      <Brain size={16} className="text-slate-400" />
                      <div>
                        <div className="text-[13px] font-medium text-slate-700">深度思考</div>
                        <div className="text-[11px] text-slate-400">显示 AI 的推理过程</div>
                      </div>
                    </div>
                    <button
                      onClick={() => setShowThinking(!showThinking)}
                      className={`relative w-10 h-[22px] rounded-full transition-colors duration-200 ${
                        showThinking ? 'bg-thinking-500' : 'bg-slate-200'
                      }`}
                    >
                      <div className={`absolute top-[2px] w-[18px] h-[18px] rounded-full bg-white shadow-sm transition-transform duration-200 ${
                        showThinking ? 'translate-x-[20px]' : 'translate-x-[2px]'
                      }`} />
                    </button>
                  </div>
                  {/* 发送快捷键 */}
                  <div className="flex items-center justify-between py-2">
                    <div className="flex items-center gap-2.5">
                      <Keyboard size={16} className="text-slate-400" />
                      <div>
                        <div className="text-[13px] font-medium text-slate-700">发送快捷键</div>
                        <div className="text-[11px] text-slate-400">选择发送消息的快捷键</div>
                      </div>
                    </div>
                    <select
                      value={settings.sendKey}
                      onChange={(e) => updateSetting('sendKey', e.target.value)}
                      className="text-[13px] text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-slate-300"
                    >
                      <option value="enter">Enter</option>
                      <option value="ctrl+enter">Ctrl+Enter</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* 显示设置 */}
              <div>
                <h3 className="text-[13px] font-semibold text-slate-500 uppercase tracking-wider mb-3">显示设置</h3>
                <div className="space-y-3">
                  {/* 字体大小 */}
                  <div className="flex items-center justify-between py-2">
                    <div className="flex items-center gap-2.5">
                      <Type size={16} className="text-slate-400" />
                      <div>
                        <div className="text-[13px] font-medium text-slate-700">字体大小</div>
                        <div className="text-[11px] text-slate-400">调整聊天区域的字体大小</div>
                      </div>
                    </div>
                    <select
                      value={settings.fontSize}
                      onChange={(e) => updateSetting('fontSize', e.target.value)}
                      className="text-[13px] text-slate-600 bg-slate-50 border border-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-slate-300"
                    >
                      <option value="small">小</option>
                      <option value="medium">中</option>
                      <option value="large">大</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* 数据管理 */}
              <div>
                <h3 className="text-[13px] font-semibold text-slate-500 uppercase tracking-wider mb-3">数据管理</h3>
                <div className="space-y-2">
                  <button
                    onClick={exportCurrentChat}
                    className={`flex items-center gap-2 px-4 py-2.5 rounded-lg text-[13px] transition-colors w-full ${
                      theme === 'owner'
                        ? 'text-owner-600 bg-owner-50 hover:bg-owner-100'
                        : 'text-merchant-600 bg-merchant-50 hover:bg-merchant-100'
                    }`}
                  >
                    <Download size={15} />
                    <span>导出当前对话</span>
                  </button>
                  <button
                    onClick={clearAllHistory}
                    className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-[13px] text-red-500 bg-red-50 hover:bg-red-100 transition-colors w-full"
                  >
                    <AlertTriangle size={15} />
                    <span>清除所有对话记录</span>
                  </button>
                </div>
                <p className="text-[11px] text-slate-400 mt-2 px-1">
                  清除操作将删除所有本地保存的对话历史，不可撤销。
                </p>
              </div>

              {/* 关于 */}
              <div>
                <h3 className="text-[13px] font-semibold text-slate-500 uppercase tracking-wider mb-3">关于</h3>
                <div className="text-[13px] text-slate-500 space-y-1.5 px-1">
                  <div>DecoPilot · 洞居智能装修助手</div>
                  <div className="text-[11px] text-slate-400">版本 1.0.0</div>
                </div>
              </div>
            </div>
          </div>
        </>
      )}

      {/* ===== Toast 提示 ===== */}
      {toast && (
        <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-[70] animate-slide-up">
          <div className="px-4 py-2.5 rounded-xl bg-slate-800 text-white text-[13px] shadow-soft-lg whitespace-nowrap">
            {toast}
          </div>
        </div>
      )}

      {/* Click outside to close menus */}
      {(showUserTypeMenu || activeMenuId || feedbackPopoverId) && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => {
            setShowUserTypeMenu(false);
            setActiveMenuId(null);
            setFeedbackPopoverId(null);
          }}
        />
      )}
    </div>
  );
}

export default App;
