import { MessageRole, MessageStatus, type Message } from '@blueking/chat-x';
import dayjs from 'dayjs';

import {
  AlertAnalysisMessageType,
  AlertAnalysisResultKind,
  type IAlertAnalysisMessage,
  type IAlertAnalysisMessageExtra,
  type IMetricSeriesLine,
} from '../typing';

/** 设计稿：当前线 #699DF4，上周同期 #F8B64F */
const CURRENT_COLOR = '#699df4';
const WEEK_AGO_COLOR = '#f8b64f';

const MOCK_ALERT_ID = '17800000000001';
const USER_MESSAGE_ID = 'user-turn-example-01';
const RESULT_EVENT_ID = 'alert-result-event-01';

/** 按设计稿 4:00–20:00 五个整点构造时间戳 */
const buildHourTimestamps = () => {
  const base = dayjs.tz('2024-04-20 00:00:00');
  return [4, 8, 12, 16, 20].map(hour => base.hour(hour).valueOf());
};

const buildLine = (
  key: IMetricSeriesLine['key'],
  alias: string,
  color: string,
  values: number[]
): IMetricSeriesLine => ({
  key,
  alias,
  color,
  datapoints: buildHourTimestamps().map((timestamp, index) => [values[index], timestamp]),
});

/** 组装指标趋势结果 envelope，注入到 assistant 消息的 extra 中供卡片解析 */
const createMetricSeriesEnvelope = (): IAlertAnalysisMessage => ({
  schemaVersion: 1,
  eventId: RESULT_EVENT_ID,
  messageType: AlertAnalysisMessageType.ANALYSIS_RESULT,
  payload: {
    requestMessageId: USER_MESSAGE_ID,
    subject: { type: 'alert', alert_id: MOCK_ALERT_ID },
    referenceIds: ['ref-dimension-01'],
    source: { type: 'local_ui_mock' },
    resultKind: AlertAnalysisResultKind.METRIC_SERIES,
    result: {
      title: 'AVG(CPU 单核使用率)',
      dimensions: [
        { key: 'bk_hostname', alias: '主机名', value: 'VM-156-110-centos' },
        { key: 'bk_target_ip', alias: '目标 IP', value: '192.0.2.10' },
        { key: 'bk_target_cloud_id', alias: '管控区域', value: '0' },
      ],
      series: [
        buildLine('current', '当前', CURRENT_COLOR, [26, 32, 56, 43, 37]),
        buildLine('week_ago', '上周同期', WEEK_AGO_COLOR, [26, 43, 70, 50, 44]),
      ],
    },
  },
});

/** 本地 UI 演示消息：info 分隔 + 用户提问 + 指标趋势卡片，不代表真实会话或接口 */
export const createMetricSeriesPreviewMessages = (): Message[] => [
  {
    id: 'alert-info-new-chat',
    messageId: 'alert-info-new-chat',
    role: MessageRole.Info,
    content: window.i18n.t('新对话'),
    status: MessageStatus.Complete,
  },
  {
    id: USER_MESSAGE_ID,
    messageId: USER_MESSAGE_ID,
    role: MessageRole.User,
    content: '看下异常维度（组合）1 的指标趋势',
    status: MessageStatus.Complete,
  },
  {
    id: RESULT_EVENT_ID,
    messageId: RESULT_EVENT_ID,
    role: MessageRole.Assistant,
    content: '这是该指标在这组维度下的趋势，异常主要集中在曲线后段：',
    status: MessageStatus.Complete,
    property: {
      extra: {
        alert_analysis_message: createMetricSeriesEnvelope(),
      } as IAlertAnalysisMessageExtra,
    },
  },
];
