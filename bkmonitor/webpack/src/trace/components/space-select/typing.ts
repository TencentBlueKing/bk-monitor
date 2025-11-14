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

import type { PropType } from 'vue';

import type { ISpaceItem } from 'monitor-common/typings';

export enum ETagsType {
  BCS = 'bcs' /** 容器项目 */,
  BKCC = 'bkcc' /** 业务 */,
  BKCI = 'bkci' /** 蓝盾项目 */,
  BKSAAS = 'bksaas' /** 蓝鲸应用 */,
  MONITOR = 'monitor' /** 监控空间 */,
}

export interface ILocalSpaceList extends ISpaceItem {
  hasData?: boolean;
  isCheck?: boolean;
  isSpecial?: boolean;
  name?: string;
  noAuth?: boolean;
  preciseMatch?: boolean;
  show?: boolean;
  tags?: ITagsItem[];
}
interface ITagsItem {
  id: string;
  name: string;
  type: ETagsType;
}

export const SPACE_SELECTOR_PROPS = {
  /* 当前选中的空间 */
  value: {
    type: Array as PropType<(number | string)[]>,
    default: () => [],
  },
  /* 当前的主空间（勾选的第一个空间） */
  currentSpace: {
    type: [Number, String],
    default: () => null,
  },
  /* 所有空间列表 */
  spaceList: {
    type: Array as PropType<ISpaceItem[]>,
    default: () => [],
  },
  /* 是否为多选 */
  multiple: {
    type: Boolean,
    default: true,
  },
  /* 是否包含我有权限的选项 */
  needAuthorityOption: {
    type: Boolean,
    default: true,
  },
  /* 是否包含我有告警的选项 */
  needAlarmOption: {
    type: Boolean,
    default: true,
  },
  /* 是否包含有权限的业务（最大20个）, 配置管理业务  告警接收业务  三个选项  */
  needDefaultOptions: {
    type: Boolean,
    default: false,
  },
  /* 禁用 */
  disabled: {
    type: Boolean,
    default: false,
  },
  /* 是否包含申请权限功能 */
  hasAuthApply: {
    type: Boolean,
    default: false,
  },
  isCommonStyle: {
    type: Boolean,
    default: true,
  },
  /* 是否包含我有故障的选项 */
  needIncidentOption: {
    type: Boolean,
    default: false,
  },
  /* 是否包含多选/单选切换按钮  multiple属性需替换成变量 */
  needChangeChoiceType: {
    type: Boolean,
    default: false,
  },
  /* 是否自动选择为当前空间（将空间添加到url上）单选时自动选择为当前空间, 多选时则（选择的第一个空间为当前空间） */
  isAutoSelectCurrentSpace: {
    type: Boolean,
    default: false,
  },
};
export const SPACE_SELECTOR_EMITS = {
  change: (_val: number[]) => true,
  applyAuth: (_val: (number | string)[]) => true,
  changeChoiceType: (_val: boolean) => true,
} as const;

export interface ITriggerSlotOptions {
  active: boolean;
  disabled: boolean;
  error: boolean;
  multiple: boolean;
  valueStr: string;
  valueStrList: { id: string; name: string }[];
  clear: () => void;
}
