import type { DiagnosticDataService } from '../services/diagnostic-data-service';
import type { DiagnosticSessionService } from '../services/diagnostic-session-service';
import type { DiagnosticPanelKey, IncidentDiagnosisDto } from '../typing';
/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import type { Message } from '@blueking/chat-x';

const MOCK_INCIDENT_DOCUMENT_ID = '17800000009527';
const MOCK_INCIDENT_ID = '9527';

const detailLink = (url: string) => ({ action: 'link' as const, url });

const logPattern =
  'Jul #NUMBER# #TIME# * rsyslogd origin software rsyslogd swVersion 8.24.0-41.el7_7.2 x-pid #NUMBER# x-info #URL# rsyslogd was HUPed';
const logSample =
  'Jul 23 19:00 * rsyslogd origin software rsyslogd swVersion 8.24.0-41.el7_7.2 x-pid 234 x-info #URL# rsyslogd was HUPed';

const diagnosisMockIncidentName = '【Pod】BcsPod(activity-10111-deployment-bys)引起的故障';
const diagnosisMockTreatmentPlans = [
  {
    id: 'plan-1',
    name: 'CPU 告警排查',
    time: '2026-09-09 13:12:00',
    status: 'success' as const,
  },
  {
    id: 'plan-2',
    name: 'CI 流程水分析排查',
    time: '2026-09-09 13:12:00',
    status: 'failed' as const,
  },
];

const diagnosisPanels: Record<DiagnosticPanelKey, IncidentDiagnosisDto> = {
  summary: {
    sub_panel: 'summary',
    contents: '被调接口 (trpc.cj.trpc2s.activitiyscvr/SendAwardSync) 服务所在主机 10.0.2.12 网络不通导致',
  },
  suggestion: {
    sub_panel: 'suggestion',
    contents: '重启服务器，或联系网络管理员检查服务器网络是否正常',
  },
  alerts_analysis: {
    sub_panel: 'alerts_analysis',
    contents: [
      {
        score: 0.9,
        alert_count: 3,
        interaction: detailLink('#/alarm-center/dimension/1'),
        dimension_values: {
          主机名: 'VM-156-110-centos',
          '目标 IP': '11.185.156.110',
          管控区域: 0,
          'APM 应用(app_name)': 'bk-monitor-frontened',
        },
        alerts: [
          { id: '17800000000001', strategy_id: '101', strategy_name: '日志平台 - es 磁盘容量告警' },
          { id: '17800000000002', strategy_id: '102', strategy_name: '蓝鲸 - es 磁盘容量告警' },
          { id: '17800000000003', strategy_id: '101', strategy_name: '日志平台 - es 磁盘容量告警' },
        ],
        strategy_alerts_mapping: {
          101: {
            strategy_id: '101',
            strategy_name: '日志平台 - es 磁盘容量告警',
            alerts: ['17800000000001', '17800000000003'],
            interaction: detailLink('#/strategy-config?id=101'),
          },
          102: {
            strategy_id: '102',
            strategy_name: '蓝鲸 - es 磁盘容量告警',
            alerts: ['17800000000002'],
            interaction: detailLink('#/strategy-config?id=102'),
          },
        },
      },
      {
        score: 0.9,
        interaction: detailLink('#/alarm-center/dimension/2'),
        dimension_values: {},
      },
      {
        score: 0.9,
        interaction: detailLink('#/alarm-center/dimension/3'),
        dimension_values: {},
      },
    ],
  },
  trace_analysis: {
    sub_panel: 'trace_analysis',
    individual_summary:
      '在关联调用链中定位到异常 Span，下面给出的错误信息与示例 span 明细，点击字段可跳转到 Trace 检索。',
    contents: {
      trace_messages_analysis: [
        {
          trace_id: '7160731cd9fe607033c1ae7d7a5f449b',
          span_id: 'a1b2c3d4e5f60718',
          app_name: 'bkmonitorv3',
          service_name: 'unify-query',
          kind: 'SERVER',
          log_count: 20,
          pattern: "TypeError: '<' not supported between instances of 'str' and 'int'",
          error_message:
            "TypeError: '<' not supported between instances of 'str' and 'int' in IncidentHandlersResource",
          interaction: detailLink('#/trace/explore?traceId=7160731cd9fe607033c1ae7d7a5f449b'),
        },
      ],
    },
  },
  logs_analysis: {
    sub_panel: 'logs_analysis',
    individual_summary: '对告警窗口内异常日志做了聚类，下面给出出现次数最高的 Pattern 和对应示例日志，便于对照排查。',
    contents: {
      logs_from_alerts: [
        {
          pattern: logPattern,
          sample: logSample,
          log_count: 212,
          interaction: detailLink('#/log-retrieve?cluster=1'),
        },
        {
          log_count: 54,
          interaction: detailLink('#/log-retrieve?cluster=2'),
        },
      ],
    },
  },
  events_analysis: {
    sub_panel: 'events_analysis',
    individual_summary: '通过分析告警产生前 1 小时时间窗口事件，识别出与当前告警高度相关的 K8s 与变更事件，示例如下。',
    contents: {
      k8s_warning_events: [
        {
          title: 'FailedMount',
          event_name: 'FailedMount',
          time: '2024-04-20 19:22:02',
          description:
            'MountVolume.SetUp failed for volume "kube-api-access-xxx": object "default"/"sa-token" not found',
        },
        { title: 'Unhealthy' },
        { title: 'Events-Name' },
      ],
      incident_ticket_events: [
        {
          title: '变更单审批超时',
          event_name: '变更单审批超时',
          time: '2024-04-20 19:22:02',
          description: 'ITSM ticket TICKET-20240420-118 超过 30 分钟未完成审批',
        },
      ],
    },
    display: {
      labels_mapping: {
        k8s_warning_events: {
          label: 'K8s 事件',
          top: 3,
          unit: '个',
          interaction: detailLink('#/event-center/k8s'),
        },
        incident_ticket_events: {
          label: 'ITSM 系统事件',
          top: 3,
          unit: '个',
          interaction: detailLink('#/event-center/itsm'),
        },
      },
      fields: {
        k8s_warning_events: {
          time: '发生时间',
          event_name: '事件名',
          description: '事件内容',
        },
        incident_ticket_events: {
          time: '发生时间',
          event_name: '事件名',
          description: '事件内容',
        },
      },
      statistics: {
        k8s_warning_events: { total: 20 },
        incident_ticket_events: { total: 20 },
      },
    },
  },
};

const assertNotAborted = (signal?: AbortSignal) => {
  if (!signal?.aborted) return;
  throw new DOMException('Aborted', 'AbortError');
};

const wait = (delay: number, signal: AbortSignal) =>
  new Promise<void>((resolve, reject) => {
    assertNotAborted(signal);
    const timer = globalThis.setTimeout(resolve, delay);
    signal.addEventListener(
      'abort',
      () => {
        globalThis.clearTimeout(timer);
        reject(new DOMException('Aborted', 'AbortError'));
      },
      { once: true }
    );
  });

export const diagnosisMockSnapshot = {
  alertReason: String(diagnosisPanels.summary.contents || ''),
  incidentName: diagnosisMockIncidentName,
  panels: diagnosisPanels,
  recommendation: String(diagnosisPanels.suggestion.contents || ''),
  treatmentPlans: diagnosisMockTreatmentPlans,
};

export const isDiagnosticMockEnabled = (environment = process.env.NODE_ENV) => environment === 'development';

export const mockDiagnosticDataService: DiagnosticDataService = {
  async getAlertIncidentDetail(_alertId, options) {
    assertNotAborted(options?.signal);
    return {
      greyed_spaces: [],
      incident: {
        id: MOCK_INCIDENT_DOCUMENT_ID,
        incident_id: MOCK_INCIDENT_ID,
        incident_name: diagnosisMockIncidentName,
        bk_biz_id: Number(typeof window === 'undefined' ? 2 : window.cc_biz_id) || 2,
        bk_biz_name: '演示业务',
        alert_count: 11,
        treatment_plans: diagnosisMockTreatmentPlans,
      },
    };
  },
  async getIncidentResults(_incidentDocumentId, _bizId, options) {
    assertNotAborted(options?.signal);
    return {
      enabled: true,
      status: 'finished',
      panels: {
        incident_diagnosis: {
          enabled: true,
          status: 'finished',
          sub_panels: Object.fromEntries(
            Object.keys(diagnosisPanels).map(key => [key, { enabled: true, status: 'finished' }])
          ),
        },
      },
    };
  },
  async getIncidentDiagnosis(_incidentDocumentId, _bizId, subPanel, options) {
    assertNotAborted(options?.signal);
    return diagnosisPanels[subPanel];
  },
  async getPanelDetail(params, options) {
    assertNotAborted(options?.signal);
    return {
      drawer_type: params.drawer_type,
      payload: {
        done: true,
        list: [],
        page: params.page || 1,
        page_size: params.page_size || 30,
        total: 0,
      },
    };
  },
};

export const createMockDiagnosticSessionService = ({
  delay = 120,
}: {
  delay?: number;
} = {}): DiagnosticSessionService => ({
  async loadSession(context, { signal }) {
    assertNotAborted(signal);
    return {
      sessionCode: `mock-alert-analysis-${context.bizId}-${context.alarmId}`,
      messages: [],
    };
  },
  async persistUserMessage({ content, messageId, signal }) {
    assertNotAborted(signal);
    return {
      id: messageId,
      messageId,
      role: 'user',
      status: 'complete',
      content,
    } as unknown as Message;
  },
  async streamCompletion({ onDelta, signal }) {
    const chunks = ['根据当前诊断结果，', '被调接口所在主机网络不通，', '建议先检查服务器网络或重启服务器。'];
    let content = '';
    for (const chunk of chunks) {
      await wait(delay, signal);
      content += chunk;
      onDelta(chunk, { cover: false });
    }
    return {
      content,
      property: {
        extra: {
          alert_analysis_message: {
            schemaVersion: 1,
            type: 'log_analysis',
            payload: {
              summary: '对告警窗口内异常日志做了聚类，下面给出出现次数最高的 Pattern 和对应示例日志。',
              items: [
                {
                  id: 'mock-chat-log-1',
                  pattern: logPattern,
                  sample: logSample,
                },
              ],
            },
          },
        },
      },
    };
  },
});

export const mockDiagnosticSessionService = createMockDiagnosticSessionService();

export const getDiagnosticMockAdapters = (
  environment = process.env.NODE_ENV
): {
  dataService?: DiagnosticDataService;
  sessionService?: DiagnosticSessionService;
} =>
  isDiagnosticMockEnabled(environment)
    ? {
        dataService: mockDiagnosticDataService,
        sessionService: mockDiagnosticSessionService,
      }
    : {};
