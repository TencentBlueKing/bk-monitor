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
import { shallowRef } from 'vue';

import { createGlobalState } from '@vueuse/core';

import type { TapdRelationItem } from '../../services/relation-tapd';
import type { IssueActivityItem } from '../../typing/detail';

export type TTapdIssueActivities = { issueId: string; list: IssueActivityItem[] };
export type TTapdIssueInfos = { issueId: string; list: TapdRelationItem[] };

/**
 * @description TAPD 单据操作（创建/关联）成功后，后端返回的活动记录全局状态
 *
 * 用于在 TAPD 侧滑栏关闭后，将活动记录回写到 Issue 详情页的「活动」Tab 列表中，
 * 通过 createGlobalState 实现跨组件（sideslider → slider-wrapper）的状态共享。
 */
export const useTapdIssueActivities = createGlobalState(() => {
  /** 当前 issueId 对应的 TAPD 活动记录列表，null 表示无数据 */
  const activities = shallowRef<TTapdIssueActivities>(null);
  const infos = shallowRef<TTapdIssueInfos>(null);

  /**
   * 设置指定 issue 的 TAPD 活动
   * @param data 包含 issueId 和对应活动记录的数据
   */
  const setActivities = (data: TTapdIssueActivities) => {
    activities.value = data;
  };
  const setInfos = (data: TTapdIssueInfos) => {
    infos.value = data;
  };
  return { activities, infos, setActivities, setInfos };
});
