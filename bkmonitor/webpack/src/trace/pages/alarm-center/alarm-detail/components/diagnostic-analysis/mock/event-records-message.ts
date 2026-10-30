import { MessageRole, MessageStatus, type Message } from '@blueking/chat-x';
import dayjs from 'dayjs';

import {
  AlertAnalysisMessageType,
  AlertAnalysisResultKind,
  EventRecordSourceType,
  type IAlertAnalysisMessage,
  type IAlertAnalysisMessageExtra,
  type IEventRecordItem,
} from '../typing';

const MOCK_ALERT_ID = '17800000000001';
const USER_MESSAGE_ID = 'user-turn-event-list-01';
const RESULT_EVENT_ID = 'alert-result-event-list-01';
const EVENT_TIME = dayjs.tz('2026-10-10 00:00:00').valueOf();
const EVENT_TOTAL = 20;

const EVENT_NAMES = [
  'Agent 心跳丢失（AgentLost）',
  'BcsOOMKilled',
  'ConfigChanged',
  'NodeNotReady',
  'ITSMTicket',
];

/** 按序号循环取事件名，批量生成演示事件项 */
const buildEvent = (index: number): IEventRecordItem => ({
  id: `event-record-${String(index + 1).padStart(2, '0')}`,
  eventName: EVENT_NAMES[index % EVENT_NAMES.length],
  source: {
    type: EventRecordSourceType.BCS,
    alias: 'K8s',
  },
  fields: [
    { key: '内容', value: '主机（0-192.0.2.10）Agent 失联' },
    { key: '目标', value: 'Default Area[0] / 192.0.2.10' },
  ],
  time: EVENT_TIME,
});

/** 组装事件列表结果 envelope，注入到 assistant 消息的 extra 中供卡片解析 */
const createEventRecordsEnvelope = (): IAlertAnalysisMessage => ({
  schemaVersion: 1,
  eventId: RESULT_EVENT_ID,
  messageType: AlertAnalysisMessageType.ANALYSIS_RESULT,
  payload: {
    requestMessageId: USER_MESSAGE_ID,
    subject: { type: 'alert', alert_id: MOCK_ALERT_ID },
    referenceIds: ['ref-event-list-01'],
    source: { type: 'local_ui_mock' },
    resultKind: AlertAnalysisResultKind.EVENT_RECORDS,
    result: {
      total: EVENT_TOTAL,
      items: Array.from({ length: EVENT_TOTAL }, (_, index) => buildEvent(index)),
    },
  },
});

/** 本地 UI 演示消息：用户查看事件明细 + 事件列表卡片，不代表真实会话或接口 */
export const createEventRecordsPreviewMessages = (): Message[] => [
  {
    id: USER_MESSAGE_ID,
    messageId: USER_MESSAGE_ID,
    role: MessageRole.User,
    content: 'K8s 事件这 20 个事件分别是什么？',
    status: MessageStatus.Complete,
  },
  {
    id: RESULT_EVENT_ID,
    messageId: RESULT_EVENT_ID,
    role: MessageRole.Assistant,
    content: '这组维度命中的告警如下：',
    status: MessageStatus.Complete,
    property: {
      extra: {
        alert_analysis_message: createEventRecordsEnvelope(),
      } as IAlertAnalysisMessageExtra,
    },
  },
];
