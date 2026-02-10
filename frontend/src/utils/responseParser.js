/**
 * DecoPilot 响应解析器
 * 处理后端流式输出的结构化数据
 */

// 输出类型枚举
export const OutputType = {
  // 基础类型
  TEXT: 'text',
  THINKING: 'thinking',
  ANSWER: 'answer',
  ERROR: 'error',

  // 结构化数据类型
  SOURCES: 'sources',
  SUBSIDY_CALC: 'subsidy_calc',
  MERCHANT_CARD: 'merchant_card',
  MERCHANT_LIST: 'merchant_list',
  PROCESS_STEPS: 'process_steps',
  TABLE: 'table',
  CHECKLIST: 'checklist',
  COMPARISON: 'comparison',

  // 交互类型
  QUICK_REPLIES: 'quick_replies',
  ACTION_BUTTONS: 'action_buttons',

  // 元数据类型
  META: 'meta',
  STREAM_START: 'stream_start',
  STREAM_END: 'stream_end',
};

/**
 * 解析单行NDJSON响应
 * @param {string} line - JSON字符串
 * @returns {Object|null} 解析后的对象
 */
export function parseLine(line) {
  if (!line || !line.trim()) return null;
  try {
    return JSON.parse(line);
  } catch (e) {
    console.warn('Failed to parse line:', line, e);
    return null;
  }
}

/**
 * 响应聚合器
 * 将流式响应聚合为完整的响应对象
 */
export class ResponseAggregator {
  constructor() {
    this.reset();
  }

  reset() {
    this.answer = '';
    this.thinking = [];
    this.sources = [];
    this.subsidyCalc = null;
    this.merchants = [];
    this.processSteps = [];
    this.tables = [];
    this.quickReplies = [];
    this.actionButtons = [];
    this.errors = [];
    this.meta = {
      sessionId: null,
      requestId: null,
      startTime: null,
      endTime: null,
      durationMs: null,
      collectionsUsed: [],
    };
  }

  /**
   * 处理单个响应块
   * @param {Object} chunk - 解析后的响应块
   * @returns {string} 处理的类型
   */
  process(chunk) {
    if (!chunk || !chunk.type) return null;

    const { type, data } = chunk;

    switch (type) {
      case OutputType.ANSWER:
        this.answer += data.content || '';
        break;

      case OutputType.THINKING:
        if (data.logs) {
          this.thinking = this.thinking.concat(data.logs);
        }
        break;

      case OutputType.SOURCES:
        if (Array.isArray(data)) {
          this.sources = this.sources.concat(data);
        }
        break;

      case OutputType.SUBSIDY_CALC:
        this.subsidyCalc = data;
        break;

      case OutputType.MERCHANT_CARD:
        this.merchants.push(data);
        break;

      case OutputType.MERCHANT_LIST:
        if (data.merchants) {
          this.merchants = this.merchants.concat(data.merchants);
        }
        break;

      case OutputType.PROCESS_STEPS:
        if (data.steps) {
          this.processSteps = data.steps;
        }
        break;

      case OutputType.TABLE:
        this.tables.push(data);
        break;

      case OutputType.QUICK_REPLIES:
        if (data.replies) {
          this.quickReplies = data.replies;
        }
        break;

      case OutputType.ACTION_BUTTONS:
        if (data.buttons) {
          this.actionButtons = data.buttons;
        }
        break;

      case OutputType.ERROR:
        this.errors.push({
          message: data.message,
          code: data.code,
        });
        break;

      case OutputType.STREAM_START:
        this.meta.sessionId = data.session_id;
        this.meta.requestId = data.request_id;
        this.meta.startTime = data.start_time;
        break;

      case OutputType.STREAM_END:
        this.meta.durationMs = data.duration_ms;
        this.meta.collectionsUsed = data.collections_used || [];
        this.meta.endTime = Date.now();
        break;
    }

    return type;
  }

  /**
   * 获取聚合后的完整响应
   * @returns {Object} 完整响应对象
   */
  getResult() {
    return {
      answer: this.answer,
      thinking: this.thinking,
      sources: this.sources,
      subsidyCalc: this.subsidyCalc,
      merchants: this.merchants,
      processSteps: this.processSteps,
      tables: this.tables,
      quickReplies: this.quickReplies,
      actionButtons: this.actionButtons,
      errors: this.errors,
      meta: this.meta,
      hasError: this.errors.length > 0,
      hasStructuredData: !!(
        this.subsidyCalc ||
        this.merchants.length > 0 ||
        this.processSteps.length > 0 ||
        this.tables.length > 0
      ),
    };
  }
}

/**
 * 流式响应处理器
 * 处理fetch的流式响应
 */
export async function* streamResponse(response) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const parsed = parseLine(line);
        if (parsed) {
          yield parsed;
        }
      }
    }

    // 处理剩余的buffer
    if (buffer) {
      const parsed = parseLine(buffer);
      if (parsed) {
        yield parsed;
      }
    }
  } finally {
    reader.releaseLock();
  }
}

/**
 * 发送聊天请求并处理流式响应
 * @param {string} endpoint - API端点
 * @param {Object} payload - 请求体
 * @param {Function} onChunk - 每个chunk的回调
 * @returns {Promise<Object>} 聚合后的响应
 */
export async function sendChatRequest(endpoint, payload, onChunk) {
  const response = await fetch(endpoint, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const aggregator = new ResponseAggregator();

  for await (const chunk of streamResponse(response)) {
    const type = aggregator.process(chunk);
    if (onChunk) {
      onChunk(chunk, type, aggregator.getResult());
    }
  }

  return aggregator.getResult();
}

// 默认导出
export default {
  OutputType,
  parseLine,
  ResponseAggregator,
  streamResponse,
  sendChatRequest,
};
