import { MessageRole, MessageStatus, type Message } from '@blueking/chat-x';
import dayjs from 'dayjs';

import { AlertLevelEnum, AlarmStatusEnum } from '@/pages/alarm-center/typings';

import {
  AlertAnalysisMessageType,
  AlertAnalysisResultKind,
  type IAlertAnalysisMessage,
  type IAlertAnalysisMessageExtra,
  type IAlertListItem,
} from '../typing';

const MOCK_ALERT_ID = '17800000000001';
const USER_MESSAGE_ID = 'user-turn-alert-list-01';
const RESULT_EVENT_ID = 'alert-result-alert-list-01';

const BEGIN_TIME = dayjs.tz('2026-10-10 00:00:00').valueOf();

/** 补齐演示用告警项的公共字段（时间 / 通知状态 / 状态） */
const buildAlert = (item: Omit<IAlertListItem, 'beginTime' | 'notifyText' | 'status'>): IAlertListItem => ({
  ...item,
  beginTime: BEGIN_TIME,
  notifyText: '已通知',
  status: AlarmStatusEnum.ABNORMAL,
});

/** 组装维度命中告警列表 envelope，注入到 assistant 消息的 extra 中供卡片解析 */
const createAlertListEnvelope = (): IAlertAnalysisMessage => ({
  schemaVersion: 1,
  eventId: RESULT_EVENT_ID,
  messageType: AlertAnalysisMessageType.ANALYSIS_RESULT,
  payload: {
    requestMessageId: USER_MESSAGE_ID,
    subject: { type: 'alert', alert_id: MOCK_ALERT_ID },
    referenceIds: ['ref-alert-list-01'],
    source: { type: 'local_ui_mock' },
    resultKind: AlertAnalysisResultKind.ALERT_LIST,
    result: {
      alerts: [
        buildAlert({
          id: '17800000000011',
          title: '[调用分析] 被调请求量波动告警',
          severity: AlertLevelEnum.FATAL,
          fields: [
            { key: '内容', value: 'observed_generation - metadata_generation > 0，当前值 1' },
            { key: '目标', value: '集群 bkop · k8s-worker · 正式' },
            { key: '空间', value: '[#2]蓝鲸(业务)' },
          ],
        }),
        buildAlert({
          id: '17800000000012',
          title: '[调用分析] 被调成功率低于阈值',
          severity: AlertLevelEnum.WARNING,
          fields: [
            { key: '内容', value: '前 5 点瞬间值 42，上升超过 30%，当前值 60' },
            { key: '目标', value: 'trpc-cluster-access-demo:bkm.web' },
            { key: '空间', value: '[#2]蓝鲸(业务)' },
          ],
        }),
        buildAlert({
          id: '17800000000013',
          title: '[主机] CPU 使用率过高',
          severity: AlertLevelEnum.REMIND,
          fields: [
            { key: '内容', value: 'SUM(trace分钟请求数) ≥ 15，当前值 19' },
            { key: '目标', value: '集群 bkop · k8s-worker · 正式' },
            { key: '空间', value: 'bkop:bk_log_search' },
          ],
        }),
      ],
    },
  },
});

/** 本地 UI 演示消息：用户查看维度命中告警 + 告警列表卡片，不代表真实会话或接口 */
export const createAlertListPreviewMessages = (): Message[] => [
  {
    id: USER_MESSAGE_ID,
    messageId: USER_MESSAGE_ID,
    role: MessageRole.User,
    content: '这组维度包含的 3 个告警都是哪些？',
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
        alert_analysis_message: createAlertListEnvelope(),
      } as IAlertAnalysisMessageExtra,
    },
  },
];
