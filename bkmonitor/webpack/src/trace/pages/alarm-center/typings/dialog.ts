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
import type { AlarmShieldDetail } from './shield';

/** 一键拉群 dialog 组件所需私有参数 */
export interface AlertChartDialogParams {
  /** 需要拉群讨论的 告警事件名称（选择多个告警事件时可不填） */
  alertName?: string;
  /** 需要拉群讨论的 告警事件 责任人 */
  assignee?: string[];
}

/** 告警确认 dialog 组件 确认提交成功后回调事件对象 */
export type AlertConfirmDialogEvent = boolean;

/** 告警分派 dialog 组件 派单提交成功后回调事件对象 */
export type AlertDispatchDialogEvent = string[];

/** 告警 各操作 dialog 组件 回调事件对象 */
export type AlertOperationDialogEvent = AlertConfirmDialogEvent | AlertDispatchDialogEvent | AlertShieldDialogEvent;
/** 告警 各操作 dialog 组件所需的非公共私有参数 */
export type AlertOperationDialogParams = AlertChartDialogParams & AlertShieldDialogParams;
/** 告警屏蔽 dialog 组件 屏蔽提交成功后回调事件对象 */
export type AlertShieldDialogEvent = boolean;

/** 报警屏蔽dialog 组件所需私有参数 */
export interface AlertShieldDialogParams {
  /** dialog 中 屏蔽内容 信息 */
  alarmShieldDetail?: AlarmShieldDetail[];
}
