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

import { listAlertTags } from 'monitor-api/modules/alert';
import { getAssignConditionKeys, searchObjectAttribute } from 'monitor-api/modules/assign';
import { type IFilterField, EFieldType } from 'trace/components/retrieval-filter/typing';
import { handleTransformToTimestamp } from 'trace/components/time-range/utils';

/* 需要拉取 CMDB 子选项的 key，子选项通过 searchObjectAttribute 获取，自身不放入 fields */
const CMDB_CHILD_KEYS = ['set', 'module', 'host'];
/* 需要拉取告警标签子选项的 key，子选项通过 listAlertTags 获取，自身不放入 fields */
const TAGS_CHILD_KEYS = ['dimensions'];

/* 不需要出现在 fields 中的 key */
const EXCLUDE_KEYS = ['tags'];

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

/**
 * @description 匹配规则组件的字段逻辑
 * 拉取告警策略匹配条件 key 并构造检索过滤器所需的 fields，
 * 含子选项的 key（set/module/host/dimensions）的子数据通过各自接口并行获取，
 * 仅把子选项展开为独立字段（alias 带上父选项名），父 key 本身不放入 fields。
 */
export const useMatchRuleFields = () => {
  /** 检索过滤器字段列表 */
  const fields = shallowRef<IFilterField[]>([]);
  /** 字段加载状态 */
  const loading = shallowRef(false);

  /**
   * 拉取并构造 fields
   * @param timeRange 可选时间窗 [start, end]，用于 dimensions 子项统计，默认最近 7 天
   */
  const fetchFields = async (timeRange?: [number, number]) => {
    const range = timeRange ?? handleTransformToTimestamp(['now-7d', 'now']);
    const bkBizIds = [Number(window.bk_biz_id)];
    loading.value = true;
    try {
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
      fields.value = result;
    } finally {
      loading.value = false;
    }
  };

  return {
    fields,
    loading,
    fetchFields,
  };
};
