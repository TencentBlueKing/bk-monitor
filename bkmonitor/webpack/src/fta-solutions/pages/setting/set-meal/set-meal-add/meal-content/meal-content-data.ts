/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import { random } from 'monitor-common/utils/utils';

import { type INoticeWayValue, robot } from '../components/notice-mode';

export const mealType = {
  notice: 'notice',
  callback: 'webhook',
};

export interface IExecution {
  notifyConfig?: INoticeWayValue[];
  // 执行通知配置
  riskLevel?: number; // 敏感度，1 - 高危，2 - 一般，3 - 无所谓
}

export interface IMealData {
  id?: number;
  name?: string;
  notice?: INotice; // 通知告警
  peripheral?: IPeripheral; // 周边系统
  pluginType?: string; // 套餐类型
  webhook?: IWebhook; // http回调
}

export interface INotice {
  alert?: INoticeAlert[];
  execution?: IExecution[];
  template?: INoticeTemplate[];
}
export interface INoticeAlert {
  intervalNotifyMode?: 'increasing' | 'standard'; // 间隔模式
  key?: string; // key前端随机生成
  notifyConfig?: INoticeWayValue[];
  notifyInterval?: number; // 时间间隔
  // 告警通知配置
  timeRange?: string[]; // 时间段
}

export interface INoticeTemplate {
  messageTmpl?: string;
  // 通知模板配置
  signal?: string; // 触发信号：abnormal-告警触发时，recovered-告警恢复时，closed-告警关闭时
  titleTmpl?: string;
}
export interface IPeripheral {
  riskLevel?: number;
  timeout?: number;
  data?: {
    formTemplateId?: number | string;
    templateDetail?: {
      [propName: string]: string;
    };
  };
}

export interface IWebhook {
  riskLevel?: number;
  timeout?: number;
  res?: {
    authorize?: {
      // 认证
      authConfig?: { password?: string; token?: string; username?: string };
      authType?: string;
    };
    body?: {
      // 主体
      content: string;
      contentType: string;
      dataType: string;
      params: {
        desc: string;
        isEnabled: boolean;
        key: string;
        value: string;
      }[];
    };
    failedRetry?: {
      // 设置
      maxRetryTimes: number;
      needPoll: boolean;
      notifyInterval: number;
      retryInterval: number;
      timeout: number;
    };
    headers?: {
      desc: string;
      index: number;
      isEnabled: boolean;
      key: string;
      value: string;
    }[];
    method?: string;
    queryParams?: {
      desc: string;
      isEnabled: boolean;
      key: string;
      value: string;
    }[];
    url: string;
  };
}

export const templateSignalName = {
  abnormal: window.i18n.tc('告警触发时'),
  recovered: window.i18n.tc('告警恢复时'),
  closed: window.i18n.tc('告警关闭时'),
  ack: window.i18n.tc('告警确认时'),
};

export const executionName = {
  1: window.i18n.tc('高危'),
  2: window.i18n.tc('谨慎'),
  3: window.i18n.tc('普通'),
};
export const intervalModeName = {
  standard: window.i18n.tc('固定'),
  increasing: window.i18n.tc('递增'),
};

// 敏感度
export const sensitivityName = {
  1: `${window.i18n.t('高危')}（${window.i18n.t('执行后不可逆')}）`,
  2: `${window.i18n.t('谨慎')}（${window.i18n.t('不能反复执行')}）`,
  3: `${window.i18n.t('普通')}（${window.i18n.t('有告警就执行')}）`,
};
export const sensitivityList = [
  { id: 1, name: `${window.i18n.t('高危')}：${window.i18n.t('执行后不可逆')}` },
  { id: 2, name: `${window.i18n.t('谨慎')}：${window.i18n.t('不能反复执行')}` },
  { id: 3, name: `${window.i18n.t('普通')}：${window.i18n.t('有告警就执行')}` },
];
export const intervalModeTips = {
  standard: window.i18n.t('固定N分钟间隔进行通知'),
  increasing: window.i18n.t('按通知次数的指数递增，依次按N，2N，4N，8N,...依次类推执行，最大24小时'),
};

export const executionTips = {
  1: window.i18n.t('高危代表执行此类操作影响比较大，在执行处理套餐时需要进行及时的通知。'),
  2: window.i18n.t('谨慎代表执行此类操作影响比高危小，但是也不可多次反复的执行，一般在失败时需要提示。'),
  3: window.i18n.t(
    '大部分的处理套餐建议是可以做成可以反复执行并且风险可控的，常见的回调、发工单等甚至都不需要有额外的通知。'
  ),
};

export const DEFAULT_MESSAGE_TMPL = `{{content.level}}
{{content.begin_time}}
{{content.time}}
{{content.duration}}
{{content.target_type}}
{{content.data_source}}
{{content.content}}
{{content.current_value}}
{{content.biz}}
{{content.target}}
{{content.dimension}}
{{content.detail}}
{{content.assign_detail}}
{{content.related_info}}`;

export const DEFAULT_TITLE_TMPL = '{{business.bk_biz_name}} - {{alarm.name}}{{alarm.display_type}}';

// 套餐内容初始化
export const mealDataInit = (): IMealData => ({
  pluginType: '',
  id: 0,
  name: '',
  notice: {
    // 告警通知
    alert: [
      {
        timeRange: ['00:00:00', '23:59:59'],
        notifyInterval: 120,
        intervalNotifyMode: 'standard',
        notifyConfig: [
          { level: 1, type: [] },
          { level: 2, type: [] },
          { level: 3, type: [] },
        ],
        key: random(10),
      },
    ],
    execution: [
      {
        riskLevel: 1,
        notifyConfig: [
          { phase: 3, type: [] },
          { phase: 2, type: [] },
          { phase: 1, type: [] },
        ],
      },
      {
        riskLevel: 2,
        notifyConfig: [
          { phase: 3, type: [] },
          { phase: 2, type: [] },
          { phase: 1, type: [] },
        ],
      },
      {
        riskLevel: 3,
        notifyConfig: [
          { phase: 3, type: [] },
          { phase: 2, type: [] },
          { phase: 1, type: [] },
        ],
      },
    ],
    template: [
      {
        signal: 'abnormal',
        messageTmpl: DEFAULT_MESSAGE_TMPL,
        titleTmpl: DEFAULT_TITLE_TMPL,
      },
      {
        signal: 'recovered',
        messageTmpl: DEFAULT_MESSAGE_TMPL,
        titleTmpl: DEFAULT_TITLE_TMPL,
      },
      {
        signal: 'closed',
        messageTmpl: DEFAULT_MESSAGE_TMPL,
        titleTmpl: DEFAULT_TITLE_TMPL,
      },
    ],
  },
  webhook: {
    // http回调
    res: {
      headers: [],
      queryParams: [],
      authorize: {
        authConfig: {},
        authType: 'none',
      },
      body: {
        dataType: 'default',
        contentType: 'default',
        content: '',
        params: [],
      },
      failedRetry: {
        maxRetryTimes: 2,
        needPoll: false,
        notifyInterval: 120,
        retryInterval: 2,
        timeout: 10,
      },
      url: '',
      method: 'GET',
    },
    riskLevel: 2,
    timeout: 10,
  },
  peripheral: {
    data: {
      formTemplateId: '',
      templateDetail: {},
    },
    riskLevel: 2,
    timeout: 10,
  },
});

// 将phase转成level
export const executionNotifyConfigChange = (notifyConfig: INoticeWayValue[], isExecution = true) => {
  if (isExecution) {
    if (notifyConfig) {
      return notifyConfig.map(item => ({
        ...item,
        level: item.phase,
      }));
    }
    return [
      { level: 1, notice_ways: [] },
      { level: 2, notice_ways: [] },
      { level: 3, notice_ways: [] },
    ];
  }
  if (notifyConfig) {
    return notifyConfig.map(item => ({
      ...item,
      phase: item.level,
    }));
  }
  return [
    { phase: 1, notice_ways: [] },
    { phase: 2, notice_ways: [] },
    { phase: 3, notice_ways: [] },
  ];
};
// 转换成后端参数
export const transformMealContentParams = (data: IMealData) => {
  if (data.pluginType === mealType.notice) {
    const noticeData = data.notice;
    return {
      templateDetail: {
        alert: noticeData.alert
          .sort((a, b) => (timeTransform(a.timeRange[0]) as number) - (timeTransform(b.timeRange[0]) as number))
          .map(alert => ({
            timeRange: (alert.timeRange as string[]).join('--'),
            notifyInterval: alert.notifyInterval * 60,
            intervalNotifyMode: alert.intervalNotifyMode,
            notifyConfig: alert.notifyConfig,
          })),
        execution: noticeData.execution.map(execution => ({
          riskLevel: execution.riskLevel,
          notify_config: execution.notifyConfig,
        })),
        template: noticeData.template.map(template => ({
          signal: template.signal,
          messageTmpl: template.messageTmpl,
          titleTmpl: template.titleTmpl,
        })),
      },
    };
  }
  if (data.pluginType === mealType.callback) {
    const webhookData = data.webhook;
    return {
      templateDetail: {
        method: webhookData.res.method,
        url: webhookData.res.url,
        headers: webhookData.res.headers,
        authorize: webhookData.res.authorize,
        body: webhookData.res.body,
        queryParams: webhookData.res.queryParams,
        needPoll: webhookData.res.failedRetry.needPoll,
        notifyInterval: webhookData.res.failedRetry.notifyInterval * 60,
        failedRetry: {
          isEnabled: true,
          maxRetryTimes: webhookData.res.failedRetry.maxRetryTimes,
          retryInterval: webhookData.res.failedRetry.retryInterval,
          timeout: webhookData.res.failedRetry.timeout,
        },
      },
      timeout: webhookData.timeout * 60,
    };
  }
  if (data.pluginType !== '') {
    const peripheralData = data.peripheral;
    return {
      templateDetail: peripheralData.data.templateDetail,
      templateId: peripheralData.data.formTemplateId,
      timeout: peripheralData.timeout * 60,
    };
  }
  return null;
};

// 套餐数据回填
export const mealContentDataBackfill = (data: any): IMealData => {
  const mealData: IMealData = mealDataInit();
  const { executeConfig } = data;
  mealData.id = data.pluginId;
  mealData.name = data.pluginName;
  mealData.pluginType = data.pluginType;
  if (data.pluginType === mealType.notice) {
    mealData.notice = {
      alert: executeConfig.templateDetail.alert.map((item, index) => ({
        timeRange: item.timeRange.split('--'),
        notifyInterval: item.notifyInterval / 60,
        intervalNotifyMode: item.intervalNotifyMode,
        notifyConfig: notifyConfigFill(item.notifyConfig),
        key: index === 0 ? mealData.notice.alert[0].key : random(10),
      })),
      execution: executeConfig.templateDetail.execution.map(item => ({
        ...item,
        notifyConfig: notifyConfigFill(item.notifyConfig, false),
      })),
      template: executeConfig.templateDetail.template,
    };
    return mealData;
  }
  if (data.pluginType === mealType.callback) {
    const { templateDetail } = executeConfig;
    mealData.webhook = {
      res: {
        headers: templateDetail.headers,
        queryParams: templateDetail.queryParams,
        authorize: templateDetail.authorize,
        body: templateDetail.body,
        failedRetry: {
          maxRetryTimes: templateDetail.failedRetry?.maxRetryTimes || 0,
          needPoll: !!templateDetail.needPoll,
          notifyInterval: (templateDetail.notifyInterval || 0) / 60,
          retryInterval: templateDetail.failedRetry?.retryInterval || 0,
          timeout: templateDetail.failedRetry?.timeout || 0,
        },
        url: templateDetail.url,
        method: templateDetail.method,
      },
      // riskLevel: data.riskLevel,
      timeout: executeConfig.timeout / 60,
    };
    return mealData;
  }
  if (data.pluginType !== '') {
    mealData.peripheral = {
      data: {
        templateDetail: executeConfig.templateDetail,
        formTemplateId: executeConfig?.templateId || '',
      },
      // riskLevel: data.riskLevel,
      timeout: executeConfig.timeout / 60,
    };
    return mealData;
  }
};

export const getNotifyConfig = notify_config => {
  return notify_config.map(notifyConfig => ({
    ...notifyConfig,
    notice_ways:
      notifyConfig?.notice_ways?.map(way => ({
        ...way,
        // 只有wxwork-bot和bkchat会有receivers
        // 其中wxwork-bot是input框，需要将数组receivers转换为逗号分隔的字符串
        receivers: way.name === robot.wxworkBot ? way.receivers.join(',') : way.receivers,
      })) || [],
  }));
};

// 应对接口返回的通知方式数据不完整的处理办法
export const notifyConfigFill = (notifyConfig: any[], isLevel = true) => {
  if (isLevel) {
    const defaultNotifyConfig = [
      { level: 1, type: [] },
      { level: 2, type: [] },
      { level: 3, type: [] },
    ];
    if (!notifyConfig.length) {
      return defaultNotifyConfig;
    }
    return defaultNotifyConfig.map(item => {
      const notifyConfigItem = notifyConfig.find(config => config.level === item.level);
      const obj: any = item;
      if (notifyConfigItem) {
        obj.level = notifyConfigItem.level;
        obj.type = notifyConfigItem.type;
        if (notifyConfigItem?.chatid) {
          obj.chatid = notifyConfigItem.chatid;
        }
      }
      return obj;
    });
  }
  const defaultNotifyConfig = [
    { phase: 1, type: [] },
    { phase: 2, type: [] },
    { phase: 3, type: [] },
  ];
  if (!notifyConfig.length) {
    return defaultNotifyConfig;
  }
  return defaultNotifyConfig.map(item => {
    const notifyConfigItem = notifyConfig.find(config => config.phase === item.phase);
    const obj: any = item;
    if (notifyConfigItem) {
      obj.phase = notifyConfigItem.phase;
      obj.type = notifyConfigItem.type;
      if (notifyConfigItem?.chatid) {
        obj.chatid = notifyConfigItem.chatid;
      }
    }
    return obj;
  });
};

// 其他传入后台参数(executeConfig外层的数据)
export const otherParams = (data: IMealData) => {
  if (data.pluginType === mealType.notice) {
    return {};
  }
  if (data.pluginType === mealType.callback) {
    return {
      riskLevel: data.webhook.riskLevel,
    };
  }
  if (data.pluginType !== '') {
    return {
      riskLevel: data.peripheral.riskLevel,
    };
  }
  return {};
};

export type ITimeValue = `${string}:${string}:${string}` | string;

const numberToStr = number => {
  if (number === 0) {
    return '00';
  }
  if (number < 10) {
    return `0${number}`;
  }
  return `${number}`;
};

export const timeTransform = (timeValue: number | string | unknown, isToStr = false, minIsMinute = false) => {
  if (isToStr) {
    if (minIsMinute) {
      const one = Math.floor(Number(timeValue) / 60);
      const two = Math.floor(Number(timeValue) - one * 60);
      return `${numberToStr(one)}:${numberToStr(two)}`;
    }
    const one = Math.floor(Number(timeValue) / 3600);
    const two = Math.floor((Number(timeValue) - one * 3600) / 60);
    const three = Math.floor(Number(timeValue) - one * 3600 - two * 60);
    return `${numberToStr(one)}:${numberToStr(two)}:${numberToStr(three)}`;
  }
  return (timeValue as ITimeValue).split(':').reduce((acc, cur, index) => {
    const time = Number(cur);
    if (minIsMinute) {
      if (index === 0) {
        acc += time * 60;
      }
      if (index === 1) {
        acc += time;
      }
    } else {
      if (index === 0) {
        acc += time * 60 * 60;
      }
      if (index === 1) {
        acc += time * 60;
      }
      if (index === 2) {
        acc += time;
      }
    }
    return acc;
  }, 0);
};

// 时间段重叠校验
export const timeRangeValidate = (allData: string[][], targetData: string[]) => {
  const oneDay = 24 * 60 * 60;
  const allDataTimeNumArr = allData.map(item => {
    const one = timeTransform(item[0]);
    const two = timeTransform(item[1]);
    if (one > two) {
      // 跨天
      return [one, Number(two) + oneDay];
    }
    // 不跨天
    return [one, two];
  });
  const one = timeTransform(targetData[0]);
  const two = timeTransform(targetData[1]);
  let targetDataTimeNumberArr = [];
  if (one > two) {
    // 跨天
    targetDataTimeNumberArr = [one, Number(two) + oneDay];
  } else {
    targetDataTimeNumberArr = [one, two];
  }
  const start = targetDataTimeNumberArr[0];
  const end = targetDataTimeNumberArr[1];
  return allDataTimeNumArr.every(item => {
    const itemStart = item[0] as number;
    const itemEnd = item[1] as number;
    if (itemEnd > oneDay) {
      return start > itemEnd - oneDay && end < itemStart;
    }
    // 非跨天
    return (
      (start < itemStart && end < itemStart) ||
      (start > itemEnd && (end > oneDay ? end - oneDay < itemStart : end > itemEnd))
    );
  });
};

// 新增默认时间段
export const defaultAddTimeRange = (allData: string[][], minIsMinute = false) => {
  const oneDay = minIsMinute ? 24 * 60 : 24 * 60 * 60;
  const alllDataNum = [];
  // 转换成秒
  allData.forEach(item => {
    const one = timeTransform(item[0], false, minIsMinute);
    const two = timeTransform(item[1], false, minIsMinute);
    if (one > two) {
      // 跨天的时间段分成连个时间段
      const oneArr = [0, two];
      const twoArr = [one, oneDay - 1];
      alllDataNum.push(oneArr);
      alllDataNum.push(twoArr);
    } else {
      alllDataNum.push([one, two]);
    }
  });
  // 按起始时间排序
  const allDataSort = alllDataNum.sort((a, b) => a[0] - b[0]);
  // 从第一开始查找间隔
  const allInterval = [];
  allDataSort.reduce((acc, cur, index) => {
    const one = acc;
    const two = cur;
    if (allDataSort.length > 1) {
      if (index > 0) {
        const isHasInterval = two[0] - one[1] > 2;
        if (one[0] > 2 && index === 1) {
          // 当第一起始时间段大于2
          allInterval.push([0, one[0] - 1]);
        }
        if (isHasInterval) {
          // 当包含间隔时
          allInterval.push([one[1] + 1, two[0] - 1]);
        }
        if (index === allDataSort.length - 1 && two[1] < oneDay - 2) {
          // 当最后一个时
          allInterval.push([two[1] + 1, oneDay - 1]);
        }
      }
    } else {
      const one = allDataSort[0][0];
      const two = allDataSort[0][1];
      if (one > 2) {
        allInterval.push([0, one - 1]);
      }
      if (two < oneDay - 2) {
        allInterval.push([two + 1, oneDay - 1]);
      }
    }
    return cur;
  }, []);
  return allInterval.map(item => [
    timeTransform(item[0], true, minIsMinute),
    timeTransform(item[1], true, minIsMinute),
  ]);
};
