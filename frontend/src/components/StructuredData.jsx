/**
 * 结构化数据渲染组件
 * 用于渲染补贴计算、商家卡片、流程步骤等结构化数据
 */
import React from 'react';

/**
 * 补贴计算结果卡片
 */
export function SubsidyCard({ data }) {
  if (!data) return null;

  // 处理批量计算结果
  if (data.items) {
    return (
      <div className="subsidy-card batch">
        <h4>补贴计算结果</h4>
        <div className="subsidy-items">
          {data.items.map((item, index) => (
            <div key={index} className="subsidy-item">
              <span className="category">{item.category}</span>
              <span className="amount">¥{item.final_amount.toFixed(0)}</span>
              <span className="explanation">{item.explanation}</span>
            </div>
          ))}
        </div>
        <div className="subsidy-total">
          <span>总补贴</span>
          <span className="total-amount">¥{data.total_subsidy.toFixed(0)}</span>
          {data.exceeded_limit && (
            <span className="limit-warning">已达月度上限</span>
          )}
        </div>
      </div>
    );
  }

  // 单个计算结果
  return (
    <div className="subsidy-card">
      <h4>补贴计算</h4>
      <div className="subsidy-detail">
        <div className="row">
          <span>品类</span>
          <span>{data.category}</span>
        </div>
        <div className="row">
          <span>订单金额</span>
          <span>¥{data.original_amount?.toFixed(0)}</span>
        </div>
        <div className="row">
          <span>补贴比例</span>
          <span>{(data.subsidy_rate * 100).toFixed(0)}%</span>
        </div>
        <div className="row highlight">
          <span>预估补贴</span>
          <span className="amount">¥{data.final_amount?.toFixed(0)}</span>
        </div>
      </div>
      {data.explanation && (
        <div className="explanation">{data.explanation}</div>
      )}
    </div>
  );
}

/**
 * 商家卡片
 */
export function MerchantCard({ merchant }) {
  if (!merchant) return null;

  return (
    <div className="merchant-card">
      {merchant.image_url && (
        <div className="merchant-image">
          <img src={merchant.image_url} alt={merchant.name} />
        </div>
      )}
      <div className="merchant-info">
        <h4>{merchant.name}</h4>
        <div className="merchant-meta">
          <span className="category">{merchant.category}</span>
          <span className="rating">
            {'★'.repeat(Math.floor(merchant.rating))}
            {merchant.rating % 1 >= 0.5 ? '½' : ''}
            <span className="rating-num">{merchant.rating.toFixed(1)}</span>
          </span>
          <span className="reviews">{merchant.review_count}条评价</span>
        </div>
        {merchant.highlights && merchant.highlights.length > 0 && (
          <div className="highlights">
            {merchant.highlights.map((h, i) => (
              <span key={i} className="highlight-tag">{h}</span>
            ))}
          </div>
        )}
        <div className="merchant-footer">
          <span className="price-range">{merchant.price_range}</span>
          <span className="address">{merchant.address}</span>
        </div>
        {merchant.subsidy_rate && (
          <div className="subsidy-badge">
            补贴{(merchant.subsidy_rate * 100).toFixed(0)}%
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * 商家列表
 */
export function MerchantList({ data }) {
  if (!data || !data.merchants || data.merchants.length === 0) return null;

  return (
    <div className="merchant-list">
      <h4>{data.title || '推荐商家'}</h4>
      <div className="merchants">
        {data.merchants.map((merchant, index) => (
          <MerchantCard key={merchant.id || index} merchant={merchant} />
        ))}
      </div>
    </div>
  );
}

/**
 * 流程步骤
 */
export function ProcessSteps({ data }) {
  if (!data || !data.steps || data.steps.length === 0) return null;

  return (
    <div className="process-steps">
      <h4>{data.title || '流程步骤'}</h4>
      <div className="steps">
        {data.steps.map((step, index) => (
          <div
            key={index}
            className={`step ${step.status || 'pending'}`}
          >
            <div className="step-number">{step.step_number}</div>
            <div className="step-content">
              <h5>{step.title}</h5>
              <p>{step.description}</p>
              {step.duration && (
                <span className="duration">{step.duration}</span>
              )}
              {step.tips && step.tips.length > 0 && (
                <div className="tips">
                  {step.tips.map((tip, i) => (
                    <span key={i} className="tip">💡 {tip}</span>
                  ))}
                </div>
              )}
              {step.warnings && step.warnings.length > 0 && (
                <div className="warnings">
                  {step.warnings.map((warning, i) => (
                    <span key={i} className="warning">⚠️ {warning}</span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * 数据表格
 */
export function DataTable({ data }) {
  if (!data || !data.headers || !data.rows) return null;

  return (
    <div className="data-table">
      {data.title && <h4>{data.title}</h4>}
      <table>
        <thead>
          <tr>
            {data.headers.map((header, index) => (
              <th key={index}>{header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.rows.map((row, rowIndex) => (
            <tr key={rowIndex}>
              {row.map((cell, cellIndex) => (
                <td key={cellIndex}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {data.footer && <div className="table-footer">{data.footer}</div>}
    </div>
  );
}

/**
 * 引用来源
 */
export function Sources({ sources }) {
  if (!sources || sources.length === 0) return null;

  return (
    <div className="sources">
      <h5>参考来源</h5>
      <div className="source-list">
        {sources.map((source, index) => (
          <div key={index} className="source-item">
            <span className="source-title">{source.title}</span>
            <span className="source-collection">{source.collection}</span>
            {source.relevance_score > 0 && (
              <span className="relevance">
                相关度: {(source.relevance_score * 100).toFixed(0)}%
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * 快捷回复按钮
 */
export function QuickReplies({ replies, onSelect }) {
  if (!replies || replies.length === 0) return null;

  return (
    <div className="quick-replies">
      {replies.map((reply, index) => (
        <button
          key={index}
          className="quick-reply-btn"
          onClick={() => onSelect && onSelect(reply)}
        >
          {reply.text}
        </button>
      ))}
    </div>
  );
}

/**
 * 操作按钮
 */
export function ActionButtons({ buttons, onAction }) {
  if (!buttons || buttons.length === 0) return null;

  const handleClick = (button) => {
    if (onAction) {
      onAction(button);
    } else if (button.action === 'url') {
      window.open(button.value, '_blank');
    } else if (button.action === 'copy') {
      navigator.clipboard.writeText(button.value);
    }
  };

  return (
    <div className="action-buttons">
      {buttons.map((button, index) => (
        <button
          key={index}
          className={`action-btn ${button.style || 'default'}`}
          onClick={() => handleClick(button)}
        >
          {button.text}
        </button>
      ))}
    </div>
  );
}

/**
 * 思考过程展示
 */
export function ThinkingProcess({ logs, collapsed = true }) {
  const [isCollapsed, setIsCollapsed] = React.useState(collapsed);

  if (!logs || logs.length === 0) return null;

  return (
    <div className="thinking-process">
      <div
        className="thinking-header"
        onClick={() => setIsCollapsed(!isCollapsed)}
      >
        <span>🤔 思考过程</span>
        <span className="toggle">{isCollapsed ? '展开' : '收起'}</span>
      </div>
      {!isCollapsed && (
        <div className="thinking-logs">
          {logs.map((log, index) => (
            <div key={index} className="log-item">{log}</div>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * 错误提示
 */
export function ErrorMessage({ errors }) {
  if (!errors || errors.length === 0) return null;

  return (
    <div className="error-messages">
      {errors.map((error, index) => (
        <div key={index} className="error-item">
          <span className="error-icon">❌</span>
          <span className="error-text">{error.message}</span>
          {error.code && <span className="error-code">[{error.code}]</span>}
        </div>
      ))}
    </div>
  );
}

export default {
  SubsidyCard,
  MerchantCard,
  MerchantList,
  ProcessSteps,
  DataTable,
  Sources,
  QuickReplies,
  ActionButtons,
  ThinkingProcess,
  ErrorMessage,
};
