/**
 * 结构化数据渲染组件 — 无边框软化版
 * 移除 border，改用 bg 背景对比 + 柔和阴影
 */
import React, { useState } from 'react';
import {
  Calculator, Store, ListChecks, Table, Quote,
  AlertCircle, Brain, TrendingUp, CheckCircle, XCircle,
  ArrowRight, Clock, DollarSign, BarChart3, Lightbulb,
  ChevronDown, Star, MapPin, Tag
} from 'lucide-react';

// 通用卡片容器 — 无边框，背景对比
const Card = ({ children, className = '', gradient = false, color = 'slate' }) => {
  const gradients = {
    owner: 'bg-gradient-to-br from-owner-50/60 to-white',
    merchant: 'bg-gradient-to-br from-merchant-50/60 to-white',
    thinking: 'bg-gradient-to-br from-thinking-50/60 to-white',
    slate: 'bg-slate-50/80',
  };

  return (
    <div className={`
      rounded-2xl shadow-float my-4 overflow-hidden
      ${gradient ? gradients[color] : 'bg-slate-50/80'}
      ${className}
    `}>
      {children}
    </div>
  );
};

// 卡片头部 — 更轻量，无底部边线
const CardHeader = ({ icon: Icon, title, badge, color = 'owner' }) => {
  const colors = {
    owner: 'text-owner-500',
    merchant: 'text-merchant-500',
    thinking: 'text-thinking-500',
  };

  return (
    <div className="flex items-center justify-between px-5 py-4">
      <div className="flex items-center gap-2.5">
        <Icon size={18} className={colors[color]} />
        <h4 className="font-semibold text-slate-700 text-sm">{title}</h4>
      </div>
      {badge}
    </div>
  );
};

/**
 * 补贴计算结果卡片
 */
export function SubsidyCard({ data }) {
  if (!data) return null;

  if (data.items) {
    return (
      <Card gradient color="owner" className="animate-fade-in-up">
        <CardHeader icon={Calculator} title="补贴计算结果" color="owner" />
        <div className="px-5 pb-5">
          <div className="space-y-2">
            {data.items.map((item, index) => (
              <div
                key={index}
                className="flex justify-between items-center bg-white/80 rounded-xl p-4 hover:bg-white transition-all duration-200"
              >
                <span className="text-slate-600 text-sm">{item.category}</span>
                <span className="font-semibold text-owner-600 text-lg">¥{item.final_amount.toFixed(0)}</span>
              </div>
            ))}
          </div>
          <div className="mt-5 pt-5 border-t border-slate-100/60 flex justify-between items-center">
            <span className="font-medium text-slate-600 text-sm">总补贴金额</span>
            <div className="flex items-center gap-3">
              <span className="text-3xl font-bold text-owner-600">¥{data.total_subsidy.toFixed(0)}</span>
              {data.exceeded_limit && (
                <span className="badge bg-orange-100 text-orange-600">已达上限</span>
              )}
            </div>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card gradient color="owner" className="animate-fade-in-up">
      <CardHeader icon={Calculator} title="补贴计算" color="owner" />
      <div className="px-5 pb-5">
        <div className="grid grid-cols-2 gap-3">
          <div className="bg-white/80 rounded-xl p-4">
            <span className="text-2xs text-slate-400 uppercase tracking-wide">品类</span>
            <p className="font-medium text-slate-700 mt-1 text-sm">{data.category}</p>
          </div>
          <div className="bg-white/80 rounded-xl p-4">
            <span className="text-2xs text-slate-400 uppercase tracking-wide">订单金额</span>
            <p className="font-medium text-slate-700 mt-1 text-sm">¥{data.original_amount?.toFixed(0)}</p>
          </div>
          <div className="bg-white/80 rounded-xl p-4">
            <span className="text-2xs text-slate-400 uppercase tracking-wide">补贴比例</span>
            <p className="font-medium text-slate-700 mt-1 text-sm">{(data.subsidy_rate * 100).toFixed(0)}%</p>
          </div>
          <div className="bg-owner-50/80 rounded-xl p-4">
            <span className="text-2xs text-owner-500 uppercase tracking-wide">预估补贴</span>
            <p className="font-bold text-owner-600 text-xl mt-1">¥{data.final_amount?.toFixed(0)}</p>
          </div>
        </div>
        {data.explanation && (
          <div className="mt-4 flex items-start gap-2 p-4 bg-amber-50/60 rounded-xl">
            <Lightbulb size={16} className="text-amber-400 flex-shrink-0 mt-0.5" />
            <p className="text-sm text-amber-700">{data.explanation}</p>
          </div>
        )}
      </div>
    </Card>
  );
}

/**
 * ROI 分析卡片
 */
export function ROICard({ data }) {
  if (!data) return null;

  const getAssessmentStyle = (level) => {
    const styles = {
      '优秀': 'bg-green-100/80 text-green-700',
      '良好': 'bg-owner-100/80 text-owner-700',
      '一般': 'bg-amber-100/80 text-amber-700',
      '较低': 'bg-orange-100/80 text-orange-700',
      '亏损': 'bg-red-100/80 text-red-700',
    };
    return styles[level] || 'bg-slate-100 text-slate-700';
  };

  return (
    <Card gradient color="merchant" className="animate-fade-in-up">
      <CardHeader
        icon={TrendingUp}
        title="ROI 分析"
        color="merchant"
        badge={data.assessment && (
          <span className={`badge ${getAssessmentStyle(data.assessment.level)}`}>
            {data.assessment.level}
          </span>
        )}
      />
      <div className="px-5 pb-5">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-5">
          {[
            { icon: DollarSign, label: '投入', value: `¥${data.investment?.toLocaleString()}` },
            { icon: BarChart3, label: '收入', value: `¥${data.revenue?.toLocaleString()}` },
            { icon: TrendingUp, label: 'ROI', value: `${data.roi_percentage?.toFixed(1)}%`, highlight: true },
            { icon: Clock, label: '回本周期', value: typeof data.payback_days === 'number' ? `${data.payback_days}天` : data.payback_days },
          ].map((item, idx) => (
            <div key={idx} className="bg-white/80 rounded-xl p-4 text-center hover:bg-white transition-all">
              <item.icon size={18} className={`mx-auto mb-2 ${item.highlight ? 'text-merchant-500' : 'text-slate-400'}`} />
              <p className="text-2xs text-slate-400 mb-1">{item.label}</p>
              <p className={`font-bold ${item.highlight ? (data.roi_percentage >= 0 ? 'text-merchant-600 text-lg' : 'text-red-600 text-lg') : 'text-slate-700'}`}>
                {item.value}
              </p>
            </div>
          ))}
        </div>

        {data.assessment?.description && (
          <div className="bg-white/80 rounded-xl p-4 mb-4">
            <p className="text-sm text-slate-600">{data.assessment.description}</p>
          </div>
        )}

        {data.suggestions?.length > 0 && (
          <div className="bg-white/80 rounded-xl p-4">
            <p className="text-sm font-medium text-slate-600 mb-3">优化建议</p>
            <div className="space-y-2">
              {data.suggestions.map((suggestion, idx) => (
                <div key={idx} className="flex items-start gap-2">
                  <Lightbulb size={14} className="text-amber-400 flex-shrink-0 mt-1" />
                  <p className="text-sm text-slate-500">{suggestion}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

/**
 * 对比卡片
 */
export function ComparisonCard({ data }) {
  if (!data?.items?.length) return null;

  return (
    <Card className="animate-fade-in-up">
      {data.title && <CardHeader icon={Table} title={data.title} />}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-slate-100/40">
              <th className="px-5 py-3 text-left text-sm font-medium text-slate-500">对比项</th>
              {data.items.map((item, idx) => (
                <th key={idx} className="px-5 py-3 text-center text-sm font-medium text-slate-700">
                  {item.name}
                  {item.recommended && (
                    <span className="ml-2 badge-owner">推荐</span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.criteria?.map((criterion, rowIdx) => (
              <tr key={rowIdx} className="border-t border-slate-100/40 hover:bg-white/60 transition-colors">
                <td className="px-5 py-3 text-sm text-slate-500">{criterion}</td>
                {data.items.map((item, colIdx) => (
                  <td key={colIdx} className="px-5 py-3 text-sm text-center text-slate-600">
                    {item.values?.[rowIdx] || '-'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.conclusion && (
        <div className="px-5 py-4 bg-owner-50/40 flex items-start gap-2">
          <Lightbulb size={16} className="text-owner-400 flex-shrink-0 mt-0.5" />
          <p className="text-sm text-owner-600">{data.conclusion}</p>
        </div>
      )}
    </Card>
  );
}

/**
 * 清单组件
 */
export function Checklist({ data }) {
  if (!data?.items?.length) return null;

  return (
    <Card className="animate-fade-in-up">
      {data.title && <CardHeader icon={ListChecks} title={data.title} />}
      <div className="px-5 pb-5 space-y-2">
        {data.items.map((item, idx) => (
          <div
            key={idx}
            className={`flex items-start gap-3 p-4 rounded-xl transition-all ${
              item.checked ? 'bg-green-50/60' : 'bg-white/60'
            }`}
          >
            {item.checked ? (
              <CheckCircle size={18} className="text-green-500 flex-shrink-0 mt-0.5" />
            ) : (
              <div className="w-[18px] h-[18px] rounded-full border-2 border-slate-200 flex-shrink-0 mt-0.5" />
            )}
            <div className="flex-1 min-w-0">
              <p className={`text-sm ${item.checked ? 'text-green-700' : 'text-slate-600'}`}>{item.text}</p>
              {item.note && <p className="text-xs text-slate-400 mt-1">{item.note}</p>}
            </div>
            {item.priority && (
              <span className={`badge ${
                item.priority === 'high' ? 'bg-red-100/80 text-red-600' :
                item.priority === 'medium' ? 'bg-amber-100/80 text-amber-600' :
                'bg-slate-100 text-slate-500'
              }`}>
                {item.priority === 'high' ? '重要' : item.priority === 'medium' ? '一般' : '可选'}
              </span>
            )}
          </div>
        ))}
      </div>
      {data.progress !== undefined && (
        <div className="px-5 pb-5">
          <div className="flex justify-between text-sm text-slate-500 mb-2">
            <span>完成进度</span>
            <span className="font-medium">{data.progress}%</span>
          </div>
          <div className="h-1.5 bg-slate-200/60 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-owner-500 to-owner-400 rounded-full transition-all duration-500"
              style={{ width: `${data.progress}%` }}
            />
          </div>
        </div>
      )}
    </Card>
  );
}

/**
 * 时间线组件
 */
export function Timeline({ data }) {
  if (!data?.events?.length) return null;

  return (
    <Card className="animate-fade-in-up">
      {data.title && <CardHeader icon={Clock} title={data.title} />}
      <div className="px-5 pb-5">
        <div className="relative">
          <div className="absolute left-[15px] top-0 bottom-0 w-0.5 bg-slate-200/60" />
          <div className="space-y-4">
            {data.events.map((event, idx) => (
              <div key={idx} className="relative pl-10">
                <div className={`absolute left-0 w-8 h-8 rounded-full flex items-center justify-center ${
                  event.status === 'completed' ? 'bg-green-500 text-white' :
                  event.status === 'current' ? 'bg-owner-500 text-white' :
                  'bg-slate-100 border-2 border-slate-200'
                }`}>
                  {event.status === 'completed' && <CheckCircle size={14} />}
                </div>
                <div className={`p-4 rounded-xl ${
                  event.status === 'current' ? 'bg-owner-50/60' : 'bg-white/60'
                }`}>
                  <div className="flex justify-between items-start mb-1">
                    <h5 className="font-medium text-slate-700 text-sm">{event.title}</h5>
                    {event.date && <span className="text-xs text-slate-400">{event.date}</span>}
                  </div>
                  {event.description && <p className="text-sm text-slate-500">{event.description}</p>}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </Card>
  );
}

/**
 * 商家卡片
 */
export function MerchantCard({ merchant }) {
  if (!merchant) return null;

  return (
    <div className="bg-slate-50/80 rounded-2xl p-4 shadow-float hover:shadow-float-md transition-all duration-200 animate-fade-in">
      <div className="flex gap-4">
        {merchant.image_url && (
          <div className="w-20 h-20 rounded-xl overflow-hidden flex-shrink-0 bg-slate-100">
            <img src={merchant.image_url} alt={merchant.name} className="w-full h-full object-cover" />
          </div>
        )}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <h4 className="font-semibold text-slate-700 truncate text-sm">{merchant.name}</h4>
            {merchant.subsidy_rate && (
              <span className="badge-owner flex-shrink-0">
                <Tag size={10} />
                补贴{(merchant.subsidy_rate * 100).toFixed(0)}%
              </span>
            )}
          </div>
          <div className="flex items-center gap-2 mt-1.5 text-sm">
            <span className="text-slate-400">{merchant.category}</span>
            <span className="flex items-center gap-0.5 text-amber-500">
              <Star size={12} fill="currentColor" />
              {merchant.rating?.toFixed(1)}
            </span>
            <span className="text-slate-300">{merchant.review_count}评价</span>
          </div>
          {merchant.highlights?.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {merchant.highlights.map((h, i) => (
                <span key={i} className="badge bg-slate-100/80 text-slate-500">{h}</span>
              ))}
            </div>
          )}
          <div className="flex items-center justify-between mt-2.5 text-sm">
            <span className="font-medium text-merchant-600">{merchant.price_range}</span>
            <span className="flex items-center gap-1 text-slate-400 truncate text-xs">
              <MapPin size={12} />
              {merchant.address}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * 商家列表
 */
export function MerchantList({ data }) {
  if (!data?.merchants?.length) return null;

  return (
    <div className="my-4 animate-fade-in-up">
      <div className="flex items-center gap-2.5 mb-4">
        <Store size={18} className="text-owner-500" />
        <h4 className="font-semibold text-slate-700 text-sm">{data.title || '推荐商家'}</h4>
      </div>
      <div className="space-y-3">
        {data.merchants.map((merchant, idx) => (
          <MerchantCard key={merchant.id || idx} merchant={merchant} />
        ))}
      </div>
    </div>
  );
}

/**
 * 流程步骤
 */
export function ProcessSteps({ data }) {
  if (!data?.steps?.length) return null;

  return (
    <Card className="animate-fade-in-up">
      <CardHeader icon={ListChecks} title={data.title || '流程步骤'} />
      <div className="px-5 pb-5 space-y-4">
        {data.steps.map((step, idx) => (
          <div key={idx} className={`relative pl-12 ${idx < data.steps.length - 1 ? 'pb-4' : ''}`}>
            {idx < data.steps.length - 1 && (
              <div className="absolute left-[15px] top-8 bottom-0 w-0.5 bg-slate-200/60" />
            )}
            <div className={`absolute left-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
              step.status === 'completed' ? 'bg-green-500 text-white' :
              step.status === 'current' ? 'bg-owner-500 text-white' :
              'bg-slate-100 text-slate-500'
            }`}>
              {step.status === 'completed' ? '✓' : step.step_number}
            </div>
            <div className={`p-4 rounded-xl ${
              step.status === 'current' ? 'bg-owner-50/60' : 'bg-white/60'
            }`}>
              <div className="flex items-center justify-between mb-1">
                <h5 className="font-medium text-slate-700 text-sm">{step.title}</h5>
                {step.duration && (
                  <span className="flex items-center gap-1 text-xs text-slate-400">
                    <Clock size={12} />
                    {step.duration}
                  </span>
                )}
              </div>
              <p className="text-sm text-slate-500">{step.description}</p>
              {step.tips?.length > 0 && (
                <div className="mt-3 space-y-1">
                  {step.tips.map((tip, i) => (
                    <p key={i} className="flex items-start gap-1.5 text-xs text-owner-500">
                      <Lightbulb size={12} className="flex-shrink-0 mt-0.5" />
                      {tip}
                    </p>
                  ))}
                </div>
              )}
              {step.warnings?.length > 0 && (
                <div className="mt-3 space-y-1">
                  {step.warnings.map((warning, i) => (
                    <p key={i} className="flex items-start gap-1.5 text-xs text-orange-500">
                      <AlertCircle size={12} className="flex-shrink-0 mt-0.5" />
                      {warning}
                    </p>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </Card>
  );
}

/**
 * 数据表格
 */
export function DataTable({ data }) {
  if (!data?.headers || !data?.rows) return null;

  return (
    <Card className="animate-fade-in-up">
      {data.title && <CardHeader icon={Table} title={data.title} />}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-slate-100/40">
              {data.headers.map((header, idx) => (
                <th key={idx} className="px-5 py-3 text-left text-sm font-medium text-slate-500">{header}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {data.rows.map((row, rowIdx) => (
              <tr key={rowIdx} className="border-t border-slate-100/40 hover:bg-white/60 transition-colors">
                {row.map((cell, cellIdx) => (
                  <td key={cellIdx} className="px-5 py-3 text-sm text-slate-600">{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.footer && (
        <div className="px-5 py-3 bg-slate-100/30 text-sm text-slate-400">
          {data.footer}
        </div>
      )}
    </Card>
  );
}

/**
 * 引用来源 — 更紧凑
 */
export function Sources({ sources }) {
  if (!sources?.length) return null;

  return (
    <div className="bg-slate-50/60 rounded-xl p-4 my-4 animate-fade-in">
      <div className="flex items-center gap-2 mb-2.5">
        <Quote size={13} className="text-slate-400" />
        <h5 className="text-xs font-medium text-slate-500">参考来源</h5>
      </div>
      <div className="space-y-1.5">
        {sources.map((source, idx) => (
          <div key={idx} className="flex items-center gap-2 text-xs bg-white/60 rounded-lg px-3 py-2">
            <span className="font-medium text-slate-600">{source.title}</span>
            <span className="text-slate-200">|</span>
            <span className="text-slate-400">{source.collection}</span>
            {source.relevance_score > 0 && (
              <span className="ml-auto text-owner-400 text-2xs">
                {(source.relevance_score * 100).toFixed(0)}%
              </span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * 快捷回复按钮 — 药丸样式
 */
export function QuickReplies({ replies, onSelect }) {
  if (!replies?.length) return null;

  return (
    <div className="flex flex-wrap gap-2 my-4 animate-fade-in-up">
      {replies.map((reply, idx) => (
        <button
          key={idx}
          onClick={() => onSelect?.(reply)}
          className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full text-sm font-medium bg-white shadow-float hover:shadow-float-md text-slate-600 hover:text-slate-800 transition-all duration-200 hover:-translate-y-0.5"
        >
          <ArrowRight size={12} className="text-slate-400" />
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
  if (!buttons?.length) return null;

  const handleClick = (button) => {
    if (onAction) {
      onAction(button);
    } else if (button.action === 'url') {
      window.open(button.value, '_blank');
    } else if (button.action === 'copy') {
      navigator.clipboard.writeText(button.value);
    }
  };

  const getStyle = (style) => ({
    primary: 'btn-owner',
    secondary: 'btn-ghost',
    success: 'btn-merchant',
    danger: 'bg-red-500 text-white hover:bg-red-600',
    default: 'bg-white shadow-float text-slate-600 hover:shadow-float-md',
  }[style] || 'bg-white shadow-float text-slate-600 hover:shadow-float-md');

  return (
    <div className="flex flex-wrap gap-2 my-4 animate-fade-in-up">
      {buttons.map((button, idx) => (
        <button
          key={idx}
          onClick={() => handleClick(button)}
          className={`btn btn-md ${getStyle(button.style)}`}
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
  const [isCollapsed, setIsCollapsed] = useState(collapsed);

  if (!logs?.length) return null;

  return (
    <div className="thinking-inline my-4 animate-fade-in-up">
      <button
        onClick={() => setIsCollapsed(!isCollapsed)}
        className="thinking-inline-header"
      >
        <Brain size={14} />
        <span className="font-medium">思考过程</span>
        <span className="text-xs text-thinking-400">({logs.length} 步)</span>
        <ChevronDown size={14} className={`transition-transform duration-200 ${isCollapsed ? '' : 'rotate-180'}`} />
      </button>
      {!isCollapsed && (
        <div className="thinking-inline-content animate-fade-in">
          {logs.map((log, idx) => (
            <div key={idx} className="flex gap-2 text-sm">
              <span className="flex-shrink-0 text-xs text-thinking-400 font-mono mt-0.5">{idx + 1}.</span>
              <p className="text-slate-500">{log}</p>
            </div>
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
  if (!errors?.length) return null;

  return (
    <div className="bg-red-50/60 rounded-2xl p-5 my-4 animate-fade-in">
      {errors.map((error, idx) => (
        <div key={idx} className="flex items-start gap-3">
          <XCircle size={18} className="text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="font-medium text-red-600 text-sm">{error.message}</p>
            {error.code && <p className="text-xs text-red-400 mt-1">错误代码: {error.code}</p>}
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * 统一的结构化数据渲染器
 */
export function StructuredDataRenderer({ type, data, onAction }) {
  const components = {
    subsidy_calc: SubsidyCard,
    roi_analysis: ROICard,
    merchant_card: MerchantCard,
    merchant_list: MerchantList,
    process_steps: ProcessSteps,
    table: DataTable,
    checklist: Checklist,
    timeline: Timeline,
    comparison: ComparisonCard,
    sources: Sources,
    quick_replies: QuickReplies,
    action_buttons: ActionButtons,
    thinking: ThinkingProcess,
    error: ErrorMessage,
  };

  const Component = components[type];
  if (!Component) return null;

  const props = {
    quick_replies: { replies: data, onSelect: onAction },
    action_buttons: { buttons: data, onAction },
    sources: { sources: data },
    thinking: { logs: data },
    error: { errors: data },
    merchant_card: { merchant: data },
  }[type] || { data };

  return <Component {...props} />;
}

export default {
  SubsidyCard,
  ROICard,
  ComparisonCard,
  Checklist,
  Timeline,
  MerchantCard,
  MerchantList,
  ProcessSteps,
  DataTable,
  Sources,
  QuickReplies,
  ActionButtons,
  ThinkingProcess,
  ErrorMessage,
  StructuredDataRenderer,
};