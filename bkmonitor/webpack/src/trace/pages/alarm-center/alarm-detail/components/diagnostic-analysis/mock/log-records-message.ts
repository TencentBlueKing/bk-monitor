import { MessageRole, MessageStatus, type Message } from '@blueking/chat-x';
import dayjs from 'dayjs';

import {
  AlertAnalysisMessageType,
  AlertAnalysisResultKind,
  type IAlertAnalysisMessage,
  type IAlertAnalysisMessageExtra,
  type ILogSeriesLine,
  type ILogTextToken,
} from '../typing';

const COUNT_COLOR = '#699df4';
const MOCK_ALERT_ID = '17800000000001';
const USER_MESSAGE_ID = 'user-turn-log-01';
const RESULT_EVENT_ID = 'alert-result-log-01';

const buildHourTimestamps = () => {
  const base = dayjs.tz('2024-04-20 00:00:00');
  return [4, 8, 12, 16, 20].map(hour => base.hour(hour).valueOf());
};

const buildCountLine = (values: number[]): ILogSeriesLine => ({
  key: 'count',
  color: COUNT_COLOR,
  datapoints: buildHourTimestamps().map((timestamp, index) => [values[index], timestamp]),
});

const token = (text: string, highlight?: ILogTextToken['highlight']): ILogTextToken =>
  highlight ? { text, highlight } : { text };

/** 聚类 Pattern：通配位为 wildcard 占位 */
const LOG_PATTERN: ILogTextToken[] = [
  token('Jul '),
  token('#NUMBER#', 'wildcard'),
  token(' '),
  token('#TIME#', 'wildcard'),
  token(' * rsyslogd origin software rsyslogd swVersion 8.24.0-41.el7_7.2 x-pid '),
  token('#NUMBER#', 'wildcard'),
  token(' x-info '),
  token('#URL#', 'wildcard'),
  token(' rsyslogd was HUPed'),
];

/** 示例日志：value 为命中的实际取值 */
const LOG_SAMPLE: ILogTextToken[] = [
  token('Jul '),
  token('23', 'value'),
  token(' '),
  token('19:00', 'value'),
  token(' * rsyslogd origin software rsyslogd swVersion 8.24.0-41.el7_7.2 x-pid '),
  token('234', 'value'),
  token(' x-info #URL# rsyslogd was HUPed'),
];

/** 组装日志聚类结果 envelope，注入到 assistant 消息的 extra 中供卡片解析 */
const createLogRecordsEnvelope = (): IAlertAnalysisMessage => ({
  schemaVersion: 1,
  eventId: RESULT_EVENT_ID,
  messageType: AlertAnalysisMessageType.ANALYSIS_RESULT,
  payload: {
    requestMessageId: USER_MESSAGE_ID,
    subject: { type: 'alert', alert_id: MOCK_ALERT_ID },
    referenceIds: ['ref-log-01'],
    source: { type: 'local_ui_mock' },
    resultKind: AlertAnalysisResultKind.LOG_RECORDS,
    result: {
      matchCount: 212,
      pattern: LOG_PATTERN,
      samples: [LOG_SAMPLE, LOG_SAMPLE],
      series: [buildCountLine([45, 70, 128, 90, 80])],
    },
  },
});

/** 本地 UI 演示消息：用户查看聚类明细 + 日志聚类卡片，不代表真实会话或接口 */
export const createLogRecordsPreviewMessages = (): Message[] => [
  {
    id: USER_MESSAGE_ID,
    messageId: USER_MESSAGE_ID,
    role: MessageRole.User,
    content: '展开查看聚类结果 1 的日志明细',
    status: MessageStatus.Complete,
  },
  {
    id: RESULT_EVENT_ID,
    messageId: RESULT_EVENT_ID,
    role: MessageRole.Assistant,
    content: '这个聚类结果的日志明细如下：',
    status: MessageStatus.Complete,
    property: {
      extra: {
        alert_analysis_message: createLogRecordsEnvelope(),
      } as IAlertAnalysisMessageExtra,
    },
  },
];
