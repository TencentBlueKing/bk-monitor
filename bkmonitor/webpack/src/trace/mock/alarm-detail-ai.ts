/**
 * 【临时联调 mock，联调就绪后请删除本文件 + src/trace/index.ts 里的 installAlarmDetailAiMock() 调用】
 *
 * 告警详情 AI诊断（TAPD 137783448）前端验证开关。
 * 不拦截真实接口，只做三件事：
 *   1. 覆盖「该告警是否已纳入故障」这一个展示条件
 *   2. 为第一个板块提供 BKFara 事件分析的流程记录
 *   3. 为左侧维度信息上方提供「告警问题」文案
 *   4. 为底部追问输入框提供假回复，用来验证会话交互
 *
 * 触发方式（hash 或 search 均可）：
 *   aiMock=incident  已纳入故障 → 结论里带「关联故障」，可跳故障详情
 *   aiMock=alert     未纳入故障 → 结论只针对当前这条告警，无「关联故障」
 *
 * 带 aiMock 时会自动展开右侧 AI诊断 面板。
 */
export type AlarmDetailAiMockScene = 'alert' | 'incident';

export interface AlarmDetailAiMockApi {
  ask: (question: string) => Promise<string>;
  getFlags: () => AlarmDetailAiMockFlags | null;
  shouldAutoOpen: () => boolean;
}

export interface AlarmDetailAiMockFlags {
  alertProblem: {
    highlight?: string;
    text: string;
  } | null;
  bkFaraProcesses: Array<{
    executeResult: string;
    executeTime: string;
    link?: string;
    name: string;
  }>;
  hasIncident: boolean;
  incident: {
    id: string;
    incident_id: number;
    incident_name: string;
  } | null;
}

declare global {
  interface Window {
    __ALARM_DETAIL_AI_MOCK__?: AlarmDetailAiMockApi;
  }
}

const MOCK_SCENES: AlarmDetailAiMockScene[] = ['incident', 'alert'];

const MOCK_ALERT_PROBLEM = {
  text: '当前服务 (activity-microservices.msgcenter) 调用接口(trpc.cj.trpc2s.activitiyscvr/SendAwardSync) 的成功率为 ',
  highlight: '65%',
};

const MOCK_INCIDENT = {
  id: 'mock-incident-137783448',
  incident_id: 137783448,
  incident_name: '【Pod】BcsPod(activity-10111-deployment-bys)引起的故障',
};

const MOCK_BKFARA_PROCESSES = [
  {
    name: '流程名称1',
    executeTime: '2026-09-09 13:12:00',
    executeResult: '成功',
    // 【占位】真实 BKFara 流程详情地址待接口补齐
    link: '#bkfara-placeholder-1',
  },
  {
    name: '流程名称2',
    executeTime: '2026-09-09 13:15:30',
    executeResult: '失败',
    // 【占位】真实 BKFara 流程详情地址待接口补齐
    link: '#bkfara-placeholder-2',
  },
];

/** 按关键词命中的假回复，命中不了就用兜底那条 */
const MOCK_REPLIES: { keywords: string[]; reply: string }[] = [
  {
    keywords: ['根因', '原因', '为什么', 'why'],
    reply:
      '从可疑维度和调用链看，被调接口 (trpc.cj.trpc2s.activitiyscvr/SendAwardSync) 所在主机 10.0.2.12 在 16:42 出现网络抖动，同一时间窗口内该主机上的其它服务同样出现超时，所以更可能是主机侧网络问题，而不是业务代码变更引入的。',
  },
  {
    keywords: ['影响', '范围', '波及'],
    reply:
      '当前影响范围集中在 activity-microservices.msgcenter 这一个服务，同集群其余 3 个服务的成功率未见下降。按调用链上下游推算，预计影响下游 2 个接口的少量请求。',
  },
  {
    keywords: ['怎么处理', '建议', '解决', '恢复', '止损'],
    reply:
      '建议按这个顺序处理：1）先把 10.0.2.12 从负载均衡摘除止损；2）联系网络管理员确认该主机的网络链路；3）确认恢复后再灰度放量观察 10 分钟。',
  },
];

const FALLBACK_REPLY =
  '这条告警的关键信息我已经在上面的诊断结论里给出了。你可以再问我「根因是什么」「影响范围多大」「应该怎么处理」，我会结合可疑维度、调用链和日志继续分析。';

/**
 * 告警列表路由会重写 query 把 aiMock 洗掉，所以读到一次就记住，
 * 直到整页刷新换成另一个分支为止。
 */
let cachedScene: '' | AlarmDetailAiMockScene = '';

function readAiMockScene(): '' | AlarmDetailAiMockScene {
  const fromSearch = new URLSearchParams(window.location.search).get('aiMock');
  const hash = window.location.hash || '';
  const queryIndex = hash.indexOf('?');
  const fromHash = queryIndex >= 0 ? new URLSearchParams(hash.slice(queryIndex)).get('aiMock') : '';
  const raw = (fromHash || fromSearch || '').trim();
  if (MOCK_SCENES.includes(raw as AlarmDetailAiMockScene)) {
    cachedScene = raw as AlarmDetailAiMockScene;
  }
  return cachedScene;
}

export function shouldAutoOpenAiAnalysis() {
  return Boolean(window.__ALARM_DETAIL_AI_MOCK__?.shouldAutoOpen?.());
}

export function askAlarmDetailAiMock(question: string) {
  return window.__ALARM_DETAIL_AI_MOCK__?.ask?.(question) ?? null;
}

export function installAlarmDetailAiMock() {
  window.__ALARM_DETAIL_AI_MOCK__ = {
    getFlags() {
      const scene = readAiMockScene();
      if (!scene) return null;
      const hasIncident = scene === 'incident';
      return {
        alertProblem: MOCK_ALERT_PROBLEM,
        bkFaraProcesses: MOCK_BKFARA_PROCESSES,
        hasIncident,
        incident: hasIncident ? MOCK_INCIDENT : null,
      };
    },
    shouldAutoOpen() {
      return Boolean(readAiMockScene());
    },
    ask(question: string) {
      const text = (question || '').toLowerCase();
      const hit = MOCK_REPLIES.find(item => item.keywords.some(keyword => text.includes(keyword.toLowerCase())));
      return new Promise<string>(resolve => {
        setTimeout(() => resolve(hit?.reply || FALLBACK_REPLY), 800);
      });
    },
  };
}
