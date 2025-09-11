/* eslint-disable @typescript-eslint/naming-convention */
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

import { random } from 'monitor-common/utils';

import type { MetricDetailV2 } from './metric';

// 聚合条件接口
export interface AggCondition {
  condition?: string;
  dimension_name?: string;
  key: string;
  method?: string;
  value?: string[];
}

// 聚合函数接口
export interface AggFunction {
  id: string;
  name?: string;
  params: {
    id: string;
    value: string;
  }[];
}

export class QueryConfig {
  /** 聚合条件 */
  agg_condition: AggCondition[] = [];
  /** 聚合维度 */
  agg_dimension: string[] = [];
  /** 聚合间隔 */
  agg_interval: number | string;
  /** 聚合方法 */
  agg_method: string;
  /** 别名  a-z 字符*/
  alias: string;
  /** 函数列表 */
  functions: AggFunction[];
  /** 查询配置ID */
  id: number;
  /** 索引集ID */
  index_set_id: number;
  /* key */
  key: string = random(8);
  /** 指标ID */
  metric_id: string;
  /** 查询字符串 */
  query_string: string;
  /** 时间字段 */
  time_field: string;

  constructor(
    public readonly metricDetail: MetricDetailV2,
    data?: Partial<QueryConfig>
  ) {
    if (metricDetail?.metric_id) {
      this.metricDetail = metricDetail;
      this.agg_dimension = metricDetail.default_dimensions || [];
      this.agg_condition =
        metricDetail.result_table_label === 'uptimecheck'
          ? metricDetail.related_id
            ? metricDetail.default_condition || []
            : []
          : metricDetail.default_condition || [];
      this.functions = [];
    }
    if (data?.metric_id) {
      Object.assign(this, data);
    }
    if (data?.alias) {
      this.alias = data.alias;
    }
    // 聚合周期初始化兼容处理
    if (this.agg_interval === 'auto' || !this.agg_interval) {
      this.agg_interval = 60;
    } else if (typeof this.agg_interval === 'string') {
      this.agg_interval = this.agg_interval.includes('m')
        ? +this.agg_interval.replace(/m/gi, '')
        : +this.agg_interval.replace(/s/gi, '');
    }
    if (this.agg_method) {
      if (this.agg_method?.match(/_TIME$/)) {
        // 兼容老版本数据
        this.agg_method = this.agg_method.toLocaleLowerCase();
      }
    } else {
      this.agg_method = 'AVG';
    }

    // 处理日志关键字指标ID脏数据
    if (this.metricDetail?.metricMetaId === 'bk_log_search|log' && this.agg_method === 'COUNT') {
      const list = this.metric_id.toString().split('.');
      if (list.length > 3) {
        this.metric_id = list.slice(0, 3).join('.');
      }
    }
  }
  get data_source_label() {
    return this.metricDetail.data_source_label;
  }
  get data_type_label() {
    return this.metricDetail.data_type_label;
  }
  get result_table_id() {
    return this.metricDetail.result_table_id;
  }
}
