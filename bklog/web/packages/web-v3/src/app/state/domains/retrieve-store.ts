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

import { defineStore, type Pinia } from 'pinia';
import { resolveApplicationPinia } from '../pinia';
import { useApplicationStore } from './application-store';
import { ServicesInstance } from '@/platform/services';
import { transformSceneConfigs } from '../scene-filter-config';
import type { SceneConfigItem } from '../scene-filter-types';
import type { IndexSetOption, RetrieveCustomConfig } from '../retrieval-state.type';
import type { ConsitionItem } from '../store.type';
interface RawIndexSet {
  index_set_id: string | number;
  index_set_name?: string;
  children?: RawIndexSet[];
  indices?: IndexSetOption['indices'];
  parent_node?: unknown;
  auth_wieght?: number;
  [key: string]: unknown;
}
const random = (length = 10) => {
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
  let result = '';
  for (let i = 0; i < length; i++) {
    result += chars[Math.floor(Math.random() * chars.length)];
  }
  return result;
};

const LIGHTEN_NAME_LIMIT = 3;

const buildLightenName = (indices: IndexSetOption['indices'] = []) => {
  const tableIds = (indices ?? []).map((entry) => entry.result_table_id).filter(Boolean);
  if (!tableIds.length) return ' ()';
  if (tableIds.length <= LIGHTEN_NAME_LIMIT) {
    return ` (${tableIds.join(';')})`;
  }
  return ` (${tableIds.slice(0, LIGHTEN_NAME_LIMIT).join(';')}+${tableIds.length - LIGHTEN_NAME_LIMIT})`;
};

/**
 * 索引集列表初始化
 * @param {*} indexSetList 索引集列表
 * @param {*} parentId 父节点 index_set_id，根节点为 '#'
 */
export const resolveIndexItemAttr = (indexSetList: RawIndexSet[] = [], parentId = '#'): IndexSetOption[] => {
  const s1: IndexSetOption[] = [];
  const s2: IndexSetOption[] = [];
  indexSetList?.forEach((item) => {
    const indexSetId = `${item.index_set_id}`;
    const copyItem: IndexSetOption = {
      ...item,
      children: resolveIndexItemAttr(item.children ?? [], indexSetId),
      index_set_id: indexSetId,
      indexName: item.index_set_name as string,
      lightenName: buildLightenName(item.indices),
      unique_id: `${parentId}_${indexSetId}`,
      is_child_node: parentId !== '#',
      parent_id: parentId === '#' ? '' : parentId,
    };
    delete copyItem.parent_node;

    // 这里只有两层，数据结构固定为 parent_id#child_id
    // 如果是根节点 数据结构为 #_child_id

    if (copyItem.auth_wieght === 1) {
      s1.push(copyItem);
    } else {
      s2.push(copyItem);
    }
  });

  return s1.concat(s2);
};

export const createRetrieveState = () => ({
  chartKey: random(10), // 复用监控的图表，改变key重新请求图表
  cacheDatePickerValue: [] as (Date | string)[],
  cacheTimeRange: '',
  filedSettingConfigID: 1,
  indexSetList: [] as IndexSetOption[],
  flatIndexSetList: [] as IndexSetOption[],
  isIndexSetLoading: false,
  isTrendDataLoading: false,
  /** @deprecated Compatibility only; first-render readiness is owned by shell-gate. */
  trendShellPending: true,
  /** @deprecated Compatibility only; result requests never gate the page shell. */
  resultShellReady: false,
  isTotalCountLoaded: false,
  trendDataCount: 0,
  catchFieldCustomConfig: {
    fieldsWidth: {},
    displayFields: [],
    filterSetting: [],
    filterAddition: [],
    fixedFilterAddition: false,
    sortList: [],
  } as RetrieveCustomConfig & { contextDisplayFields?: string[] },
  activeVersion: 'v2',
  /** 场景化检索配置列表 */
  sceneConfigs: {
    is_loading: false,
    data: [] as SceneConfigItem[],
  },
});
const createRetrieveStore = (pinia: Pinia) =>
  defineStore('bklog.retrieve', {
    state: createRetrieveState,
    getters: { sceneConfigList: (state) => transformSceneConfigs(state.sceneConfigs.data ?? []) },
    actions: {
      updateActiveVersion(version?: string | null) {
        this.activeVersion = version ?? 'v2';
      },
      updateTrendDataLoading(payload: boolean) {
        this.isTrendDataLoading = payload;
      },
      updateTrendShellPending(payload: boolean) {
        this.trendShellPending = !!payload;
      },
      updateResultShellReady(payload: boolean) {
        this.resultShellReady = !!payload;
      },
      updateTotalCountLoaded(payload: boolean) {
        this.isTotalCountLoaded = payload;
      },
      updateTrendDataCount(payload: number) {
        this.trendDataCount = payload;
      },
      updateChartKey(payload?: { prefix?: string }) {
        this.chartKey = (payload?.prefix ?? '') + random(10);
      },
      updateCachePickerValue(payload: (Date | string)[]) {
        this.cacheDatePickerValue = payload;
      },
      updateCacheTimeRange(payload: string) {
        this.cacheTimeRange = payload;
      },
      updateFiledSettingConfigID(payload: number) {
        this.filedSettingConfigID = payload;
      },
      updateIndexSetList(payload: IndexSetOption[]) {
        this.indexSetList.length = 0;
        this.indexSetList = [];
        this.indexSetList.push(...payload);

        this.flatIndexSetList.length = 0;
        this.flatIndexSetList = (payload ?? []).map((item) => [item, item.children ?? []]).flat(2);
      },
      updateIndexSetLoading(payload: boolean) {
        this.isIndexSetLoading = payload;
      },
      updateCatchFieldCustomConfig(payload: Partial<RetrieveCustomConfig> | null) {
        Object.assign(
          this.catchFieldCustomConfig,
          {
            fieldsWidth: {},
            displayFields: [],
            filterSetting: [],
            filterAddition: [],
            sortList: [],
            contextDisplayFields: [],
          },
          payload ?? {},
        );
      },
      updateCatchFilterAddition({ addition }: { addition?: ConsitionItem[] }) {
        if (addition?.length) {
          this.catchFieldCustomConfig.filterAddition.length = 0;
          this.catchFieldCustomConfig.filterAddition = [];
          this.catchFieldCustomConfig.filterAddition.push(...addition);
        }
      },
      updateSceneConfigs(payload: { is_loading?: boolean; data?: SceneConfigItem[] | null }) {
        if (payload.is_loading !== undefined) {
          this.sceneConfigs.is_loading = payload.is_loading;
        }
        if (payload.data !== undefined) {
          this.sceneConfigs.data = payload.data ?? [];
        }
      },
      resetRuntimeState() {
        this.indexSetList = [];
        this.flatIndexSetList = [];
        this.isIndexSetLoading = false;
        this.isTrendDataLoading = false;
        this.isTotalCountLoaded = false;
        this.trendDataCount = 0;
        this.catchFieldCustomConfig = {
          fieldsWidth: {},
          displayFields: [],
          filterSetting: [],
          filterAddition: [],
          fixedFilterAddition: false,
          sortList: [],
          contextDisplayFields: [],
        };
        this.sceneConfigs = {
          is_loading: false,
          data: [],
        };
      },
      requestSceneConfigs() {
        this.updateSceneConfigs({ is_loading: true });
        const bkBizId = useApplicationStore(pinia).bkBizId;
        return ServicesInstance.retrieve
          .getSceneConfigs({ query: { bk_biz_id: bkBizId } })
          .then((resp) => {
            const data = (resp.data ?? resp ?? []) as SceneConfigItem[];
            this.updateSceneConfigs({ data });
            return data;
          })
          .catch((err) => {
            console.error('requestSceneConfigs error:', err);
            this.updateSceneConfigs({ data: [] });
            return [];
          })
          .finally(() => this.updateSceneConfigs({ is_loading: false }));
      },
      getIndexSetList(payload: {
        spaceUid: string;
        bkBizId?: string | number;
        isLoading?: boolean;
        is_group?: boolean;
      }) {
        const { spaceUid, isLoading = true, is_group } = payload;
        if (isLoading) this.updateIndexSetLoading(true);
        this.updateIndexSetList([]);
        return ServicesInstance.retrieve
          .getIndexSetList({ query: { space_uid: spaceUid, is_group } })
          .then((res) => {
            let processedIndexSetList: IndexSetOption[] = [];
            if (res.data.length) {
              processedIndexSetList = resolveIndexItemAttr(res.data);
              this.updateIndexSetList(processedIndexSetList);
            }
            return [res, processedIndexSetList] as const;
          })
          .finally(() => this.updateIndexSetLoading(false));
      },
    },
  });
const retrieveStores = new WeakMap<Pinia, ReturnType<typeof createRetrieveStore>>();
export const useRetrieveStore = (pinia?: Pinia) => {
  pinia = resolveApplicationPinia(pinia);
  let store = retrieveStores.get(pinia);
  if (!store) {
    store = createRetrieveStore(pinia);
    retrieveStores.set(pinia, store);
  }
  return store(pinia);
};
