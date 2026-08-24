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
/** RUM 检索的三个视角，当前仅 span 视角有实现 */
export type RumMode = 'session' | 'span' | 'view';

export const RUM_MODE_LIST: RumMode[] = ['session', 'view', 'span'];

/** 应用列表项，字段取自 rum/meta/application/list_application */
export interface IRumApplication {
  [key: string]: any;
  app_alias: string;
  app_name: string;
  application_id: number;
  data_status: 'disabled' | 'no_data' | 'normal';
  /** 前端本地标记，非接口字段：是否被用户置顶 */
  isTop?: boolean;
}

/** 驱动列表 / 维度统计 / 字段候选值的公共查询参数 */
export interface IRumCommonParams {
  app_name: string;
  filters: IRumFilter[];
  mode: RumMode;
  query_string: string;
}

/** 后端约定的过滤条件结构，见接口协议 1.1 Filter */
export interface IRumFilter {
  key: string;
  operator: string;
  value: Array<boolean | number | string>;
  options?: {
    group_relation?: 'AND' | 'OR';
    is_wildcard?: boolean;
  };
}

/** 绝大多数检索接口的入参 = 公共查询参数 + 时间区间 */
export type IRumQueryParams = IRumCommonParams & IRumTimeRange;

/** 秒级时间戳区间 */
export interface IRumTimeRange {
  end_time: number;
  start_time: number;
}
