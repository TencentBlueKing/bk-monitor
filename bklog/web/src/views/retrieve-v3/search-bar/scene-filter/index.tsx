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

import { computed, defineComponent, onMounted, onUnmounted, ref, watch } from 'vue';

import http from '@/api';
import { getOs } from '@/common/util';
import useLocale from '@/hooks/use-locale';
import useRetrieveEvent from '@/hooks/use-retrieve-event';
import useStore from '@/hooks/use-store';
import { BK_LOG_STORAGE } from '@/store/store.type';
import { RetrieveUrlResolver } from '@/store/url-resolver';
import { isEqual } from 'lodash-es';
import { useRoute, useRouter } from 'vue-router/composables';

import RetrieveHelper, { RetrieveEvent } from '../../../retrieve-helper';
import SceneFilterTags from '../../../retrieve-v2/sub-bar/scene-filter-tags';
import V3Searchbar from '../index';
import FilterPanel from './filter-panel';
import { getAllSceneFieldOpKeys } from './scene-config';
import { cancelPendingRetrieveRequests, resetRetrieveData } from './scene-retrieve-utils';
import { SceneType } from './types';
import type { FilterValues, SceneDisplayFields } from './types';

import './index.scss';

export default defineComponent({
  name: 'SceneFilter',
  props: {
    isSticky: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const store = useStore();
    const route = useRoute();
    const router = useRouter();

    const sceneConfigs = computed(() => store.getters['retrieve/sceneConfigList']);

    const activeScene = computed<string>({
      get: () => store.state.indexItem.scene_active || SceneType.Container,
      set: (val: string) => {
        store.commit('updateIndexItem', { scene_active: val });
      },
    });

    const filterValues = computed<FilterValues>({
      get: () => store.state.indexItem.scene_filter_values ?? {},
      set: (val: FilterValues) => {
        store.commit('updateIndexItem', { scene_filter_values: val });
      },
    });

    /** id→name 映射表：用于 tags 显示选中值的名称 */
    const filterLabels = ref<Record<string, Record<string, string>>>({});

    const syncUrlParams = (options?: { clearKeywordAndAddition?: boolean }) => {
      const { scene_active, scene_filter_values } = store.state.indexItem;
      const resolver = new RetrieveUrlResolver({
        scene_active,
        scene_filter_values,
      });

      // 先清除所有可能的场景筛选字段，避免切换场景时残留旧字段
      const cleanQuery: Record<string, any> = { ...route.query };
      for (const key of getAllSceneFieldOpKeys(sceneConfigs.value)) {
        delete cleanQuery[key];
      }

      // 场景切换时清除 keyword 和 addition
      if (options?.clearKeywordAndAddition) {
        delete cleanQuery.keyword;
        delete cleanQuery.addition;
      }

      router.replace({
        query: { ...cleanQuery, ...resolver.resolveParamsToUrl() },
      });
    };

    // ---- 条件变更提示条逻辑 ----
    const { t } = useLocale();
    const { addEvent } = useRetrieveEvent();

    /** 上次查询时的 filterValues 快照 */
    const lastQueriedFilterValues = ref<FilterValues | null>(null);
    /** 是否显示提示条 */
    const showQueryHint = ref(false);
    /** 上次查询时的 activeScene 快照 */
    const lastQueriedScene = ref<string | null>(null);

    /** 除去值为空数组的字段 */
    const normalizeFilterValues = (values: FilterValues): FilterValues => {
      const result: FilterValues = {};
      for (const [key, val] of Object.entries(values)) {
        if (val?.value !== undefined) {
          if (Array.isArray(val.value) && val.value.length === 0) continue;
          result[key] = val;
        }
      }
      return result;
    };

    /** 根据当前值与快照的对比，更新提示条状态 */
    const updateQueryHint = () => {
      if (lastQueriedFilterValues.value === null) {
        const hasValues = Object.keys(normalizeFilterValues(filterValues.value)).length > 0;
        store.commit('updateIndexItem', { isSceneFilterChanged: hasValues });
        return;
      }
      const filtersChanged = !isEqual(
        normalizeFilterValues(filterValues.value),
        normalizeFilterValues(lastQueriedFilterValues.value),
      );
      const sceneChanged = activeScene.value !== lastQueriedScene.value;
      const changed = filtersChanged || sceneChanged;
      showQueryHint.value = changed;
      store.commit('updateIndexItem', { isSceneFilterChanged: changed });
    };

    const handleSceneChange = (type: string) => {
      // 取消进行中的请求
      cancelPendingRetrieveRequests();

      activeScene.value = type;
      filterValues.value = {};
      filterLabels.value = {};

      store.commit('retrieve/updateCatchFieldCustomConfig', { fixedFilterAddition: false, filterAddition: [] });
      store.commit('updateStorage', { [BK_LOG_STORAGE.SEARCH_TYPE]: 0 });
      store.commit('updateIndexItemParams', { keyword: '', addition: [] });

      // 清空检索数据
      resetRetrieveData(store);

      // 获取场景化检索用户自定义配置
      http.request('retrieve/getSceneUserCustomConfig', {
        query: {
          bk_biz_id: store.state.bkBizId,
          scene_id: type,
        },
      }).then((res) => {
        store.commit('retrieve/updateCatchFieldCustomConfig', res.data);
      });

      syncUrlParams({ clearKeywordAndAddition: true });

      updateQueryHint();
    };

    const handleFilterChange = (
      payload: {
        values: FilterValues;
        labels?: { fieldName: string; labels: Record<string, string> };
        operatorChange?: { fieldKey: string; op: string };
      },
    ) => {
      filterValues.value = payload.values;
      if (payload.labels) {
        filterLabels.value = { ...filterLabels.value, [payload.labels.fieldName]: payload.labels.labels };
      }
      // 操作符变更时，同步更新本地显示字段配置中的操作符
      if (payload.operatorChange) {
        const { fieldKey, op } = payload.operatorChange;
        const currentFields = currentDisplayFields.value;
        if (currentFields) {
          const updated = currentFields.map(
            ([k, o]) => (k === fieldKey ? [k, op] as [string, string] : [k, o] as [string, string]),
          );
          handleDisplayFieldsChange(updated);
        }
      }
      updateQueryHint();
    };

    const handleClear = () => {
      filterValues.value = {};
      filterLabels.value = {};
      showQueryHint.value = false;
      store.commit('updateIndexItem', { isSceneFilterChanged: false });
    };

    // 每场景独立的显示字段配置
    const bkBizId = computed(() => store.state.bkBizId);

    /** 从 localStorage 读取当前业务的场景显示字段配置 */
    const getLocalSceneDisplayFields = (): SceneDisplayFields => {
      const all = store.state.storage[BK_LOG_STORAGE.SCENE_DISPLAY_FIELDS] ?? {};
      return all[bkBizId.value] ?? {};
    };

    /** 将当前业务的场景显示字段配置写入 localStorage */
    const saveLocalSceneDisplayFields = (fields: SceneDisplayFields) => {
      const all = store.state.storage[BK_LOG_STORAGE.SCENE_DISPLAY_FIELDS] ?? {};
      all[bkBizId.value] = fields;
      store.commit('updateStorage', {
        [BK_LOG_STORAGE.SCENE_DISPLAY_FIELDS]: all,
      });
    };

    const sceneDisplayFields = ref<SceneDisplayFields>(getLocalSceneDisplayFields());

    const currentDisplayFields = computed<Array<[string, string]> | null>(() => {
      const fields = sceneDisplayFields.value[activeScene.value];
      if (!fields) return null;
      // 从全部字段中过滤出缓存中也存在的字段，得到显示字段
      const allFieldKeys = new Set(
        (sceneConfigs.value.find((s: any) => s.type === activeScene.value)?.fields ?? []).map((f: any) => f.key),
      );
      const filtered = fields.filter(([key]) => allFieldKeys.has(key));
      return filtered.length > 0 ? filtered : null;
    });

    const handleDisplayFieldsChange = (fields: Array<[string, string]> | null) => {
      sceneDisplayFields.value = {
        ...sceneDisplayFields.value,
        [activeScene.value]: fields,
      };
      saveLocalSceneDisplayFields(sceneDisplayFields.value);
    };

    const syncQueriedSnapshot = () => {
      lastQueriedFilterValues.value = JSON.parse(JSON.stringify(store.state.indexItem.scene_filter_values ?? {}));
      lastQueriedScene.value = activeScene.value;
      showQueryHint.value = false;
      store.commit('updateIndexItem', { isSceneFilterChanged: false });
      syncUrlParams();
    };

    // 监听 is_loading 从 false→true，表示查询开始
    watch(
      () => store.state.indexSetQueryResult.is_loading,
      (newVal, oldVal) => {
        if (newVal && !oldVal) {
          syncQueriedSnapshot();
        }
      },
    );

    // 监听索引集切换，重置快照
    addEvent(RetrieveEvent.INDEX_SET_ID_CHANGE, () => {
      lastQueriedFilterValues.value = null;
      lastQueriedScene.value = null;
      showQueryHint.value = false;
      store.commit('updateIndexItem', { isSceneFilterChanged: false });
    });

    // 监听字段列表为空事件（场景化检索模式下，字段为空时跳过检索，需同步状态）
    addEvent(RetrieveEvent.SCENE_FIELD_EMPTY, () => {
      syncQueriedSnapshot();
    });

    const shortcutKey = getOs() === 'macos' ? 'cmd+shift+enter' : 'ctrl+shift+enter';

    const hintText = () => t('检索条件有变更，请点击{icon}按钮{shortcut}', {
      icon: '🔍',
      shortcut: `(${shortcutKey})`,
    });

    // ---- 场景化检索禁用判断 ----
    /** 当前是否正在检索中 */
    const isSearching = computed(() => store.state.indexSetQueryResult.is_loading);

    /** 场景过滤条件是否为空 */
    const isSceneFilterEmpty = computed(() => store.getters.isSceneFilterEmpty);

    // ---- 快捷键搜索逻辑 ----
    const handleShortcutKeySearch = (event: KeyboardEvent) => {
      // 仅在场景化检索模式下响应快捷键
      if (!store.getters.isSceneMode) return;

      const isMac = getOs() === 'macos';
      const isCtrlShiftEnter = !isMac && event.ctrlKey && event.shiftKey && event.key === 'Enter';
      const isCmdShiftEnter = isMac && event.metaKey && event.shiftKey && event.key === 'Enter';

      if (isCtrlShiftEnter || isCmdShiftEnter) {
        // 阻止默认行为
        event.preventDefault();
        event.stopPropagation();

        // 场景化检索模式下，未选择过滤条件时不允许查询
        if (isSceneFilterEmpty.value) return;
        // 正在检索中时不允许再次触发检索
        if (isSearching.value) return;

        // 场景化检索模式下，先请求字段列表数据，再执行查询
        store.dispatch('requestIndexSetFieldInfo').then((resp: any) => {
          if (resp?.data?.fields?.length) {
            store.dispatch('requestIndexSetQuery');
            RetrieveHelper.fire(RetrieveEvent.SEARCH_VALUE_CHANGE);
          } else {
            RetrieveHelper.fire(RetrieveEvent.SCENE_FIELD_EMPTY);
          }
        });
      }
    };

    // 监听场景筛选面板高度变化并上报
    let panelObserver: ResizeObserver | undefined;

    onMounted(() => {
      const el = document.querySelector('.scene-filter-panel-section') as HTMLElement;
      if (!el) return;

      // 初始化高度
      RetrieveHelper.setSceneFilterPanelHeight(el.offsetHeight);

      panelObserver = new ResizeObserver(entries => {
        for (const entry of entries) {
          RetrieveHelper.setSceneFilterPanelHeight((entry.target as HTMLElement).offsetHeight);
        }
      });
      panelObserver.observe(el);

      // 注册全局快捷键监听
      document.addEventListener('keydown', handleShortcutKeySearch);
    });

    onUnmounted(() => {
      if (panelObserver) {
        panelObserver.disconnect();
        panelObserver = undefined;
      }
      // 组件卸载时重置高度为 0
      RetrieveHelper.setSceneFilterPanelHeight(0);

      // 移除全局快捷键监听
      document.removeEventListener('keydown', handleShortcutKeySearch);
    });

    return () => (
      <div class='scene-filter-root'>
        <div class='scene-filter-panel-section'>
          <FilterPanel
            activeScene={activeScene.value}
            filterValues={filterValues.value}
            displayFields={currentDisplayFields.value}
            on-scene-change={handleSceneChange}
            on-filter-change={handleFilterChange}
            on-clear={handleClear}
            on-display-fields-change={handleDisplayFieldsChange}
          />
        </div>
        <div class='scene-search-sticky'>
          {props.isSticky && <SceneFilterTags filterLabels={filterLabels.value} />}
          <V3Searchbar />
          <transition name='slide-hint'>
            {showQueryHint.value && !isSceneFilterEmpty.value && (
              <div class='query-hint-bar'>
                <i class='bklog-icon bklog-circle-alert-filled query-hint-icon' />
                <span class='query-hint-text'>{hintText()}</span>
              </div>
            )}
          </transition>
        </div>
        <div class='scene-search-sticky-spacer' />
      </div>
    );
  },
});
