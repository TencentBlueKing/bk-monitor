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

/** 「未分组的指标」固定分组 id，始终置底且不可拖拽/删除 */
export const UNGROUP_ID = '__UNGROUP__';

/** 分组的可见/隐藏指标数量统计 */
export interface MetricGroupCount {
  /** 隐藏指标数 */
  hidden: number;
  /** 可见指标数 */
  visible: number;
}

/** 指标分组 */
export interface MetricGroupModel {
  /** 分组唯一标识 */
  id: string;
  /** 分组标题，如 CPU、网络 */
  title: string;
}

/** 单个指标 */
export interface MetricItemModel {
  /** 所属分组 id，UNGROUP_ID 表示未分组 */
  groupId: string;
  /** 是否隐藏（显示开关关闭） */
  hidden: boolean;
  /** 指标唯一标识 */
  id: string;
  /** 指标名称 */
  title: string;
}
