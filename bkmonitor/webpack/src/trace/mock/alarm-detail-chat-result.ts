/**
 * 【临时联调 mock，联调就绪后请删除本文件 + diagnostic-analysis.tsx 里的 buildAlarmDetailChatResult 调用】
 *
 * 告警详情 AI诊断：分析板块里原本新开页的入口改为在会话里回显后，
 * 回答需要的结构化数据还没有真实接口，这里按请求上下文造一份同构的假数据。
 *
 * 覆盖四处入口：
 *   异常维度（组合）标题图标  → 指标趋势
 *   「包含 N 个告警」          → 告警列表
 *   日志聚类结果标题图标       → 日志聚类明细
 *   事件分析的事件总数         → 事件列表
 */
import {
  ChatResultKind,
  type IChatAlertItem,
  type IChatEventItem,
  type IChatResult,
  type IChatResultRequest,
  type IChatSeries,
} from '@/pages/alarm-center/alarm-detail/components/diagnostic-analysis/chat/chat-result-typing';

/** 回显数据的时间窗口：以告警开始时间为基准往前后各铺一段 */
const POINT_COUNT = 30;
const POINT_INTERVAL = 60 * 1000;

const SERIES_COLORS = ['#3A84FF', '#FF9C01', '#2DCB9D'];

/** 用曲线名做种子，保证同一组维度每次生成的曲线一致，便于反复对照 */
function createSeed(text: string) {
  let seed = 0;
  for (let i = 0; i < text.length; i++) {
    seed = (seed * 31 + text.charCodeAt(i)) % 9973;
  }
  return seed || 17;
}

/** 造一条带异常抬升的曲线：后 1/3 段整体拉高，对应告警发生 */
function createSeries(name: string, color: string, baseTime: number, base: number): IChatSeries {
  const seed = createSeed(name);
  const startTime = baseTime - POINT_COUNT * POINT_INTERVAL * 0.7;
  const datapoints: [number, number][] = [];
  for (let i = 0; i < POINT_COUNT; i++) {
    const wave = Math.sin((i + seed) / 3) * base * 0.12;
    const noise = (((seed * (i + 3)) % 17) / 17 - 0.5) * base * 0.08;
    const anomaly = i > POINT_COUNT * 0.66 ? base * 0.55 * ((i - POINT_COUNT * 0.66) / (POINT_COUNT * 0.34)) : 0;
    const value = Math.max(0, base + wave + noise + anomaly);
    datapoints.push([Number(value.toFixed(2)), startTime + i * POINT_INTERVAL]);
  }
  return { name, color, datapoints };
}

const MOCK_ALERT_NAMES = [
  '[调用分析] 被调请求量波动告警',
  '[调用分析] 被调成功率低于阈值',
  '[主机] CPU 使用率过高',
  'Pod 重启次数异常',
  '[调用分析] 被调耗时 P95 上升',
];

const MOCK_ALERT_STATUS = ['未恢复', '已恢复', '未恢复', '已恢复', '未恢复'];

function buildAlertList(request: IChatResultRequest, baseTime: number) {
  const { alertCount = 0, strategies = [], dimensions = [] } = request.context || {};
  const total = alertCount || MOCK_ALERT_NAMES.length;
  const dimensionSuffix = dimensions
    .filter(item => !String(item.name).includes('占位') && !String(item.value).includes('占位'))
    .map(item => `${item.name}=${item.value}`)
    .join('，');

  // 回显要给全量，卡片里再按 5 条一批展开
  const alerts: IChatAlertItem[] = Array.from({ length: total }, (_, index) => {
    const beginTime = new Date(baseTime - (index + 1) * 7 * 60 * 1000);
    return {
      id: `${17889308161668 + index}`,
      name: MOCK_ALERT_NAMES[index % MOCK_ALERT_NAMES.length],
      severity: ((index % 3) + 1) as IChatAlertItem['severity'],
      status: MOCK_ALERT_STATUS[index % MOCK_ALERT_STATUS.length],
      strategyName: strategies[index % Math.max(strategies.length, 1)]?.strategy_name || dimensionSuffix || '--',
      beginTime: formatTime(beginTime.getTime()),
    };
  });

  return { alerts, total };
}

const MOCK_EVENT_TEMPLATES = [
  { name: 'BcsPodKilling', source: 'Kubernetes', content: 'Pod activity-10111-deployment-bys 被驱逐，节点资源不足' },
  { name: 'BcsOOMKilled', source: 'Kubernetes', content: '容器 msgcenter 因内存超限被 OOM Kill，已重启 2 次' },
  { name: 'ConfigChanged', source: '变更事件', content: '服务 activity-microservices.msgcenter 发布了新版本 v1.8.3' },
  { name: 'NodeNotReady', source: 'Kubernetes', content: '节点 10.0.2.12 状态变更为 NotReady，持续 3 分钟' },
  { name: 'ITSMTicket', source: '变更事件', content: 'ITSM ticket TICKET-20240420-118 超过 30 分钟未完成审批' },
];

function buildEventList(request: IChatResultRequest, baseTime: number) {
  const { eventTotal = 0, eventUnit = window.i18n.t('个事件') as string } = request.context || {};
  const total = eventTotal || MOCK_EVENT_TEMPLATES.length;
  const events: IChatEventItem[] = Array.from({ length: total }, (_, index) => {
    const template = MOCK_EVENT_TEMPLATES[index % MOCK_EVENT_TEMPLATES.length];
    return {
      ...template,
      time: formatTime(baseTime - (index + 1) * 5 * 60 * 1000),
    };
  });
  return { events, total, unit: eventUnit };
}

const MOCK_DEMO_LOGS = [
  JSON.stringify(
    {
      dtEventTimeStamp: 1713611921000,
      ip: '10.0.34.8',
      path: '/var/log/kubelet.log',
      log: 'Liveness probe failed: dial tcp 10.0.34.8:8080: i/o timeout',
    },
    null,
    2
  ),
  JSON.stringify(
    {
      dtEventTimeStamp: 1713611983000,
      ip: '10.0.2.12',
      path: '/var/log/kubelet.log',
      log: 'Readiness probe failed: dial tcp 10.0.2.12:8080: i/o timeout',
    },
    null,
    2
  ),
];

function formatTime(timestamp: number) {
  const date = new Date(timestamp);
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(
    date.getMinutes()
  )}:${pad(date.getSeconds())}`;
}

interface IBuildOptions {
  /** 告警开始时间（毫秒），取不到时用当前时间 */
  baseTime?: number;
  /** 指标名，作为趋势图标题 */
  metricTitle?: string;
}

/** 按板块请求拼出回答里的结构化结果，拿不到对应类型时返回 null（回答只留文字） */
export function buildAlarmDetailChatResult(
  request: IChatResultRequest,
  options: IBuildOptions = {}
): IChatResult | null {
  const baseTime = options.baseTime || Date.now();

  switch (request.kind) {
    case ChatResultKind.METRIC: {
      const conditions = (request.context?.dimensions || []).filter(
        item => !String(item.name).includes('占位') && !String(item.value).includes('占位')
      );
      const title = options.metricTitle || (window.i18n.t('指标趋势') as string);
      const series = [
        createSeries(`${title}-current`, SERIES_COLORS[0], baseTime, 60),
        createSeries(`${title}-baseline`, SERIES_COLORS[1], baseTime, 42),
      ];
      series[0].name = window.i18n.t('当前') as string;
      series[1].name = window.i18n.t('上周同期') as string;
      return { kind: ChatResultKind.METRIC, title, conditions, series };
    }
    case ChatResultKind.ALERT_LIST: {
      const { alerts, total } = buildAlertList(request, baseTime);
      return { kind: ChatResultKind.ALERT_LIST, alerts, total };
    }
    case ChatResultKind.LOG_CLUSTER: {
      const pattern = request.context?.pattern || '';
      const trend = [createSeries(pattern || 'log-cluster', SERIES_COLORS[2], baseTime, 12)];
      trend[0].name = window.i18n.t('日志条数') as string;
      return {
        kind: ChatResultKind.LOG_CLUSTER,
        pattern,
        logCount: request.context?.logCount || 0,
        demoLogs: MOCK_DEMO_LOGS,
        trend,
      };
    }
    case ChatResultKind.EVENT_LIST: {
      const { events, total, unit } = buildEventList(request, baseTime);
      return { kind: ChatResultKind.EVENT_LIST, events, total, unit };
    }
    default:
      return null;
  }
}
