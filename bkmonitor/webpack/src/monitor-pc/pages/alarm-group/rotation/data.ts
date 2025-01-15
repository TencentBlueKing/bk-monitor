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
/* 后台数据转换部分 */
/* 将值班通知设置组件数据转为后台接口参数 */
export function dutyNoticeConfigToParams(data) {
  const typeMap = {
    week: 'weekly',
    month: 'monthly',
  };
  const hoursAgo = (() => {
    if (data.timeType === 'week') {
      return data.startNum * 24 * 7;
    }
    return data.startNum * 24;
  })();
  return {
    plan_notice: {
      enabled: data.isSend, // 是否发送
      days: data.nearDay, // 发送多久以后得
      chat_ids: data.rtxId.split(','),
      type: typeMap[data.sendType],
      date: typeMap[data.sendType] === 'weekly' ? data.week : data.month,
      time: data.sendTime,
    },
    personal_notice: {
      enabled: data.needNotice,
      hours_ago: hoursAgo,
      duty_rules: data.rotationId,
    },
  };
}
/* 将后台数据转换为组件数据 */
export function paramsToDutyNoticeConfig(dutyNotice) {
  const typeMap = {
    weekly: 'week',
    monthly: 'month',
  };
  const hoursAgo = (() => {
    const days = dutyNotice.personal_notice.hours_ago / 24;
    if (days % 7 === 0) {
      return {
        timeType: 'week',
        startNum: days / 7,
      };
    }
    return {
      timeType: 'day',
      startNum: days,
    };
  })();
  return {
    isSend: dutyNotice.plan_notice.enabled,
    sendType: typeMap[dutyNotice.plan_notice.type],
    week: dutyNotice.plan_notice.type === 'weekly' ? dutyNotice.plan_notice.date : 1,
    month: dutyNotice.plan_notice.type === 'monthly' ? dutyNotice.plan_notice.date : 1,
    sendTime: dutyNotice.plan_notice.time,
    nearDay: dutyNotice.plan_notice.days,
    rtxId: dutyNotice.plan_notice.chat_ids.join(','),
    needNotice: dutyNotice.personal_notice.enabled,
    startNum: hoursAgo.startNum,
    timeType: hoursAgo.timeType,
    rotationId: dutyNotice.personal_notice.duty_rules,
  };
}
