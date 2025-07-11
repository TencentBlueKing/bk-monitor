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

// @ts-ignore
import { handleTransformToTimestamp, intTimestampStr } from '@/components/time-range/utils';

import { ConditionOperator } from './condition-operator';
import { Route } from 'vue-router';
import { BK_LOG_STORAGE } from './store.type';

/**
 * 初始化App时解析URL中的参数
 * 对应结果映射到Store里面
 */
class RouteUrlResolver {
  private route;
  private resolver: Map<string, (str) => unknown>;
  private resolveFieldList: string[];

  constructor({ route, resolveFieldList }: { route: Route; resolveFieldList?: string[] }) {
    this.route = route;
    this.resolver = new Map<string, (str) => unknown>();
    this.resolveFieldList = resolveFieldList ?? this.getDefaultResolveFieldList();
    this.setDefaultResolver();
  }

  get query() {
    return this.route?.query ?? {};
  }

  public setDefaultResolveFieldList(val?) {
    this.resolveFieldList = val ?? this.getDefaultResolveFieldList();
  }

  public setResolver(key: string, fn: (str) => unknown) {
    this.resolver.set(key, fn);
  }

  /**
   * 将URL参数解析为store里面缓存的数据结构
   */
  public convertQueryToStore<T>(): T {
    return this.resolveFieldList.reduce((output, key) => {
      const value = this.resolver.get(key)?.(this.query?.[key]) ?? this.commonResolver(this.query?.[key]);
      if (value !== undefined) {
        return Object.assign(output, { [key]: value });
      }

      return output;
    }, {}) as T;
  }

  /**
   * 需要清理URL参数时，获取默认的参数配置列表
   * @returns
   */
  public getDefUrlQuery(ignoreList = []) {
    const routeQuery = this.query;
    const appendParamKeys = [...this.resolveFieldList, 'end_time'].filter(f => !(ignoreList ?? []).includes(f));
    const undefinedQuery = appendParamKeys.reduce((out, key) => Object.assign(out, { [key]: undefined }), {});
    return {
      ...routeQuery,
      ...undefinedQuery,
    };
  }

  private getDefaultResolveFieldList() {
    // 这里start_time 和 end_time 是一对，用于时间日期选择器
    // 所以如果解析必须要以 [start_time, end_time] 格式
    return [
      'addition',
      'keyword',
      'start_time',
      'end_time',
      'timezone',
      'unionList',
      'datePickerValue',
      'host_scopes',
      'ip_chooser',
      'search_mode',
      'clusterParams',
      'bizId',
      'spaceUid',
      'format',
      'index_id',
      BK_LOG_STORAGE.FAVORITE_ID,
      BK_LOG_STORAGE.HISTORY_ID,
    ];
  }

  private commonResolver(str, next?) {
    if (str !== undefined && str !== null) {
      const val = decodeURIComponent(str);
      return next?.(val) ?? val;
    }

    return undefined;
  }

  private objectResolver(str) {
    return this.commonResolver(str, val => JSON.parse(decodeURIComponent(val)));
  }

  private arrayResolver(str) {
    return this.objectResolver(str);
  }

  private timeFormatResolver(str) {
    if (str === undefined || str === null || str === '') {
      return 'YYYY-MM-DD HH:mm:ss';
    }

    return str;
  }

  /**
   * datepicker时间范围格式化为标准时间格式
   * @param timeRange [start_time, end_time]
   */
  private dateTimeRangeResolver(timeRange: string[]) {
    const decodeValue = timeRange.map(t => {
      const r = decodeURIComponent(t);
      return intTimestampStr(r);
    });

    const result: number[] = handleTransformToTimestamp(decodeValue, this.timeFormatResolver(this.query.format));
    return { start_time: result[0], end_time: result[1] };
  }

  private additionResolver(str) {
    return this.commonResolver(str, value => {
      if (value === undefined || value === null || value === '') {
        return [];
      }

      return (JSON.parse(decodeURIComponent(value)) ?? []).map(val => {
        const instance = new ConditionOperator(val);
        return instance.formatApiOperatorToFront(true);
      });
    });
  }

  private datePickerValueResolver() {
    return this.commonResolver(this.query.start_time, value => {
      const endTime = this.commonResolver(this.query.end_time) ?? value;
      return [intTimestampStr(value), intTimestampStr(endTime)];
    });
  }

  private searchModeResolver() {
    const hasAddition = this.query.keyword?.length;
    const hasKeyword = this.query.addition?.length;
    const defValue = ['sql', 'ui'].includes(this.query.search_mode) ? this.query.search_mode : 'ui';

    if (hasAddition && hasKeyword) {
      return defValue;
    }

    if (this.query.keyword?.length) {
      return 'sql';
    }

    if (this.query.addition?.length) {
      return 'ui';
    }

    return defValue;
  }

  private setDefaultResolver() {
    this.resolver.set('addition', this.additionResolver.bind(this));
    this.resolver.set('unionList', this.arrayResolver.bind(this));
    this.resolver.set('host_scopes', this.objectResolver.bind(this));
    this.resolver.set('ip_chooser', this.objectResolver.bind(this));
    this.resolver.set('clusterParams', this.objectResolver.bind(this));
    this.resolver.set('timeRange', this.dateTimeRangeResolver.bind(this));
    this.resolver.set('search_mode', this.searchModeResolver.bind(this));
    this.resolver.set('format', this.timeFormatResolver.bind(this));

    // datePicker默认直接获取URL中的 start_time, end_time
    this.resolver.set('datePickerValue', this.datePickerValueResolver.bind(this));

    this.resolver.set('start_time', val => {
      return this.commonResolver(val, value => {
        const end_time = this.commonResolver(this.query?.end_time) ?? value;
        return this.dateTimeRangeResolver([value, end_time]).start_time;
      });
    });

    this.resolver.set('end_time', val => {
      return this.commonResolver(val, value => {
        const start_time = this.commonResolver(this.query?.start_time) ?? value;
        return this.dateTimeRangeResolver([start_time, value]).end_time;
      });
    });
  }
}

/**
 * Store 中的参数解析为URL参数
 * 用于默认初始化或者解析Store中的参数更新到URL中
 */
class RetrieveUrlResolver {
  routeQueryParams;
  storeFieldKeyMap;
  constructor(params) {
    this.routeQueryParams = params;
    // store中缓存的字段和URL中参数的字段key映射
    this.storeFieldKeyMap = {
      bk_biz_id: 'bizId',
    };
  }

  resolveParamsToUrl() {
    const getEncodeString = val => JSON.stringify(val);

    /**
     * 路由参数格式化字典函数
     * 不同的字段需要不同的格式化函数
     */
    const routeQueryMap = {
      host_scopes: val => {
        const isEmpty = !Object.keys(val ?? {}).some(k => {
          if (typeof val[k] === 'object') {
            return Array.isArray(val[k]) ? val[k].length : Object.keys(val[k] ?? {}).length;
          }

          return val[k]?.length;
        });

        return isEmpty ? undefined : getEncodeString(val);
      },
      start_time: () => this.routeQueryParams.datePickerValue[0],
      end_time: () => this.routeQueryParams.datePickerValue[1],
      keyword: val => (/^\s*\*\s*$/.test(val) ? undefined : val),
      unionList: val => {
        if (this.routeQueryParams.isUnionIndex && val?.length) {
          return getEncodeString(val);
        }

        return undefined;
      },
      default: val => {
        if (typeof val === 'object' && val !== null) {
          if (Array.isArray(val) && val.length) {
            return getEncodeString(val);
          }

          if (Object.keys(val).length) {
            return getEncodeString(val);
          }

          return undefined;
        }

        return val?.length ? val : undefined;
      },
    };

    const getRouteQueryValue = () => {
      return Object.keys(this.routeQueryParams)
        .filter(key => {
          return !['ids', 'isUnionIndex', 'datePickerValue'].includes(key);
        })
        .reduce((result, key) => {
          const val = this.routeQueryParams[key];
          const valueFn = typeof routeQueryMap[key] === 'function' ? routeQueryMap[key] : routeQueryMap.default;
          const value = valueFn(val);
          const fieldName = this.storeFieldKeyMap[key] ?? key;
          return Object.assign(result, { [fieldName]: value });
        }, {});
    };

    return getRouteQueryValue();
  }
}

export default RouteUrlResolver;
export { RetrieveUrlResolver };
