import React, { useState, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import {
  Send, Bot, User, Brain, Search, Loader2,
  Menu, Plus, MessageSquare, Settings, MoreVertical,
  PanelLeftClose, PanelLeft, Trash2, Home, Store,
  Calculator, TrendingUp, Users, FileText, Sparkles,
  ChevronDown, Gift, Building2, Zap
} from 'lucide-react';
import './index.css';

function App() {
  // User Type State
  const [userType, setUserType] = useState('c_end'); // 'c_end' or 'b_end'
  const [showUserTypeMenu, setShowUserTypeMenu] = useState(false);

  // Chat State
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [enableSearch, setEnableSearch] = useState(true);
  const [showThinking, setShowThinking] = useState(true);
  const [currentChatId, setCurrentChatId] = useState(null);

  // UI State
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [activeMenuId, setActiveMenuId] = useState(null);
  const [showToolsPanel, setShowToolsPanel] = useState(false);
  const [history, setHistory] = useState([]);

  const messagesEndRef = useRef(null);

  // User type configurations
  const userTypeConfig = {
    c_end: {
      name: '业主模式',
      icon: Home,
      color: 'blue',
      greeting: '你好！我是洞居平台的装修顾问"小洞"，很高兴为您服务。我可以帮您解答装修问题、查询补贴政策、推荐优质商家。请问有什么可以帮您的？',
      quickActions: [
        { icon: Gift, label: '查询补贴', prompt: '装修补贴怎么领取？有什么条件？' },
        { icon: Sparkles, label: '风格推荐', prompt: '现在流行什么装修风格？' },
        { icon: Calculator, label: '预算评估', prompt: '100平米的房子装修大概需要多少钱？' },
        { icon: Store, label: '商家推荐', prompt: '有什么靠谱的家具商家推荐？' },
      ]
    },
    b_end: {
      name: '商家模式',
      icon: Building2,
      color: 'emerald',
      greeting: '您好！我是洞居平台的商家助手"洞掌柜"，专门为入驻商家提供服务。我可以帮您解答入驻问题、分析经营数据、优化获客策略。请问有什么可以帮您的？',
      quickActions: [
        { icon: FileText, label: '入驻指南', prompt: '如何入驻洞居平台？需要什么条件？' },
        { icon: TrendingUp, label: 'ROI分析', prompt: '如何提高投放ROI？' },
        { icon: Users, label: '获客策略', prompt: '有什么好的获客方法？' },
        { icon: Zap, label: '话术生成', prompt: '帮我生成一段首次接触客户的话术' },
      ]
    }
  };

  const currentConfig = userTypeConfig[userType];

  // Initialize with greeting
  useEffect(() => {
    setMessages([{ role: 'assistant', content: currentConfig.greeting }]);
  }, [userType]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  useEffect(() => {
    if (currentChatId) {
      setHistory(prev => prev.map(item => {
        if (item.id === currentChatId) {
          return { ...item, messages: messages };
        }
        return item;
      }));
    }
  }, [messages, currentChatId]);

  const startNewChat = () => {
    setMessages([{ role: 'assistant', content: currentConfig.greeting }]);
    setInput('');
    setCurrentChatId(null);
    setActiveMenuId(null);
  };

  const loadChat = (chat) => {
    setCurrentChatId(chat.id);
    setMessages(chat.messages);
    if (window.innerWidth < 768) {
      setIsSidebarOpen(false);
    }
  };

  const deleteChat = (e, chatId) => {
    e.stopPropagation();
    setHistory(prev => prev.filter(item => item.id !== chatId));
    if (currentChatId === chatId) {
      startNewChat();
    }
    setActiveMenuId(null);
  };

  const createHistoryItem = (firstUserMsg, initialMessages) => {
    const newId = Date.now();
    const newItem = {
      id: newId,
      title: firstUserMsg.length > 15 ? firstUserMsg.substring(0, 15) + '...' : firstUserMsg,
      date: '刚刚',
      messages: initialMessages,
      userType: userType
    };
    setHistory(prev => [newItem, ...prev]);
    return newId;
  };

  const sendMessage = async (customMessage = null) => {
    const messageToSend = customMessage || input.trim();
    if (!messageToSend || isLoading) return;

    setInput('');

    let updatedMessages = [...messages, { role: 'user', content: messageToSend }];
    setMessages(updatedMessages);
    setIsLoading(true);

    let activeId = currentChatId;
    if (!activeId) {
      activeId = createHistoryItem(messageToSend, updatedMessages);
      setCurrentChatId(activeId);
    }

    const newMsgId = Date.now();
    const assistantMsg = { role: 'assistant', content: '', thinking: [], id: newMsgId };
    updatedMessages = [...updatedMessages, assistantMsg];
    setMessages(updatedMessages);

    try {
      // Use new API endpoint based on user type
      const endpoint = userType === 'c_end' ? '/api/v1/chat/c-end' : '/api/v1/chat/b-end';

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: messageToSend,
          session_id: `${userType}_${activeId}`,
          enable_search: enableSearch,
          show_thinking: showThinking
        })
      });

      if (!response.ok) {
        // Fallback to legacy endpoint
        const legacyResponse = await fetch('/chat_stream', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: messageToSend, enable_search: enableSearch, show_thinking: showThinking })
        });

        if (!legacyResponse.ok) {
          throw new Error(`Server error: ${legacyResponse.status}`);
        }

        await processStream(legacyResponse, newMsgId);
      } else {
        await processStream(response, newMsgId);
      }
    } catch (error) {
      console.error('Error:', error);
      setMessages(prev => prev.map(msg =>
        msg.id === newMsgId
          ? { ...msg, content: '抱歉，发生了网络错误，请稍后重试。' }
          : msg
      ));
    } finally {
      setIsLoading(false);
    }
  };

  const processStream = async (response, newMsgId) => {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (!line.trim()) continue;
        try {
          const data = JSON.parse(line);
          setMessages(prev => prev.map(msg => {
            if (msg.id !== newMsgId) return msg;
            if (data.type === 'thinking') {
              return { ...msg, thinking: [...(msg.thinking || []), ...data.content] };
            } else if (data.type === 'answer') {
              return { ...msg, content: msg.content + data.content };
            }
            return msg;
          }));
        } catch (e) { console.error("Parse error", e); }
      }
    }
  };

  const switchUserType = (type) => {
    setUserType(type);
    setShowUserTypeMenu(false);
    startNewChat();
  };

  const colorClasses = {
    blue: {
      bg: 'bg-blue-600',
      bgLight: 'bg-blue-100',
      bgLighter: 'bg-blue-50',
      text: 'text-blue-600',
      textLight: 'text-blue-700',
      ring: 'ring-blue-200',
      border: 'border-blue-200',
      hover: 'hover:bg-blue-700',
      hoverLight: 'hover:bg-blue-100',
    },
    emerald: {
      bg: 'bg-emerald-600',
      bgLight: 'bg-emerald-100',
      bgLighter: 'bg-emerald-50',
      text: 'text-emerald-600',
      textLight: 'text-emerald-700',
      ring: 'ring-emerald-200',
      border: 'border-emerald-200',
      hover: 'hover:bg-emerald-700',
      hoverLight: 'hover:bg-emerald-100',
    }
  };

  const colors = colorClasses[currentConfig.color];
  const UserTypeIcon = currentConfig.icon;

  return (
    <div className="flex h-screen bg-gradient-to-br from-gray-50 to-gray-100 text-gray-800 font-sans overflow-hidden">
      {/* Sidebar */}
      <aside
        className={`${
          isSidebarOpen ? 'w-72 translate-x-0' : 'w-0 -translate-x-full opacity-0 overflow-hidden'
        } bg-white/80 backdrop-blur-xl border-r border-gray-200/50 flex flex-col transition-all duration-300 ease-in-out shrink-0 shadow-xl`}
      >
        {/* Logo & User Type Selector */}
        <div className="p-4 border-b border-gray-100">
          <div className="flex items-center gap-3 mb-4">
            <div className={`w-10 h-10 rounded-xl ${colors.bg} flex items-center justify-center shadow-lg`}>
              <Sparkles size={20} className="text-white" />
            </div>
            <div>
              <h1 className="font-bold text-lg text-gray-800">DecoPilot</h1>
              <p className="text-xs text-gray-500">智能装修助手</p>
            </div>
          </div>

          {/* User Type Selector */}
          <div className="relative">
            <button
              onClick={() => setShowUserTypeMenu(!showUserTypeMenu)}
              className={`w-full flex items-center justify-between px-4 py-3 ${colors.bgLighter} ${colors.text} rounded-xl text-sm font-medium transition-all hover:shadow-md`}
            >
              <div className="flex items-center gap-2">
                <UserTypeIcon size={18} />
                <span>{currentConfig.name}</span>
              </div>
              <ChevronDown size={16} className={`transition-transform ${showUserTypeMenu ? 'rotate-180' : ''}`} />
            </button>

            {showUserTypeMenu && (
              <div className="absolute top-full left-0 right-0 mt-2 bg-white rounded-xl shadow-xl border border-gray-100 overflow-hidden z-20">
                <button
                  onClick={() => switchUserType('c_end')}
                  className={`w-full flex items-center gap-3 px-4 py-3 text-sm transition-colors ${userType === 'c_end' ? 'bg-blue-50 text-blue-700' : 'hover:bg-gray-50'}`}
                >
                  <Home size={18} />
                  <div className="text-left">
                    <div className="font-medium">业主模式</div>
                    <div className="text-xs text-gray-500">装修咨询、补贴查询、商家推荐</div>
                  </div>
                </button>
                <button
                  onClick={() => switchUserType('b_end')}
                  className={`w-full flex items-center gap-3 px-4 py-3 text-sm transition-colors ${userType === 'b_end' ? 'bg-emerald-50 text-emerald-700' : 'hover:bg-gray-50'}`}
                >
                  <Building2 size={18} />
                  <div className="text-left">
                    <div className="font-medium">商家模式</div>
                    <div className="text-xs text-gray-500">入驻指导、经营分析、获客策略</div>
                  </div>
                </button>
              </div>
            )}
          </div>
        </div>

        {/* New Chat Button */}
        <div className="p-4">
          <button
            onClick={startNewChat}
            className={`w-full flex items-center justify-center gap-2 px-4 py-3 ${colors.bg} ${colors.hover} text-white rounded-xl text-sm font-medium transition-all shadow-md hover:shadow-lg`}
          >
            <Plus size={18} />
            <span>新对话</span>
          </button>
        </div>

        {/* History List */}
        <div className="flex-1 overflow-y-auto px-3" onClick={() => setActiveMenuId(null)}>
          <div className="px-2 py-2 text-xs font-semibold text-gray-400 uppercase tracking-wider">历史记录</div>
          <div className="space-y-1">
            {history.filter(item => item.userType === userType).map((item) => (
              <div key={item.id} className="relative group">
                <button
                  onClick={() => loadChat(item)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 text-sm rounded-xl transition-all text-left ${
                    currentChatId === item.id
                      ? `${colors.bgLight} ${colors.textLight}`
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <MessageSquare size={16} className="shrink-0 opacity-60" />
                  <span className="truncate flex-1">{item.title}</span>
                  <div
                    onClick={(e) => {
                      e.stopPropagation();
                      setActiveMenuId(activeMenuId === item.id ? null : item.id);
                    }}
                    className="p-1.5 hover:bg-white/50 rounded-lg opacity-0 group-hover:opacity-100 transition-all"
                  >
                    <MoreVertical size={14} className="text-gray-400" />
                  </div>
                </button>

                {activeMenuId === item.id && (
                  <div className="absolute right-2 top-10 z-10 bg-white shadow-xl rounded-xl border border-gray-100 py-1 w-32">
                    <button
                      onClick={(e) => deleteChat(e, item.id)}
                      className="w-full flex items-center gap-2 px-3 py-2 text-xs text-red-600 hover:bg-red-50 transition-colors"
                    >
                      <Trash2 size={14} />
                      删除对话
                    </button>
                  </div>
                )}
              </div>
            ))}
            {history.filter(item => item.userType === userType).length === 0 && (
              <div className="text-center py-8 text-gray-400 text-sm">
                暂无历史记录
              </div>
            )}
          </div>
        </div>

        {/* Settings */}
        <div className="p-3 border-t border-gray-100">
          <button className="w-full flex items-center gap-3 px-3 py-2.5 text-sm hover:bg-gray-100 rounded-xl transition-colors text-gray-600">
            <Settings size={18} />
            <span>设置</span>
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col h-full relative min-w-0">
        {/* Top Navigation Bar */}
        <header className="h-16 flex items-center justify-between px-4 bg-white/50 backdrop-blur-sm border-b border-gray-100 shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="p-2.5 hover:bg-gray-100 rounded-xl text-gray-500 transition-colors"
            >
              {isSidebarOpen ? <PanelLeftClose size={20} /> : <PanelLeft size={20} />}
            </button>
            <div className="flex items-center gap-2">
              <UserTypeIcon size={20} className={colors.text} />
              <span className="font-semibold text-gray-700">{currentConfig.name}</span>
            </div>
          </div>
          <div className={`px-3 py-1.5 ${colors.bgLighter} ${colors.text} rounded-full text-xs font-medium`}>
            在线
          </div>
        </header>

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto p-4 md:px-8 lg:px-16 pb-48 w-full max-w-4xl mx-auto space-y-6">
          {messages.length === 1 && (
            /* Welcome Screen with Quick Actions */
            <div className="mt-8">
              <div className="text-center mb-8">
                <div className={`w-20 h-20 ${colors.bg} rounded-2xl flex items-center justify-center mx-auto mb-4 shadow-xl`}>
                  <Bot size={40} className="text-white" />
                </div>
                <h2 className="text-2xl font-bold text-gray-800 mb-2">
                  {userType === 'c_end' ? '您好，我是小洞' : '您好，我是洞掌柜'}
                </h2>
                <p className="text-gray-500 max-w-md mx-auto">
                  {userType === 'c_end'
                    ? '您的专属装修顾问，帮您解答装修问题、查询补贴、推荐商家'
                    : '您的专属经营助手，帮您分析数据、优化获客、提升业绩'}
                </p>
              </div>

              <div className="grid grid-cols-2 gap-3 max-w-lg mx-auto">
                {currentConfig.quickActions.map((action, idx) => (
                  <button
                    key={idx}
                    onClick={() => sendMessage(action.prompt)}
                    className={`flex items-center gap-3 p-4 bg-white rounded-xl border border-gray-200 hover:border-gray-300 hover:shadow-md transition-all text-left group`}
                  >
                    <div className={`p-2 ${colors.bgLighter} rounded-lg ${colors.text} group-hover:scale-110 transition-transform`}>
                      <action.icon size={20} />
                    </div>
                    <span className="text-sm font-medium text-gray-700">{action.label}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, idx) => (
            <div key={idx} className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              {msg.role === 'assistant' && (
                <div className={`w-10 h-10 rounded-xl ${colors.bgLight} flex items-center justify-center shrink-0 mt-1 shadow-sm`}>
                  <Bot size={20} className={colors.text} />
                </div>
              )}

              <div className={`flex flex-col max-w-[85%] md:max-w-[75%] space-y-2 ${msg.role === 'user' ? 'items-end' : 'items-start'}`}>
                {msg.thinking && msg.thinking.length > 0 && (
                  <div className="w-full bg-white rounded-xl p-4 text-sm border border-gray-100 shadow-sm">
                    <details className="group">
                      <summary className="flex items-center gap-2 cursor-pointer text-gray-500 hover:text-gray-700 font-medium list-none select-none">
                        <Brain size={16} className="text-purple-500" />
                        <span>思考过程 ({msg.thinking.length})</span>
                        <span className="ml-auto text-xs opacity-0 group-hover:opacity-100 transition-opacity">展开</span>
                      </summary>
                      <div className="mt-3 text-gray-600 font-mono text-xs whitespace-pre-wrap pl-3 border-l-2 border-purple-200 py-1 space-y-1">
                        {msg.thinking.map((log, i) => <div key={i}>{log}</div>)}
                      </div>
                    </details>
                  </div>
                )}

                <div className={`p-4 rounded-2xl shadow-sm text-base leading-relaxed ${
                  msg.role === 'user'
                    ? `${colors.bg} text-white rounded-br-sm`
                    : 'bg-white border border-gray-100 rounded-bl-sm'
                }`}>
                  {msg.role === 'assistant'
                    ? <ReactMarkdown className="prose prose-sm max-w-none prose-p:my-2 prose-ul:my-2 prose-li:my-0.5">{msg.content || '...'}</ReactMarkdown>
                    : <div className="whitespace-pre-wrap">{msg.content}</div>
                  }
                </div>
              </div>

              {msg.role === 'user' && (
                <div className="w-10 h-10 rounded-xl bg-gray-200 flex items-center justify-center shrink-0 mt-1 shadow-sm">
                  <User size={20} className="text-gray-600" />
                </div>
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-gray-100 via-gray-100 to-transparent pt-8 pb-6">
          <div className="w-full max-w-3xl mx-auto px-4">
            <div className="bg-white rounded-2xl shadow-xl border border-gray-200 overflow-hidden">
              {/* Toolbar */}
              <div className="flex gap-2 px-4 pt-3 pb-2 border-b border-gray-100">
                <button
                  onClick={() => setEnableSearch(!enableSearch)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    enableSearch
                      ? 'bg-blue-100 text-blue-700'
                      : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                  }`}
                >
                  <Search size={14} />
                  联网搜索
                </button>
                <button
                  onClick={() => setShowThinking(!showThinking)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
                    showThinking
                      ? 'bg-purple-100 text-purple-700'
                      : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
                  }`}
                >
                  <Brain size={14} />
                  深度思考
                </button>
              </div>

              {/* Input */}
              <div className="flex items-end gap-3 p-3">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && (e.preventDefault(), sendMessage())}
                  placeholder={userType === 'c_end' ? '问问装修的事...' : '问问经营的事...'}
                  className="w-full max-h-32 p-2 bg-transparent border-none resize-none focus:ring-0 text-gray-800 placeholder-gray-400 text-base"
                  rows={1}
                  style={{ minHeight: '44px' }}
                />
                <button
                  onClick={() => sendMessage()}
                  disabled={isLoading || !input.trim()}
                  className={`p-3 rounded-xl transition-all flex items-center justify-center shrink-0 ${
                    input.trim()
                      ? `${colors.bg} text-white ${colors.hover} shadow-lg hover:shadow-xl transform hover:scale-105`
                      : 'bg-gray-100 text-gray-400 cursor-not-allowed'
                  }`}
                >
                  {isLoading ? <Loader2 size={20} className="animate-spin" /> : <Send size={20} />}
                </button>
              </div>
            </div>
            <div className="text-center mt-3 text-xs text-gray-400">
              DecoPilot · 洞居智能装修助手
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
