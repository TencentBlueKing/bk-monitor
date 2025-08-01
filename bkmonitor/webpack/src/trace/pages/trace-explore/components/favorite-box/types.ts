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

import type { EMode, IWhereItem } from '../../../../components/retrieval-filter/typing';
import type { TimeRangeType } from '../../../../components/time-range/utils';

export type IFavorite = keyof FavoriteConfigMap;
export interface IFavoriteGroup<T extends IFavorite | unknown = unknown> {
  editable: string;
  id: number;
  name: string;
  favorites: {
    config: T extends IFavorite ? FavoriteConfigMap[T] : unknown;
    create_user: string;
    group_id: number;
    id: number;
    name: string;
    update_time: string;
    update_user: string;
  }[];
}
type FavoriteConfigMap = {
  event: IEventFavoriteConfig;
  metric: IMetricFavoriteConfig;
  trace: ITraceFavoriteConfig;
};

interface IEventFavoriteConfig {
  bk_biz_id: number;
  compareValue: {
    compare: {
      type: string;
      value: boolean;
    };
    tools: {
      refleshInterval: number;
      timeRange: [string, string];
      timezone: string;
    };
  };
  queryConfig: {
    commonWhere?: any[];
    data_source_label: string;
    data_type_label: string;
    metric_field: string;
    metric_field_cache: string;
    query_string: string;
    result_table_id: string;
    where: any[];
  };
}

interface IMetricFavoriteConfig {
  localValue?: Record<string, any>[];
  compareValue?: {
    compare: {
      type: string;
      value: boolean;
    };
    target: Record<string, any>;
    tools: {
      refleshInterval: number;
      timeRange: [string, string];
      timezone: string;
    };
  };
  promqlData?: {
    alias: string;
    code: string;
    enable: boolean;
    errMsg: string;
    key: string;
    step: string;
  }[];
}

interface ITraceFavoriteConfig {
  bk_biz_id: number;
  componentData: {
    commonWhere: IWhereItem[];
    filterMode: EMode;
    mode: 'span' | 'trace';
    refreshInterval: number;
    timeRange: TimeRangeType;
  };
  queryParams: {
    app_name: string;
    end_time: string;
    filters: any[];
    mode: string;
    query: string;
    sort?: string[];
    start_time: string;
  };
}
