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

import { alertTopN, listAlertTags } from 'monitor-api/modules/alert';
import { getAssignConditionKeys, searchObjectAttribute } from 'monitor-api/modules/assign';
import { listEventPlugin } from 'monitor-api/modules/event_plugin';
import { getVariableValue } from 'monitor-api/modules/grafana';
import { groupsIpChooserDynamicGroup, listUsersUser } from 'monitor-api/modules/model';
import { getMetricListV2, getScenarioList, getStrategyV2, plainStrategyList } from 'monitor-api/modules/strategies';
import {
  type IFilterField,
  type IGetValueFnParams,
  type IOptionsInfo,
  type IValue,
  type TTagValueDisplayFormatter,
  EFieldType,
} from 'trace/components/retrieval-filter/typing';
import { handleTransformToTimestamp } from 'trace/components/time-range/utils';

/* 需要拉取 CMDB 子选项的 key，子选项通过 searchObjectAttribute 获取，自身不放入 fields */
const CMDB_CHILD_KEYS = ['set', 'module', 'host'];
/* 需要拉取告警标签子选项的 key，子选项通过 listAlertTags 获取，自身不放入 fields */
const TAGS_CHILD_KEYS = ['dimensions'];

/* 不需要出现在 fields 中的 key */
const EXCLUDE_KEYS = ['tags'];

/* 策略标签 key（对应 alertTopN 的 labels 字段） */
const STRATEGY_LABELS_KEY = 'labels';
/* 与后端 AlertTopNResource.MAX_NESTED_TOP_N_FIELDS 保持同步 */
const TAG_FIELD_BATCH_SIZE = 20;

/* keyword 类型字段支持的通用操作符 */
const KEYWORD_METHODS: IFilterField['methods'] = [
  { value: 'eq', alias: 'in' },
  { value: 'neq', alias: 'not in' },
  { value: 'include', alias: 'like' },
  { value: 'exclude', alias: 'not like' },
  { value: 'reg', alias: 'regex' },
  { value: 'nreg', alias: 'nregex' },
  { value: 'issuperset', alias: '⊇' },
];
/** 普通 key 转换为检索过滤器字段 */
const toField = (key: string, alias: string): IFilterField => ({
  alias,
  name: key,
  type: EFieldType.keyword,
  isEnableOptions: true,
  methods: KEYWORD_METHODS,
});

/** 子选项归一化中间结构 */
type TChildOption = { id: string; name: string };

/** CMDB 子选项转换（与 monitor-pc setCMDBOptions 返回结构一致） */
const toCMDBChild = (parentKey: string, child: { bk_property_id: string; bk_property_name: string }): TChildOption => ({
  id: `${parentKey}.${child.bk_property_id}`,
  name: child.bk_property_name,
});
/** 告警标签子选项转换（与 monitor-pc groupKeys 中 dimensions 子项结构一致） */
const toTagsChild = (child: { id: string; name: string }): TChildOption => ({
  id: child.id,
  name: child.name,
});

/** topN 接口部分数据需去掉首尾双引号 */
const topNDataStrTransform = (value: string) => value.replace(/(^")|("$)/g, '');

const chunkFields = <T>(fields: T[], size: number): T[][] => {
  if (!fields.length) return [];
  const chunks: T[][] = [];
  for (let index = 0; index < fields.length; index += size) {
    chunks.push(fields.slice(index, index + size));
  }
  return chunks;
};

/**
 * @description 匹配规则组件的字段与候选值逻辑
 * 拉取告警策略匹配条件 key 并构造检索过滤器所需的 fields，
 * 同时并行拉取所有字段的候选值（valueMap），并提供检索过滤器所需的 getValueFn。
 * 候选值接口参考 monitor-pc alarm-dispatch 的 allKVOptions。
 */
export const useMatchRuleFields = () => {
  /** 检索过滤器字段列表 */
  const fields = shallowRef<IFilterField[]>([]);
  /** 字段名 -> 候选值列表 */
  const valueMap = shallowRef<Map<string, IValue[]>>(new Map());
  /** 总数据加载状态（fields 与候选值） */
  const loading = shallowRef(false);
  /**
   * 策略维度候选值缓存
   * key 为 `alert.strategy_id=<id>`，命中后直接复用，避免重复请求
   */
  const strategySpecialOptions = new Map<string, Map<string, IValue[]>>();

  /**
   * 拉取并构造 fields
   * @param range 时间窗 [start, end]
   * @param bkBizIds 业务 ID 列表
   */
  const fetchFields = async (range: [number, number], bkBizIds: number[]) => {
    // 主 key 列表
    let keys: any[] = [];
    // 父 key -> 归一化子选项列表（每个接口返回结构不同，各自在 then 里处理）
    const childMap: Record<string, TChildOption[]> = {};

    await Promise.all([
      // 主 key 列表：直接赋值，遍历时再决定如何展开
      getAssignConditionKeys().then((data: any[]) => {
        keys = data;
      }),
      // CMDB 子选项：searchObjectAttribute 返回 bk_property_id / bk_property_name
      ...CMDB_CHILD_KEYS.map(key =>
        searchObjectAttribute({ bk_obj_id: key })
          .then((data: any[]) => {
            childMap[key] = data.map(child => toCMDBChild(key, child));
          })
          .catch(() => {
            childMap[key] = [];
          })
      ),
      // 告警标签子选项：listAlertTags 返回 id / name
      ...TAGS_CHILD_KEYS.map(() =>
        listAlertTags({
          conditions: [],
          query_string: '',
          status: [],
          start_time: range[0],
          end_time: range[1],
          bk_biz_ids: bkBizIds,
        })
          .then((data: any[]) => {
            childMap[TAGS_CHILD_KEYS[0]] = data.map(child => toTagsChild(child));
          })
          .catch(() => {
            childMap[TAGS_CHILD_KEYS[0]] = [];
          })
      ),
    ]);

    const result: IFilterField[] = [];
    for (const item of keys) {
      // 含子选项的 key 仅展开子选项，自身不放入 fields
      if (childMap[item.key]) {
        result.push(...childMap[item.key].map(child => toField(child.id, `[${item.display_key}]${child.name}`)));
        continue;
      }
      // 其余 key 直接作为字段（过滤掉不需要的 key）
      if (EXCLUDE_KEYS.includes(item.key)) continue;
      result.push(toField(item.key, item.display_key));
    }
    // 动态分组：后端 key 列表中不包含，需手动追加（与 monitor-pc alarm-dispatch 保持一致）
    result.push(toField('dynamic_group', window.i18n.t('动态分组')));
    fields.value = result;
  };

  /**
   * 并行拉取所有字段的候选值
   * @param range 时间窗 [start, end]
   * @param bkBizIds 业务 ID 列表
   */
  const fetchOptions = async (range: [number, number], bkBizIds: number[]) => {
    const map = new Map<string, IValue[]>();

    await Promise.all([
      // 动态分组
      groupsIpChooserDynamicGroup({ scope_list: [{ scope_id: bkBizIds[0], scope_type: 'biz' }] })
        .then(data => {
          map.set(
            'dynamic_group',
            data.map(item => ({ id: item.id, name: item.name }))
          );
        })
        .catch(() => {}),
      // 第三方告警源
      listEventPlugin()
        .then(res => {
          const plugins = [
            { id: 'bkmonitor', name: window.i18n.t('监控策略') },
            ...(res.list || []).map(item => ({ id: item.plugin_id, name: item.plugin_display_name })),
          ];
          map.set('alert.event_source', plugins);
        })
        .catch(() => {}),
      // 监控对象
      getScenarioList()
        .then(res => {
          const list: IValue[] = [];
          for (const item of res || []) {
            for (const child of item.children || []) {
              list.push({ id: child.id, name: child.name });
            }
          }
          map.set('alert.scenario', list);
        })
        .catch(() => {}),
      // 告警策略列表
      plainStrategyList()
        .then(res => {
          map.set(
            'alert.strategy_id',
            (res || []).map(item => ({ id: String(item.id), name: item.name }))
          );
        })
        .catch(() => {}),
      // 指标
      getMetricListV2({ conditions: [{ key: 'query', value: '' }], page: 1, page_size: 1000, tag: '' })
        .then(data => {
          map.set(
            'alert.metric',
            (data.metric_list || []).map(m => ({ id: m.metric_id, name: m.name }))
          );
        })
        .catch(() => {}),
      // 告警名称 / 告警 IP / 云区域 ID
      alertTopN({
        bk_biz_ids: bkBizIds,
        conditions: [],
        query_string: '',
        status: [],
        fields: ['alert_name', 'ip', 'bk_cloud_id'],
        size: 10,
        start_time: range[0],
        end_time: range[1],
      })
        .then(data => {
          for (const fieldData of data.fields || []) {
            const isChar = fieldData.is_char;
            const buckets = (fieldData.buckets || []).map(b => ({
              id: isChar ? topNDataStrTransform(b.id) : b.id,
              name: b.name,
            }));
            if (fieldData.field === 'ip') map.set('ip', buckets);
            if (fieldData.field === 'bk_cloud_id') map.set('bk_cloud_id', buckets);
            if (fieldData.field === 'alert_name') map.set('alert.name', buckets);
          }
        })
        .catch(() => {}),
      // 策略标签
      alertTopN({
        bk_biz_ids: bkBizIds,
        conditions: [],
        query_string: '',
        status: [],
        fields: [STRATEGY_LABELS_KEY],
        size: 10,
        start_time: range[0],
        end_time: range[1],
      })
        .then(data => {
          for (const t of data.fields || []) {
            if (t.field === STRATEGY_LABELS_KEY) {
              const isChar = t.is_char;
              map.set(
                STRATEGY_LABELS_KEY,
                (t.buckets || []).map(b => ({ id: isChar ? topNDataStrTransform(b.id) : b.id, name: b.name }))
              );
            }
          }
        })
        .catch(() => {}),
      // 通知人员是否为空（固定布尔候选值）
      Promise.resolve().then(() => {
        map.set('is_empty_users', [
          { id: 'true', name: 'true' },
          { id: 'false', name: 'false' },
        ]);
      }),
      // 通知人员
      listUsersUser({ app_code: 'bk-magicbox', page: 1, page_size: 20, fuzzy_lookups: '' })
        .then(data => {
          map.set(
            'notice_users',
            (data.results || []).map(item => ({ id: item.username, name: item.display_name }))
          );
        })
        .catch(() => {}),
      // CMDB 集群 / 模块 / 主机 子选项
      ...CMDB_CHILD_KEYS.map(key =>
        searchObjectAttribute({ bk_obj_id: key })
          .then(data => {
            for (const d of data || []) {
              const fieldKey = `${key}.${d.bk_property_id}`;
              if (Array.isArray(d.option)) {
                map.set(
                  fieldKey,
                  d.option.map(o => (typeof o === 'string' ? { id: o, name: o } : { id: o.id, name: o.name }))
                );
              }
            }
          })
          .catch(() => {})
      ),
    ]);

    // dimensions 标签子选项：先取标签，再对每个标签取 topN 候选值
    const tags = await listAlertTags({
      conditions: [],
      query_string: '',
      status: [],
      start_time: range[0],
      end_time: range[1],
      bk_biz_ids: bkBizIds,
    }).catch(() => [] as { id: string; name: string }[]);

    const topNData = await Promise.all(
      chunkFields(
        tags.map(t => t.id),
        TAG_FIELD_BATCH_SIZE
      ).map(fields =>
        alertTopN({
          bk_biz_ids: bkBizIds,
          conditions: [],
          query_string: '',
          status: [],
          fields,
          size: 10,
          start_time: range[0],
          end_time: range[1],
        })
          .then(data => data?.fields || [])
          .catch(() => [])
      )
    ).then(data => data.flat());

    for (const t of topNData) {
      const isChar = t.is_char;
      map.set(
        t.field,
        (t.buckets || []).map(b => ({ id: isChar ? topNDataStrTransform(b.id) : b.id, name: b.name }))
      );
    }
    valueMap.value = map;
  };

  /**
   * 拉取所选策略的维度候选值并合并进 valueMap
   * 参考 monitor-pc alarm-dispatch 的 setDimensionsInfo / setDimensionsOfStrategy：
   * 通过策略 id 获取策略的查询配置，再对每个聚合维度拉取维度候选值。
   * 此场景用于条件变更时的动态补充，无需 loading。
   * @param strategyIds 已选策略 id 列表
   */
  const fetchStrategyDimensions = (strategyIds: (number | string)[]) => {
    const strategyIdKey = 'alert.strategy_id';
    for (const strategyId of Array.from(new Set(strategyIds))
      .map(id => Number(id))
      .filter(id => !Number.isNaN(id))) {
      // 命中缓存则直接复用，避免重复请求
      const specialKey = `${strategyIdKey}=${strategyId}`;
      if (strategySpecialOptions.has(specialKey)) continue;

      getStrategyV2({ id: strategyId })
        .then(strategyInfo => {
          if (!strategyInfo) return;
          const queryConfigs = strategyInfo?.items?.[0]?.query_configs || [];
          const valuesMap = new Map<string, IValue[]>();
          const promiseList: Promise<unknown>[] = [];
          const dimensionKeySet = new Set<string>();
          for (const queryConfig of queryConfigs) {
            for (const dimensionKey of queryConfig?.agg_dimension || []) {
              if (dimensionKeySet.has(dimensionKey)) continue;
              dimensionKeySet.add(dimensionKey);
              const params = {
                params: {
                  data_source_label: queryConfig.data_source_label,
                  data_type_label: queryConfig.data_type_label,
                  field: dimensionKey,
                  metric_field: queryConfig.metric_field || queryConfig.metric_id?.split('.')?.pop() || '',
                  result_table_id: queryConfig.result_table_id,
                  where: [],
                },
                type: 'dimension',
              };
              promiseList.push(
                getVariableValue(params, { needMessage: false })
                  .then((data: any[]) => {
                    valuesMap.set(
                      dimensionKey,
                      (data || []).map(d => ({ id: d.value, name: d.label }))
                    );
                  })
                  .catch(() => {
                    valuesMap.set(dimensionKey, []);
                  })
              );
            }
          }
          return Promise.all(promiseList).then(() => {
            strategySpecialOptions.set(specialKey, valuesMap);
            // 合并到 valueMap，供检索过滤器 getValueFn 查询候选值
            const nextMap = new Map(valueMap.value);
            for (const [tempKey, tempValue] of valuesMap) {
              nextMap.set(tempKey, tempValue);
            }
            valueMap.value = nextMap;
          });
        })
        .catch(() => {});
    }
  };

  /**
   * 拉取全部数据：fields 与候选值并行加载
   * @param timeRange 可选时间窗 [start, end]，默认最近 7 天
   */
  const fetchAllData = async (timeRange?: [number, number]) => {
    const range = timeRange ?? handleTransformToTimestamp(['now-7d', 'now']);
    const bkBizIds = [Number(window.bk_biz_id)];
    loading.value = true;
    try {
      await Promise.all([fetchFields(range, bkBizIds), fetchOptions(range, bkBizIds)]);
    } finally {
      loading.value = false;
    }
  };

  /**
   * 检索过滤器候选值获取函数
   * 从 valueMap 中按字段名取候选值，支持关键字过滤与数量截取。
   */
  const getValueFn = async (params: IGetValueFnParams): Promise<IOptionsInfo> => {
    const field = params?.fields?.[0];
    const list = field ? valueMap.value.get(field) || [] : [];
    const keyword = String(params.where?.[0]?.value?.[0] || '')?.toLowerCase();
    const filtered = keyword
      ? list.filter(
          item => item.name?.toLowerCase().includes(keyword) || String(item.id).toLowerCase().includes(keyword)
        )
      : list;
    const limit = params.limit ?? filtered.length;
    return {
      count: filtered.length,
      list: filtered.slice(0, limit),
    };
  };

  /**
   * 已选条件 tag 的 value 显示值格式化函数
   * 优先使用候选项自带的 name；否则按字段 key 与 val(id) 在 valueMap 中查 name；查不到则回退 id。
   */
  const tagValueDisplayFormatter: TTagValueDisplayFormatter = (val, params) => {
    if (params.isTips) {
      return `${val}`;
    }
    const list = params?.key ? valueMap.value.get(params.key) || [] : [];
    const matched = list.find(item => `${item.id}` === `${params?.value?.id}`);
    if (matched?.name != null && matched.name !== '') {
      const name = matched.name.length > 20 ? `${matched.name.slice(0, 20)}...` : matched.name;
      return name;
    }
    return `${val}`;
  };

  return {
    fields,
    valueMap,
    loading,
    fetchAllData,
    fetchStrategyDimensions,
    getValueFn,
    tagValueDisplayFormatter,
  };
};
