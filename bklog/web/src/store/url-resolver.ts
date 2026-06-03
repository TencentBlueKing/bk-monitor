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

import { handleTransformToTimestamp, intTimestampStr } from '@/components/time-range/utils';

import { ConditionOperator } from './condition-operator';
import { BK_LOG_STORAGE } from './store.type';

import type { Route } from 'vue-router';

/**
 * 初始化App时解析URL中的参数
 * 对应结果映射到Store里面
 */
class RouteUrlResolver {
  private route;
  private resolver: Map<string, (_str: string) => unknown>;
  private paramSanitizers: Map<string, (val: unknown) => unknown>;
  private resolveFieldList: string[];

  constructor({ route, resolveFieldList }: { route: Route; resolveFieldList?: string[] }) {
    this.route = route;
    // eslint-disable-next-line
    this.resolver = new Map<string, (_str: string) => unknown>();
    this.paramSanitizers = new Map<string, (val: unknown) => unknown>();
    this.resolveFieldList = resolveFieldList ?? this.getDefaultResolveFieldList();
    this.setDefaultResolver();
    this.setDefaultSanitizers();
  }

  get query() {
    return this.route?.query ?? {};
  }

  public setDefaultResolveFieldList(val?) {
    this.resolveFieldList = val ?? this.getDefaultResolveFieldList();
  }

  public setResolver(key: string, fn: (_str: string) => unknown) {
    this.resolver.set(key, fn);

    if (!this.resolveFieldList.includes(key)) {
      this.resolveFieldList.push(key);
    }
  }

  /**
   * 将URL参数解析为store里面缓存的数据结构
   */
  public convertQueryToStore<T>(): T {
    return this.resolveFieldList.reduce((output, key) => {
      let value;
      try {
        value = this.resolver.get(key)?.(this.query?.[key]) ?? this.commonResolver(this.query?.[key]);
      } catch (error) {
        console.warn('route url resolver convertQueryToStore error', key, error);
        value = undefined;
      }

      if (value !== undefined) {
        const sanitizer = this.paramSanitizers.get(key);
        if (sanitizer) {
          value = sanitizer(value);
        }
      }

      if (value !== undefined) {
        output[key] = value;
      }

      return output;
    }, {}) as T;
  }

  /**
   * 需要清理URL参数时，获取默认的参数配置列表
   * @returns
   */
  public getDefUrlQuery(ignoreList: string[] = []) {
    const routeQuery = this.query;
    const appendParamKeys = [...this.resolveFieldList, 'end_time'].filter(f => !(ignoreList ?? []).includes(f));
    const undefinedQuery = appendParamKeys.reduce((out, key) => {
      out[key] = undefined;
      return out;
    }, {});
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
      'pid',
      BK_LOG_STORAGE.FAVORITE_ID,
      BK_LOG_STORAGE.HISTORY_ID,
    ];
  }

  /**
   * 通用解析器
   * 注意：Vue Router 3.x 的 route.query 已自动解码 URL 参数
   * 因此这里不需要再次调用 decodeURIComponent
   */
  private commonResolver(str, next?) {
    if (str !== undefined && str !== null) {
      // vue-router query 可能是 string | string[]
      const raw = Array.isArray(str) ? str[str.length - 1] : str;

      // 非字符串直接透传（尽量不因类型异常导致白屏）
      if (typeof raw !== 'string') {
        return next?.(raw) ?? raw;
      }

      let val = raw;
      try {
        val = decodeURIComponent(raw);
      } catch (error) {
        // URL 被截断或包含非法 % 序列时，decodeURIComponent 会抛 URIError
        // 这里兜底，保证不白屏：能解析多少算多少
        console.warn('route url resolver decodeURIComponent error', error);
        val = raw;
      }
      return next?.(val) ?? val;
    }

    return;
  }

  /**
   * 用于 URL query 中 JSON 参数解析（对象/数组/对象数组等）。
   * 关键点：优先直接 JSON.parse（避免对值里的 %xx 进行误解码），失败后再按需 decode 后重试。
   */
  private parseJsonParam<T>(raw: string, fallback: T, maxDepth = 3): T {
    let current = raw;

    for (let i = 0; i <= maxDepth; i++) {
      try {
        return JSON.parse(current) as T;
      } catch (e) {
        // parse 失败再尝试 decode；decode 失败直接返回 fallback
      }

      let decoded: string;
      try {
        decoded = decodeURIComponent(current);
      } catch (e) {
        return fallback;
      }

      if (decoded === current) {
        return fallback;
      }

      current = decoded;
    }

    return fallback;
  }

  private objectResolver(str) {
    return this.commonResolver(str, (val) => {
      try {
        if (typeof val !== 'string') {
          return val;
        }
        return this.parseJsonParam(val ?? '', val);
      } catch (error) {
        console.warn('route url resolver objectResolver error', error);
        return val;
      }
    });
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
   * 注意：Vue Router 已自动解码，无需再次 decodeURIComponent
   */
  private dateTimeRangeResolver(timeRange: string[]) {
    const decodeValue = timeRange.map((t) => {
      let r = t;
      try {
        r = decodeURIComponent(t);
      } catch (error) {
        console.warn('route url resolver dateTimeRangeResolver decode error', error);
        r = t;
      }
      return intTimestampStr(r);
    });

    const result: number[] = handleTransformToTimestamp(decodeValue as any, this.timeFormatResolver(this.query.format));
    return { start_time: result[0], end_time: result[1] };
  }

  /**
   * addition 条件解析器
   * Vue Router 已自动解码，无需再次 decodeURIComponent
   */
  private additionResolver(str) {
    return this.commonResolver(str, (value) => {
      if (value === undefined || value === null || value === '') {
        return [];
      }

      try {
        if (typeof value !== 'string') {
          return [];
        }
        const parsed = this.parseJsonParam<any[]>(value, []);
        return (parsed ?? []).map((val) => {
          const instance = new ConditionOperator(val);
          return instance.formatApiOperatorToFront(true);
        });
      } catch (e) {
        console.warn('additionResolver parse error:', e);
        return [];
      }
    });
  }

  private datePickerValueResolver() {
    return this.commonResolver(this.query.start_time, (value) => {
      const endTime = this.commonResolver(this.query.end_time) ?? value;
      return [intTimestampStr(value), intTimestampStr(endTime)];
    });
  }

  /**
   * addition 数组解析器
   * Vue Router 已自动解码，无需再次 decodeURIComponent
   */
  private additionArrayResolver(str) {
    if (!str) {
      return [];
    }

    try {
      const raw = Array.isArray(str) ? str[str.length - 1] : str;
      if (typeof raw !== 'string') {
        return [];
      }
      const parsed = this.parseJsonParam<any[]>(raw, []);
      return Array.isArray(parsed) ? parsed : [];
    } catch (e) {
      console.error(e);
      return [];
    }
  }

  private searchModeResolver() {
    const hasKeyword = this.query.keyword?.length;
    const additionArray = this.additionArrayResolver(this.query.addition).filter(
      str => str.length > 0 && str !== '' && str !== null && str !== undefined && str !== '',
    );
    const hasAddition = additionArray.length;
    const defValue = ['sql', 'ui'].includes(this.query.search_mode) ? this.query.search_mode : 'ui';

    if (['sql', 'ui'].includes(this.query.search_mode)) {
      return this.query.search_mode;
    }

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
    this.resolver.set('pid', this.objectResolver.bind(this));
    this.resolver.set('timeRange', this.dateTimeRangeResolver.bind(this));
    this.resolver.set('search_mode', this.searchModeResolver.bind(this));
    this.resolver.set('format', this.timeFormatResolver.bind(this));

    // datePicker默认直接获取URL中的 start_time, end_time
    this.resolver.set('datePickerValue', this.datePickerValueResolver.bind(this));

    this.resolver.set('start_time', (val) => {
      return this.commonResolver(val, (value) => {
        const endTime = this.commonResolver(this.query?.end_time) ?? value;
        return this.dateTimeRangeResolver([value, endTime]).start_time;
      });
    });

    this.resolver.set('end_time', (val) => {
      return this.commonResolver(val, (value) => {
        const startTime = this.commonResolver(this.query?.start_time) ?? value;
        return this.dateTimeRangeResolver([startTime, value]).end_time;
      });
    });
  }

  private stripQuoteArtifacts(val: string): string {
    return val.replace(/^["']+|["']+$/g, '').trim();
  }

  /**
   * 参数清洗器：对 resolver 解析后的值做格式校验，自动修正或丢弃不合法的值。
   * 主要用于防御外部系统构造的 URL 中混入 HTML 实体残留（如 &quot; → "）等脏数据。
   */
  private setDefaultSanitizers() {
    // timezone: IANA 时区格式 Region/City 或缩写如 UTC
    const timezonePattern = /^[A-Za-z][A-Za-z0-9_+-]*(\/[A-Za-z][A-Za-z0-9_+-]*)*$/;
    this.paramSanitizers.set('timezone', (val) => {
      if (typeof val !== 'string') return undefined;
      if (timezonePattern.test(val)) return val;
      const cleaned = this.stripQuoteArtifacts(val);
      return timezonePattern.test(cleaned) ? cleaned : undefined;
    });

    // bizId: 数字，支持负数
    this.paramSanitizers.set('bizId', (val) => {
      if (typeof val !== 'string') return val;
      if (/^-?\d+$/.test(val)) return val;
      const cleaned = this.stripQuoteArtifacts(val);
      return /^-?\d+$/.test(cleaned) ? cleaned : undefined;
    });

    // spaceUid: 字母、数字、下划线、连字符
    this.paramSanitizers.set('spaceUid', (val) => {
      if (typeof val !== 'string') return val;
      if (/^[a-zA-Z0-9_-]+$/.test(val)) return val;
      const cleaned = this.stripQuoteArtifacts(val);
      return /^[a-zA-Z0-9_-]+$/.test(cleaned) ? cleaned : undefined;
    });

    // search_mode: 白名单
    this.paramSanitizers.set('search_mode', (val) => {
      if (typeof val !== 'string') return undefined;
      return ['sql', 'ui'].includes(val) ? val : undefined;
    });

    // format: 日期格式仅允许合法字符集
    const formatPattern = /^[YMDHhmsS\-/:. ]+$/;
    this.paramSanitizers.set('format', (val) => {
      if (typeof val !== 'string') return val;
      if (formatPattern.test(val)) return val;
      const cleaned = this.stripQuoteArtifacts(val);
      return formatPattern.test(cleaned) ? cleaned : undefined;
    });

    // index_id: 纯数字或数字字符串
    this.paramSanitizers.set('index_id', (val) => {
      if (typeof val !== 'string') return val;
      if (/^\d+$/.test(val)) return val;
      const cleaned = val.replace(/[^\d]/g, '');
      return cleaned.length ? cleaned : undefined;
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

  /**
   * 将 Store 参数解析为 URL query 参数
   * 注意：Vue Router 3.x 的 router.push/replace({ query: {...} }) 会自动编码参数
   * 因此这里不需要手动调用 encodeURIComponent
   */
  resolveParamsToUrl() {
    const getJsonString = val => JSON.stringify(val);

    /**
     * 路由参数格式化字典函数
     * 不同的字段需要不同的格式化函数
     * Vue Router 会自动编码，无需手动 encodeURIComponent
     */
    const routeQueryMap = {
      host_scopes: (val) => {
        const isEmpty = !Object.keys(val ?? {}).some((k) => {
          if (typeof val[k] === 'object') {
            return Array.isArray(val[k]) ? val[k].length : Object.keys(val[k] ?? {}).length;
          }

          return val[k]?.length;
        });

        return isEmpty ? undefined : getJsonString(val);
      },
      // 注意：不要在这里 encodeURIComponent，vue-router 在生成 href / replace 时会自动编码
      // 这里提前编码会导致 URL 出现 %25... 的重复编码
      start_time: () => this.routeQueryParams.datePickerValue[0],
      end_time: () => this.routeQueryParams.datePickerValue[1],
      keyword: val => (/^\s*\*\s*$/.test(val) ? undefined : val),
      unionList: (val) => {
        if (this.routeQueryParams.isUnionIndex && val?.length) {
          return getJsonString(val);
        }

        return;
      },
      default: (val) => {
        if (typeof val === 'object' && val !== null) {
          if (Array.isArray(val) && val.length) {
            return getJsonString(val);
          }

          if (Object.keys(val).length) {
            return getJsonString(val);
          }

          return;
        }

        return val?.length ? val : undefined;
      },
    };

    const getRouteQueryValue = () => {
      return Object.keys(this.routeQueryParams)
        .filter((key) => {
          return !['ids', 'isUnionIndex', 'datePickerValue'].includes(key);
        })
        .reduce((result, key) => {
          const val = this.routeQueryParams[key];
          const valueFn = typeof routeQueryMap[key] === 'function' ? routeQueryMap[key] : routeQueryMap.default;
          const value = valueFn(val);
          const fieldName = this.storeFieldKeyMap[key] ?? key;
          result[fieldName] = value;
          return result;
        }, {});
    };

    return getRouteQueryValue();
  }
}

export default RouteUrlResolver;
export { RetrieveUrlResolver };
