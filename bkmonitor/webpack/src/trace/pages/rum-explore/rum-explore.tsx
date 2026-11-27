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
import {
  computed,
  defineAsyncComponent,
  defineComponent,
  onBeforeUnmount,
  onMounted,
  shallowRef,
  toRef,
  useTemplateRef,
  watch,
} from 'vue';

import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import RetrievalFilter from '../../components/retrieval-filter/retrieval-filter';
import { type IHandleGetUserConfig, type IWhereItem, EMethod, EMode } from '../../components/retrieval-filter/typing';
import {
  mergeWhereList,
  traceWhereChangeFormatter,
  traceWhereFormatter,
} from '../../components/retrieval-filter/utils';
import useUserConfig from '../../hooks/useUserConfig';
import { updateTimezone } from '../../i18n/dayjs';
import { useRumExploreStore } from '../../store/modules/rum-explore';
import RumLoadStatus from '../rum/components/rum-load-status';
import FavoriteBox, { EditFavorite } from '../trace-explore/components/favorite-box';
import TraceExploreLayout from '../trace-explore/components/trace-explore-layout';
import { safeParseJsonValueForWhere } from '../trace-explore/utils';
import RumDimensionPanel from './components/rum-dimension-panel';
import RumEllipsisMode from './components/rum-ellipsis-mode';
import RumEventsDrawer from './components/rum-events-drawer';
import RumExploreHeader from './components/rum-explore-header';
import RumExploreSkeleton from './components/rum-explore-skeleton/rum-explore-skeleton';
import RumExploreTable from './components/rum-explore-table';
import RumExploreView from './components/rum-explore-view/rum-explore-view';
import RumSpanTypeFilter from './components/rum-span-type-filter';
import RumTrendChart from './components/rum-trend-chart/rum-trend-chart';
import {
  useRumActiveRow,
  useRumColumnConfig,
  useRumDetailDrawer,
  useRumEventsDrawer,
  useRumFavorite,
  useRumFieldValues,
  useRumQuery,
  useRumSpanType,
  useRumTableData,
  useRumViewConfig,
} from './composables';
import {
  ALL_SPAN_TYPE,
  RUM_COLUMN_CONFIG_KEY,
  RUM_COLUMN_LAYOUT_PRESET,
  RUM_RESIDENT_SETTING_KEY,
  RumModeEnum,
  SPAN_TYPE_COLUMN_WIDTH_MAP,
} from './constants';
import RumSpanDetailSlider from './detail';
import { OVERVIEW_ISOLATED_LINK_FIELDS } from './detail/constants';
import { getApplicationList } from './services/rum-application';
import EmptyStatus from '@/components/empty-status/empty-status';

import type { TimeRangeType } from '../../components/time-range/utils';
import type { ConditionChangeEvent } from '../trace-explore/typing';
import type { IRumEventsTarget } from './composables/use-rum-events-drawer';
import type {
  IRumApplication,
  IRumColumnLayoutPreset,
  IRumCountDrillDown,
  IRumField,
  IRumTraceInfo,
  RumModeType,
} from './typings';

import './rum-explore.scss';

/** 点击关联 Trace 后按需加载的详情抽屉。 */
const TraceSlider = defineAsyncComponent(
  () => import(/* webpackChunkName: "trace-slider" */ '@/components/trace-slider/trace-slider')
);

/** 默认应用与置顶应用的用户配置 key */
const RUM_EXPLORE_DEFAULT_APPLICATION = 'RUM_EXPLORE_DEFAULT_APPLICATION';
const RUM_EXPLORE_APPLICATION_THUMBTACK = 'rum_explore_application_thumbtack';

export default defineComponent({
  name: 'RumExplore',
  setup() {
    const { t } = useI18n();
    const route = useRoute();
    const router = useRouter();
    const store = useRumExploreStore();

    const { handleGetUserConfig: getDefaultAppConfig, handleSetUserConfig: setDefaultAppConfig } = useUserConfig();
    const { handleGetUserConfig: getThumbtackConfig, handleSetUserConfig: setThumbtackConfig } = useUserConfig();
    const { handleGetUserConfig: getResidentConfig, handleSetUserConfig: setResidentConfig } = useUserConfig();
    /** 只读另一份用户配置，避免和常驻设置的保存 id 互相覆盖 */
    const { handleGetUserConfig: getResidentFieldConfig } = useUserConfig();

    const isCollapsed = shallowRef(false);
    /** 表格 Trace 抽屉使用全局检索命中的应用和业务，空值时关闭。 */
    const activeTraceInfo = shallowRef<IRumTraceInfo | null>(null);
    const applicationLoading = shallowRef(true);
    const applicationError = shallowRef(false);
    let disposed = false;
    /** 切 tab 的代数。连点时只让最后一次回填常驻条件 */
    let modeChangeSeq = 0;
    /** 视图配置未就绪时挂起的等待，卸载时统一取消 */
    const viewConfigWaitStops = new Set<() => void>();
    /** 当前视角「全部」常驻字段，用来区分用户清空和「这个 tab 本来就没有该字段」 */
    const activeResidentKeys = shallowRef<string[]>([]);
    /** 已解析过常驻字段的「视角 + 应用」，避免同一次切换重复请求 */
    const residentKeysReadyId = shallowRef('');
    /** 目标 tab 的常驻字段还没解析完时先挡住检索栏，避免空条件先挂上再回填 */
    const residentProjecting = shallowRef(false);
    /** 调整常驻字段列表时，组件会先抛出值变化；用这份快照把「移除字段」和「清空值」分开 */
    let residentCacheBeforeFieldEdit: null | Record<string, IWhereItem> = null;
    const applicationList = shallowRef<IRumApplication[]>([]);
    const thumbtackList = shallowRef<string[]>([]);
    const defaultApplication = shallowRef('');

    const viewConfigCtx = useRumViewConfig(computed(() => !applicationLoading.value && !applicationError.value));
    const spanTypeCtx = useRumSpanType(viewConfigCtx.viewConfig);
    const queryCtx = useRumQuery({ extraFilters: spanTypeCtx.spanTypeFilters });
    // 先恢复 URL，再初始化依赖应用的配置，避免沿用上一次进入页面的应用。
    queryCtx.initFromUrl();
    const tableCtx = useRumTableData(
      queryCtx.commonParams,
      computed(
        () =>
          viewConfigCtx.ready.value &&
          queryCtx.commonParams.value.app_name === store.appName &&
          queryCtx.commonParams.value.mode === store.mode
      )
    );
    /** 结果集替换或手动刷新时触发重置，手动刷新保留列表滚动位置。 */
    const resetSignal = computed(() => `${tableCtx.backTopSignal.value}|${store.refreshImmediate}`);
    /** events 数组列表抽屉：状态与开关由 hook 管理，重置信号变化（结果集被替换或手动刷新）时自动收起 */
    const eventsDrawerCtx = useRumEventsDrawer(resetSignal);
    /** RUM 行详情的开关、导航及 URL 恢复。 */
    const detailDrawer = useRumDetailDrawer({
      appName: toRef(store, 'appName'),
      initialQuery: route.query,
      mode: toRef(store, 'mode'),
      onOpen: handleDetailOpened,
      rows: tableCtx.tableData,
      setUrlParams: queryCtx.setUrlParams,
      timeRange: toRef(store, 'timeRange'),
    });
    /** 行点击、键盘和 events 抽屉共用的高亮状态，结果集重置时回落到详情来源行。 */
    const activeRowCtx = useRumActiveRow(resetSignal, {
      locked: eventsDrawerCtx.show,
      fallbackRowKey: detailDrawer.detailRowKey,
    });
    const configLoading = computed(
      () =>
        applicationLoading.value ||
        viewConfigCtx.loading.value ||
        residentProjecting.value ||
        (!!store.appName && viewConfigCtx.ready.value && residentKeysReadyId.value !== residentKeysCacheId())
    );
    // tagValueDisplayFormatter 用于让已选条件 tag 按字段单位与枚举别名展示
    const { getFieldValues, tagValueDisplayFormatter } = useRumFieldValues(
      computed(() => viewConfigCtx.viewConfig.value.fields)
    );
    /** 是否处于 span 视角下「指定具体类型」的特殊态 */
    const isSpanSpecialPerspective = computed(() => store.mode === RumModeEnum.SPAN && store.spanType);
    /** 是否存在检索条件，决定表格空状态类型 */
    const emptyType = computed(() => {
      const hasCondition =
        queryCtx.filterMode.value === EMode.queryString
          ? queryCtx.queryString.value.trim()
          : queryCtx.where.value.length > 0 || queryCtx.commonWhere.value.length > 0;
      return hasCondition ? 'search-empty' : 'empty';
    });

    /** 当前视角的列布局预设（默认列宽 / 固定列）：列配置与列设置面板共用同一份声明 */
    const layoutPreset = computed<IRumColumnLayoutPreset>(() => {
      const preset = RUM_COLUMN_LAYOUT_PRESET[store.mode] ?? {};
      const widths = isSpanSpecialPerspective.value ? SPAN_TYPE_COLUMN_WIDTH_MAP[store.spanType] : undefined;
      return widths ? { ...preset, widthMap: { ...preset.widthMap, ...widths } } : preset;
    });

    /** 列配置集中管理：显隐/顺序 + 列宽，并持久化到用户常驻配置 */
    const columnConfig = useRumColumnConfig({
      viewConfig: viewConfigCtx.viewConfig,
      cacheKey: computed(() =>
        store.mode && store.currentApp ? `${RUM_COLUMN_CONFIG_KEY}_${store.mode}_${store.appName}` : ''
      ),
      layoutPreset,
      overrideDisplayFields: computed(() =>
        isSpanSpecialPerspective.value
          ? (viewConfigCtx.viewConfig.value.span_type_display_fields?.[store.spanType] ?? [])
          : []
      ),
    });

    /** 检索条件字段：具体 span 类型视角下，该类型的展示字段按声明顺序前置 */
    const retrievalFields = computed(() => {
      const priorityDisplay = isSpanSpecialPerspective.value
        ? (viewConfigCtx.viewConfig.value.span_type_display_fields?.[store.spanType] ?? [])
        : [];
      const fields = viewConfigCtx.retrievalFields.value;
      if (!priorityDisplay.length) return fields;
      const priorityMap = new Map<string, number>();
      for (const [index, name] of priorityDisplay.entries()) {
        priorityMap.set(name, index);
      }
      const priorityFields = fields.filter(field => priorityMap.has(field.name));
      priorityFields.sort((a, b) => (priorityMap.get(a.name) ?? 0) - (priorityMap.get(b.name) ?? 0));
      return [...priorityFields, ...fields.filter(field => !priorityMap.has(field.name))];
    });

    /**
     * 视图配置字段缓存：接口下发的 fields 只属于当前视角，而详情侧栏需要尽量兼容所有视角的字段。
     * 以「应用 + 视角」为 key 缓存各视角取到的 fields，切走再切回时仍可作为补齐来源。
     */
    const cachedModeFields = shallowRef<Record<string, IRumField[]>>({});
    watch(
      () => [viewConfigCtx.ready.value, viewConfigCtx.viewConfig.value, store.appName, store.mode],
      () => {
        if (!viewConfigCtx.ready.value || !viewConfigCtx.viewConfig.value.fields.length) return;
        const key = `${store.appName}|${store.mode}`;
        cachedModeFields.value = { ...cachedModeFields.value, [key]: viewConfigCtx.viewConfig.value.fields };
      },
      { immediate: true }
    );

    /**
     * 详情侧栏使用的汇总字段：以当前视角的 fields 为基础，再用其它视角缓存的字段补齐缺失项；
     * 同名时保留当前视角的字段，缓存里的重复项丢弃。
     */
    const detailFields = computed<IRumField[]>(() => {
      const current = viewConfigCtx.viewConfig.value.fields;
      const names = new Set(current.map(field => field.name));
      const appPrefix = `${store.appName}|`;
      const extraFields: IRumField[] = [];
      for (const [key, fields] of Object.entries(cachedModeFields.value)) {
        // 只汇总当前应用的各视角字段，换应用后不沿用旧应用的配置
        if (!key.startsWith(appPrefix)) continue;
        for (const field of fields) {
          if (names.has(field.name)) continue;
          names.add(field.name);
          extraFields.push(field);
        }
      }
      return extraFields.length ? [...current, ...extraFields] : current;
    });

    /**
     * 详情头部可点击的字段：只有属于当前视角检索字段的项，点击后生成的条件才能被当前视角解析。
     * 检索字段取自 view_config 中 is_searched 为 true 的字段（源自接口 is_searchable），与检索条件区的候选字段同源。
     */
    const retrievalFieldNames = computed(() => viewConfigCtx.retrievalFields.value.map(field => field.name));

    const favoriteBoxRef = useTemplateRef<InstanceType<typeof FavoriteBox>>('favoriteBoxRef');
    /** 检索视图容器 ref，其根节点即表格的滚动容器，也是吸顶表头锚定的容器 */
    const rumExploreViewRef = useTemplateRef<InstanceType<typeof RumExploreView>>('rumExploreViewRef');
    const favoriteCtx = useRumFavorite({
      where: queryCtx.where,
      commonWhere: queryCtx.commonWhere,
      queryString: queryCtx.queryString,
      filterMode: queryCtx.filterMode,
      displayFields: columnConfig.displayFields,
      onApplied: () => queryCtx.handleQuery(),
    });

    const isSpanMode = computed(() => store.mode === RumModeEnum.SPAN);
    /** 具体类型只使用可检索的固定常驻字段，表格列与全局用户配置不参与兜底。 */
    const spanTypeResidentFields = computed(() => {
      const keys = viewConfigCtx.viewConfig.value.span_type_resident_fields?.[spanTypeCtx.activeSpanType.value] || [];
      const searchableKeys = new Set(viewConfigCtx.retrievalFields.value.map(field => field.name));
      return keys.filter(key => searchableKeys.has(key));
    });
    const residentSettingCustomId = computed(() => {
      return `${RUM_RESIDENT_SETTING_KEY}_${store.mode}_${store.appName}_${spanTypeCtx.activeSpanType.value}`;
    });
    /** 全部视角使用用户配置 key；具体类型的 key 仅用于触发固定常驻字段刷新，不读写用户配置。 */
    const residentSettingOnlyId = computed(() => {
      if (!store.mode || !store.currentApp) return '';
      if (spanTypeCtx.activeSpanType.value !== ALL_SPAN_TYPE) {
        return residentSettingCustomId.value;
      }
      return `${RUM_RESIDENT_SETTING_KEY}_${store.mode}_${store.appName}`;
    });
    const favoriteList = computed(
      () =>
        favoriteBoxRef.value?.getFavoriteList()?.map(item => ({
          ...item,
          config: {
            queryString: item?.config?.queryParams?.query || '',
            where: item?.config?.queryParams?.filters || [],
            commonWhere: item?.config?.componentData?.commonWhere || [],
          },
        })) || []
    );

    watch(
      () => store.timezone,
      timezone => updateTimezone(timezone)
    );

    /** 首次进入或视角配置刷新后，补齐当前 tab 的常驻字段，用户清空值时才知道该删哪个 key */
    watch(
      () => [viewConfigCtx.ready.value, store.mode, store.appName] as const,
      ([ready]) => {
        if (!ready) return;
        void resolveAllResidentKeys(modeChangeSeq);
      }
    );

    /** 自动刷新 */
    let autoRefreshTimer: number = null;
    watch(
      () => store.refreshInterval,
      interval => {
        window.clearInterval(autoRefreshTimer);
        if (!(interval > 0)) return;
        autoRefreshTimer = window.setInterval(() => {
          if (viewConfigCtx.ready.value && !tableCtx.loading.value && !tableCtx.scrollLoading.value) {
            tableCtx.fetchList();
          }
        }, interval);
      },
      { immediate: true }
    );

    async function fetchApplicationList() {
      const [list] = await Promise.all([getApplicationList(), fetchUserConfig()]);
      if (disposed) return;
      applicationList.value = list;
      store.appList = list;
      if (store.appName && list.some(item => item.app_name === store.appName)) return;
      const preferred = defaultApplication.value || thumbtackList.value[0];
      store.appName = list.some(item => item.app_name === preferred) ? preferred : list[0]?.app_name || '';
    }

    async function fetchUserConfig() {
      await Promise.allSettled([
        getDefaultAppConfig<string>(RUM_EXPLORE_DEFAULT_APPLICATION).then(res => {
          defaultApplication.value = res || '';
        }),
        getThumbtackConfig<string[]>(RUM_EXPLORE_APPLICATION_THUMBTACK).then(res => {
          thumbtackList.value = res || [];
        }),
      ]);
    }

    function residentKeysCacheId(mode: RumModeType = store.mode) {
      return `${mode}\0${store.appName}`;
    }

    function filterSearchableResidentKeys(keys: string[]) {
      const searchable = new Set(viewConfigCtx.retrievalFields.value.map(field => field.name));
      const result: string[] = [];
      const seen = new Set<string>();
      for (const key of keys) {
        if (!key || seen.has(key) || !searchable.has(key)) continue;
        seen.add(key);
        result.push(key);
      }
      return result;
    }

    /** 等到这一次切换对应的视图配置落地；失败或被更新的切换打断时返回 false */
    function waitForViewConfig(seq: number): Promise<boolean> {
      if (disposed || seq !== modeChangeSeq) return Promise.resolve(false);
      if (viewConfigCtx.ready.value) return Promise.resolve(true);
      if (viewConfigCtx.error.value && !viewConfigCtx.loading.value) return Promise.resolve(false);
      return new Promise(resolve => {
        let settled = false;
        let stop = () => {};
        const finish = (ready: boolean) => {
          if (settled) return;
          settled = true;
          stop();
          viewConfigWaitStops.delete(cancel);
          resolve(ready);
        };
        const cancel = () => finish(false);
        stop = watch(
          () => [viewConfigCtx.ready.value, viewConfigCtx.error.value, viewConfigCtx.loading.value] as const,
          ([ready, error, loading]) => {
            if (disposed || seq !== modeChangeSeq) {
              finish(false);
              return;
            }
            if (ready) finish(true);
            else if (error && !loading) finish(false);
          }
        );
        viewConfigWaitStops.add(cancel);
      });
    }

    /**
     * 当前视角在「全部」下的常驻字段。
     * 用户保存过就用用户配置，否则用视图配置的 resident_fields；具体 span 类型不走这里。
     */
    async function resolveAllResidentKeys(seq: number) {
      if (disposed || seq !== modeChangeSeq) return [];
      const cacheId = residentKeysCacheId();
      if (viewConfigCtx.ready.value && residentKeysReadyId.value === cacheId) {
        return activeResidentKeys.value;
      }
      const configKey = `${RUM_RESIDENT_SETTING_KEY}_${store.mode}_${store.appName}`;
      const savedPromise = getResidentFieldConfig<string[]>(configKey);
      const ready = await waitForViewConfig(seq);
      const saved = await savedPromise;
      if (!ready || disposed || seq !== modeChangeSeq || residentKeysCacheId() !== cacheId) return [];
      const source =
        Array.isArray(saved) && saved.length ? saved : viewConfigCtx.viewConfig.value.resident_fields || [];
      const keys = filterSearchableResidentKeys(source);
      activeResidentKeys.value = keys;
      residentKeysReadyId.value = cacheId;
      return keys;
    }

    function appliedResidentKeys(allKeys: string[]) {
      if (store.mode === RumModeEnum.SPAN && spanTypeCtx.activeSpanType.value) {
        return spanTypeResidentFields.value;
      }
      return allKeys;
    }

    function invalidateResidentProjection() {
      modeChangeSeq += 1;
      residentProjecting.value = false;
    }

    function handleAppNameChange() {
      invalidateResidentProjection();
      queryCtx.where.value = [];
      queryCtx.commonWhere.value = [];
      queryCtx.clearResidentValueCache();
      queryCtx.clearWhereValueCache();
      activeResidentKeys.value = [];
      residentKeysReadyId.value = '';
      setDefaultAppConfig(JSON.stringify(store.appName));
      queryCtx.handleQuery();
    }

    /**
     * 切换 Session / View / Span。
     * 语句清空；UI 检索条件与常驻筛选按三个 tab 共用缓存回填，目标 tab 没有的 key 不参与检索也不删除。
     * @param mode 目标视角
     * @param shouldQuery 是否立即检索；下钻要先写上点击条件时传 false
     * @returns 是否仍是最后一次切换。连点时较早的一次返回 false，调用方不要再改条件
     */
    async function handleModeChange(mode: RumModeType, shouldQuery = true) {
      const seq = ++modeChangeSeq;
      // 切走前把当前 tab 的检索条件写回共用缓存；上一次切换未完成时 where 正等待回填，不能拿空值覆盖缓存
      if (!residentProjecting.value) {
        queryCtx.saveWhereValueCache(viewConfigCtx.retrievalFields.value.map(field => field.name));
      }
      // 常驻字段按视角异步取，先卸掉检索栏，等回填后再挂上，避免空值覆盖组件内部状态后填不回去
      residentProjecting.value = true;
      store.mode = mode;
      store.userSort = null;
      queryCtx.where.value = [];
      queryCtx.queryString.value = '';
      queryCtx.commonWhere.value = [];
      try {
        const allKeys = await resolveAllResidentKeys(seq);
        if (disposed || seq !== modeChangeSeq) return false;
        queryCtx.where.value = queryCtx.projectWhere(viewConfigCtx.retrievalFields.value.map(field => field.name));
        queryCtx.commonWhere.value = queryCtx.projectResidentWhere(appliedResidentKeys(allKeys));
        if (shouldQuery) queryCtx.handleQuery();
        return true;
      } finally {
        if (seq === modeChangeSeq) residentProjecting.value = false;
      }
    }

    /**
     * 数量列下钻：切到目标视角和指定的 Span 类型，并带上点击的条件。
     * 常驻筛选仍按目标 tab 的字段从共用缓存回填。
     */
    const handleCountDrillDown = async (options: IRumCountDrillDown) => {
      store.spanType = options.spanType ?? ALL_SPAN_TYPE;
      const applied = await handleModeChange(options.targetMode, false);
      if (!applied || disposed) return;
      handleConditionChange(options.condition, false);
    };

    /**
     * 切换 span 类型只改当前生效的常驻条件：具体类型裁掉没有的字段，回到「全部」清空。
     * 这里不写共用缓存，切到其他 tab 时仍能按 key 填回来。
     * @param type 点击的类型；setSpanType 为 toggle 语义，重复点击回到「全部」，判断须以 activeSpanType 为准
     * @param shouldQuery 是否立即检索；需先改写条件时传 false，由调用方在条件就绪后触发
     */
    function handleSpanTypeChange(type: string, shouldQuery = true) {
      spanTypeCtx.setSpanType(type);
      const activeType = spanTypeCtx.activeSpanType.value;
      if (activeType === ALL_SPAN_TYPE) {
        queryCtx.commonWhere.value = [];
      } else {
        queryCtx.commonWhere.value = queryCtx.commonWhere.value.filter(w =>
          spanTypeResidentFields.value.includes(w.key)
        );
      }
      if (shouldQuery) queryCtx.handleQuery();
    }

    async function handleThumbtackChange(list: string[]) {
      thumbtackList.value = list;
      await setThumbtackConfig(JSON.stringify(list));
    }

    function handleCommonWhereChange(value: IWhereItem[]) {
      residentCacheBeforeFieldEdit = queryCtx.snapshotResidentValueCache();
      const residentKeys = appliedResidentKeys(activeResidentKeys.value);
      queryCtx.syncResidentValueCache(value, residentKeys);
      queryCtx.commonWhere.value = value;
      queryCtx.handleQuery();
      Promise.resolve().then(() => {
        residentCacheBeforeFieldEdit = null;
      });
    }

    /**
     * 常驻字段列表保存。确认设置时组件会先抛值变化，再调用这里。
     * 从列表里移除的字段不算用户清空，把刚被同步删掉的缓存写回去。
     */
    async function handleSetResidentConfig(value: string) {
      const snapshot = residentCacheBeforeFieldEdit;
      residentCacheBeforeFieldEdit = null;
      if (!spanTypeCtx.activeSpanType.value) {
        try {
          const parsed = JSON.parse(value);
          if (Array.isArray(parsed)) {
            const nextKeys = filterSearchableResidentKeys(parsed.map(key => String(key)));
            activeResidentKeys.value = nextKeys;
            residentKeysReadyId.value = residentKeysCacheId();
            if (snapshot) {
              const nextKeySet = new Set(nextKeys);
              queryCtx.restoreResidentValueCache(
                snapshot,
                Object.keys(snapshot).filter(key => !nextKeySet.has(key))
              );
            }
          }
        } catch {
          // 字段列表不是数组时保持当前 key，避免误把缓存当成已清空
        }
      }
      return setResidentConfig(value);
    }

    function handleApplyFavorite(favorite: Parameters<typeof favoriteCtx.applyFavorite>[0]) {
      invalidateResidentProjection();
      queryCtx.clearResidentValueCache();
      queryCtx.clearWhereValueCache();
      activeResidentKeys.value = [];
      residentKeysReadyId.value = '';
      residentCacheBeforeFieldEdit = null;
      favoriteCtx.applyFavorite(favorite);
      // 收藏没改视角时，视图配置不会重新 ready，需要主动补一次常驻字段
      if (viewConfigCtx.ready.value && residentKeysReadyId.value !== residentKeysCacheId()) {
        void resolveAllResidentKeys(modeChangeSeq);
      }
    }

    /** 维度面板与表格单元格触发的条件追加 */
    function handleConditionChange(condition: ConditionChangeEvent, isFromDimensionFilterPanel = true) {
      const { key, method: operator, value } = condition;
      const field = viewConfigCtx.viewConfig.value.fields.find(item => item.name === key);
      /** 范围值；切视角时 viewConfig 可能异步清空，字段缺失按普通等值条件处理 */
      const isRangeValue =
        (field?.field_display_type === 'duration' && field?.field_unit !== 'vital') || field?.field_unit === 'bytes';
      const matched = value.match(/^(-?\d+)-(-?\d+)$/);
      if (queryCtx.filterMode.value === EMode.ui) {
        queryCtx.addCondition(
          {
            key,
            operator,
            value: isRangeValue && matched ? [matched[1], matched[2]] : safeParseJsonValueForWhere(value),
          },
          isFromDimensionFilterPanel
        );
        return;
      }
      let endStr = `${operator === EMethod.eq ? '' : 'NOT '}${key} : "${value || ''}"`;
      if (isRangeValue && matched) {
        endStr = `${key} : [${matched[1]} TO ${matched[2] || matched[1]}]`;
      }
      // 语句里已有完全相同的条件时忽略本次添加，避免重复检索；
      // 比对时忽略空白差异，兼容 UI 模式切换过来时由后端生成的语句空格格式
      const normalize = (str: string) => str.replace(/\s+/g, '');
      if (queryCtx.queryString.value.split(/\s+AND\s+/).some(item => normalize(item) === normalize(endStr))) return;
      queryCtx.queryStringChange(
        queryCtx.queryString.value ? `${queryCtx.queryString.value} AND ${endStr}` : `${endStr}`
      );
    }

    /**
     * Span 详情内的「添加为检索条件」：不改动当前页面的检索条件，
     * 而是把「当前查询状态 + 新条件」拼成 URL 另开一页，避免打断正在浏览的详情与列表。
     * @param isFromDimensionFilterPanel 透传给 mergeWhereList 的「是否合并同 key 对立项」开关；
     *                                   详情侧固定传 false，只做追加
     */
    function handleRumSpanDetailConditionAdd(condition: ConditionChangeEvent, isFromDimensionFilterPanel = true) {
      const { key, method: operator, value } = condition;
      // 详情里的字段可能来自原始数据面板，未必在视图配置字段中
      const field = viewConfigCtx.viewConfig.value.fields.find(item => item.name === key);
      /** 范围值（耗时 / 字节大小）在详情里展示为 "min-max"，需拆成区间条件而非等值匹配 */
      const isRangeValue =
        (field?.field_display_type === 'duration' && field?.field_unit !== 'vital') || field?.field_unit === 'bytes';
      /** 区间值 "100-200" 的匹配结果，[1] 为下界、[2] 为上界 */
      const matched = value.match(/^(-?\d+)-(-?\d+)$/);
      const query = queryCtx.buildUrlQuery();
      // 不沿用收藏：新页应用收藏条件会覆盖掉本次追加的条件
      delete query.favorite_id;
      // 新页只还原检索态，不携带当前页正在浏览的详情抽屉
      delete query.detailShow;
      delete query.detailContext;
      /** 会话 / 页面 ID 跳转：新页只按点击的 ID 检索，不携带当前页面的其他过滤条件(其他过滤条件具体指滴是 检索栏(ui | queryString) 的参数 及 常驻筛选 中的参数) */
      const isIsolatedJump = OVERVIEW_ISOLATED_LINK_FIELDS.has(key);
      if (queryCtx.filterMode.value === EMode.ui) {
        const items = [
          {
            key,
            operator,
            value: isRangeValue && matched ? [matched[1], matched[2]] : safeParseJsonValueForWhere(value),
          },
        ];
        query.where = encodeURIComponent(
          JSON.stringify(
            isIsolatedJump ? items : mergeWhereList(queryCtx.where.value, items, isFromDimensionFilterPanel)
          )
        );
        if (isIsolatedJump) {
          query.commonWhere = encodeURIComponent(JSON.stringify([]));
          query.queryString = '';
        }
      } else {
        // 语句模式：默认拼等值/取反子句，区间值改用 ES 的 range 语法
        let endStr = `${operator === EMethod.eq ? '' : 'NOT '}${key} : "${value || ''}"`;
        if (isRangeValue && matched) {
          endStr = `${key} : [${matched[1]} TO ${matched[2] || matched[1]}]`;
        }
        query.queryString = encodeURIComponent(
          isIsolatedJump || !queryCtx.queryString.value ? endStr : `${queryCtx.queryString.value} AND ${endStr}`
        );
        if (isIsolatedJump) {
          // 语句模式下清空 UI 条件与常驻筛选，避免与查询语句叠加生效
          query.where = encodeURIComponent(JSON.stringify([]));
          query.commonWhere = encodeURIComponent(JSON.stringify([]));
        }
      }
      // 复用当前查询态另开一页：新页走 initFromUrl 还原，故不改动本页 store
      window.open(router.resolve({ path: route.path, query }).href, '_blank');
    }

    /**
     * @description 打开或切换行详情时收起 Events 抽屉，并高亮当前来源行。
     * @param {string} rowKey 当前检索视角下的来源行标识
     * @returns {void}
     */
    function handleDetailOpened(rowKey: string) {
      eventsDrawerCtx.closeDrawer();
      activeRowCtx.setActiveRowKey(rowKey);
    }

    /**
     * @description 关闭底部 events 抽屉后，在当前检索页打开命中的 Trace。
     * @param {IRumTraceInfo} trace 命中的 Trace ID 及其所属业务和应用
     * @returns {void}
     */
    function handleOpenTraceDetail(trace: IRumTraceInfo) {
      eventsDrawerCtx.closeDrawer();
      activeTraceInfo.value = trace;
    }

    /** 打开 events 抽屉：抽屉 hook 记录目标行后，把高亮行指向该行 */
    function handleEventsCellClick(target: IRumEventsTarget) {
      eventsDrawerCtx.handleEventsCellClick(target);
      activeRowCtx.setActiveRowKey(target.row?.span_id);
    }

    function handleSortChange(sort: string | string[]) {
      tableCtx.handleSortChange(sort);
      queryCtx.setUrlParams();
    }

    /** 总趋势图框选 / 复位：与头部时间选择器一致写入时间范围并同步 URL，避免刷新后回到旧区间 */
    function handleTrendDataZoomChange(value: TimeRangeType) {
      store.timeRange = value;
      queryCtx.setUrlParams();
    }

    function handleCreateApp() {
      const url = location.href.replace(location.hash, '#/apm/home');
      window.open(url, '_blank');
    }

    /**
     * 常驻设置的读取兜底链路（替换原 getResidentConfig 传给检索组件）
     * 选中具体 span 类型时不允许用户自定义，直接取视图配置中该类型的默认常驻字段；
     * 否则先读用户保存的配置，没存过才回落到视图配置的 resident_fields
     * @param key - 常驻设置的配置 id，见 residentSettingOnlyId
     */
    async function getResidentConfigCustom(key: string) {
      if (!key) {
        await getResidentConfig(key);
        return [];
      }
      if (key === residentSettingCustomId.value) {
        return spanTypeResidentFields.value;
      }
      const fields = (await getResidentConfig<string[]>(key)) || [];
      if (fields.length) {
        return fields;
      }
      return viewConfigCtx.viewConfig.value?.resident_fields || [];
    }

    async function initialize() {
      applicationLoading.value = true;
      applicationError.value = false;
      try {
        await fetchApplicationList();
        if (disposed) return;
        queryCtx.handleQuery();
      } catch {
        if (!disposed) applicationError.value = true;
      } finally {
        if (!disposed) applicationLoading.value = false;
      }
    }

    onMounted(() => {
      updateTimezone(store.timezone);
      initialize().then(() => {
        if (disposed || applicationError.value) return;
        detailDrawer.restoreDetail();
      });
    });

    onBeforeUnmount(() => {
      disposed = true;
      invalidateResidentProjection();
      for (const cancel of viewConfigWaitStops) cancel();
      viewConfigWaitStops.clear();
      window.clearInterval(autoRefreshTimer);
    });

    return {
      t,
      route,
      store,
      applicationList,
      applicationLoading,
      activeRowCtx,
      activeTraceInfo,
      eventsDrawerCtx,
      applicationError,
      initialize,
      configLoading,
      columnConfig,
      detailDrawer,
      detailFields,
      retrievalFieldNames,
      emptyType,
      layoutPreset,
      isSpanSpecialPerspective,
      favoriteBoxRef,
      favoriteCtx,
      favoriteList,
      rumExploreViewRef,
      isCollapsed,
      isSpanMode,
      queryCtx,
      residentSettingOnlyId,
      resetSignal,
      spanTypeCtx,
      tableCtx,
      thumbtackList,
      viewConfigCtx,
      retrievalFields,
      getFieldValues,
      getResidentConfig,
      getResidentConfigCustom,
      handleSetResidentConfig,
      setResidentConfig,
      handleAppNameChange,
      handleApplyFavorite,
      handleCommonWhereChange,
      handleConditionChange,
      handleEventsCellClick,
      handleModeChange,
      handleOpenTraceDetail,
      handleSortChange,
      handleSpanTypeChange,
      handleThumbtackChange,
      handleTrendDataZoomChange,
      handleCountDrillDown,
      handleCreateApp,
      tagValueDisplayFormatter,
      handleRumSpanDetailConditionAdd,
    };
  },
  render() {
    const { activeRowCtx, detailDrawer, eventsDrawerCtx, favoriteCtx, queryCtx, spanTypeCtx, tableCtx, viewConfigCtx } =
      this;
    /** 抽屉的目标行：渲染期取一次快照，既决定是否挂载抽屉，也作为 row 传入 */
    const eventsRow = eventsDrawerCtx.row.value;
    /** 省略方式控件：span 视角挂在类型筛选右侧，其他视角挂在趋势图汇聚周期右侧 */
    const ellipsisModeNode = () => (
      <RumEllipsisMode
        value={queryCtx.ellipsisMode.value}
        onChange={queryCtx.ellipsisModeChange}
      />
    );

    return (
      <div class='rum-explore'>
        <div
          style={{ display: favoriteCtx.favoriteShow.value ? 'block' : 'none' }}
          class='favorite-panel'
        >
          <FavoriteBox
            ref='favoriteBoxRef'
            defaultFavoriteId={queryCtx.urlFavoriteId.value}
            type='rum'
            onChange={this.handleApplyFavorite}
            onClose={() => {
              favoriteCtx.favoriteShow.value = false;
            }}
            onOpenBlank={data => favoriteCtx.openFavoriteInBlank(data, this.route.path)}
          />
        </div>

        <div class='main-panel'>
          <RumExploreHeader
            applicationList={this.applicationList}
            favoriteShow={favoriteCtx.favoriteShow.value}
            loading={this.applicationLoading}
            thumbtackList={this.thumbtackList}
            onAppNameChange={this.handleAppNameChange}
            onFavoriteShowChange={show => {
              favoriteCtx.favoriteShow.value = show;
            }}
            onModeChange={this.handleModeChange}
            onSetUrlParams={() => queryCtx.setUrlParams()}
            onThumbtackChange={this.handleThumbtackChange}
          />

          <div class='rum-explore-content'>
            <RumLoadStatus
              error={this.applicationError || viewConfigCtx.error.value}
              onRetry={() => (this.applicationError ? this.initialize() : viewConfigCtx.fetchViewConfig())}
            />
            {this.applicationError || viewConfigCtx.error.value ? null : this.configLoading ? (
              <RumExploreSkeleton
                kind='filter'
                showResident={queryCtx.showResidentBtn.value && queryCtx.filterMode.value !== EMode.queryString}
              />
            ) : (
              <RetrievalFilter
                key={`__${this.store.timezone}__`}
                changeWhereFormatter={traceWhereChangeFormatter}
                commonWhere={queryCtx.commonWhere.value}
                copyLoading={queryCtx.generateQueryStringLoading.value}
                defaultShowResidentBtn={queryCtx.showResidentBtn.value}
                favoriteList={this.favoriteList}
                fields={this.retrievalFields}
                /* UI 模式添加条件时不预选字段，直接聚焦到字段搜索框 */
                fieldSearchAutoFocus={true}
                filterMode={queryCtx.filterMode.value}
                getValueFn={this.getFieldValues}
                handleGetUserConfig={this.getResidentConfigCustom as IHandleGetUserConfig}
                handleSetUserConfig={this.handleSetResidentConfig}
                isShowClear={true}
                isShowCopy={true}
                isShowFavorite={true}
                isShowResident={true}
                modeChangeLoading={queryCtx.generateQueryStringLoading.value}
                /* 提示用户按 / 可唤起检索框 */
                placeholder={this.t('/ 唤起，输入检索内容')}
                queryString={queryCtx.queryString.value}
                residentSettingOnlyId={this.residentSettingOnlyId}
                residentSettingTransferDisable={spanTypeCtx.activeSpanType.value !== ALL_SPAN_TYPE}
                selectFavorite={favoriteCtx.selectedFavorite.value}
                tagValueDisplayFormatter={this.tagValueDisplayFormatter}
                where={queryCtx.where.value}
                whereFormatter={traceWhereFormatter}
                onCommonWhereChange={this.handleCommonWhereChange}
                onCopyWhere={queryCtx.copyWhere}
                onFavorite={isEdit => favoriteCtx.saveFavorite(isEdit, () => this.favoriteBoxRef?.refreshGroupList())}
                onModeChange={queryCtx.modeChange}
                onQueryStringChange={queryCtx.queryStringChange}
                onSearch={queryCtx.handleQuery}
                onShowResidentBtnChange={queryCtx.showResidentChange}
                onWhereChange={queryCtx.whereChange}
              />
            )}
            {!this.applicationLoading && !this.applicationError && !this.applicationList.length && (
              <div class='create-app-guide'>
                <EmptyStatus
                  textMap={{ 'empty-app': this.t('暂无应用') }}
                  type='empty-app'
                >
                  <p class='subTitle'>
                    <i18n-t keypath='无法查询调用链，请先 {0}'>
                      <span onClick={() => this.handleCreateApp()}>{this.t('创建应用')}</span>
                    </i18n-t>
                  </p>
                </EmptyStatus>
              </div>
            )}
            {!this.applicationError &&
              !viewConfigCtx.error.value &&
              (this.applicationLoading || !!this.applicationList.length) && (
                <TraceExploreLayout
                  isCollapsed={this.isCollapsed}
                  onUpdate:isCollapsed={value => {
                    this.isCollapsed = value;
                  }}
                >
                  {{
                    aside: () => (
                      <RumDimensionPanel
                        activeSpanType={spanTypeCtx.activeSpanType.value}
                        commonParams={queryCtx.commonParams.value}
                        groups={viewConfigCtx.fieldGroups.value}
                        loading={this.configLoading}
                        timeRange={this.store.timeRange}
                        onClose={() => {
                          this.isCollapsed = true;
                        }}
                        onConditionChange={this.handleConditionChange}
                      />
                    ),
                    default: () => (
                      <div class='result-panel'>
                        <RumLoadStatus
                          error={tableCtx.error.value}
                          loading={tableCtx.loading.value && !!tableCtx.tableData.value.length}
                          onRetry={tableCtx.retry}
                        />
                        {this.configLoading ? null : (
                          <RumTrendChart
                            v-slots={{ headerExtra: this.isSpanMode ? undefined : ellipsisModeNode }}
                            commonParams={queryCtx.commonParams.value}
                            onDataZoomChange={this.handleTrendDataZoomChange}
                          />
                        )}
                        <RumExploreView
                          ref='rumExploreViewRef'
                          v-slots={{
                            affixedTop: this.isSpanMode
                              ? () => (
                                  <RumSpanTypeFilter
                                    v-slots={{ extra: ellipsisModeNode }}
                                    list={spanTypeCtx.chipList.value}
                                    loading={this.configLoading}
                                    value={spanTypeCtx.activeSpanType.value}
                                    onChange={this.handleSpanTypeChange}
                                  />
                                )
                              : undefined,
                            default: () =>
                              this.configLoading ? (
                                <RumExploreSkeleton kind='table' />
                              ) : tableCtx.error.value && !tableCtx.tableData.value.length ? null : (
                                <RumExploreTable
                                  headerAffixedTop={{
                                    container: () => this.rumExploreViewRef?.$el,
                                    // span 模式下表格上方有 RumSpanTypeFilter 吸顶区域（高度 56px：padding 12 + chip 32 + padding 12）
                                    offsetTop: this.isSpanMode ? 56 : 0,
                                  }}
                                  activeColKey={eventsDrawerCtx.show.value ? eventsDrawerCtx.colKey.value : ''}
                                  activeRowKey={activeRowCtx.activeRowKey.value}
                                  baseColumns={this.columnConfig.baseColumns.value}
                                  commonParams={queryCtx.commonParams.value}
                                  data={tableCtx.tableData.value}
                                  defaultFieldKeys={this.columnConfig.defaultDisplayFields.value}
                                  displayableFields={this.columnConfig.displayableFields.value}
                                  ellipsisMode={queryCtx.ellipsisMode.value}
                                  emptyType={this.emptyType}
                                  fieldMap={this.columnConfig.fieldMap.value}
                                  fixedDisplayList={this.layoutPreset.leftFixedColumns}
                                  hasMore={tableCtx.hasMore.value}
                                  horizontalScrollAffixedBottom={{ container: () => this.rumExploreViewRef?.$el }}
                                  loading={tableCtx.loading.value}
                                  mode={this.store.mode}
                                  scrollLoading={tableCtx.scrollLoading.value}
                                  showSettings={!this.isSpanSpecialPerspective}
                                  sort={tableCtx.sortParams.value}
                                  timeRange={this.store.timeRange}
                                  timezone={this.store.timezone}
                                  traceLookupKey={this.resetSignal}
                                  onActiveChange={activeRowCtx.handleActiveRowChange}
                                  onClearFilter={queryCtx.clearQuery}
                                  onColumnResizeChange={width => this.columnConfig.updateColumnResizeWidth(width)}
                                  onConditionChange={this.handleConditionChange}
                                  onCountClick={this.handleCountDrillDown}
                                  onDisplayFieldChange={fields => this.columnConfig.updateDisplayFields(fields)}
                                  onEventsCellClick={this.handleEventsCellClick}
                                  onOpenDetail={detailDrawer.handleOpenDetail}
                                  onOpenSessionDetail={detailDrawer.handleOpenDetail}
                                  onOpenTraceDetail={this.handleOpenTraceDetail}
                                  onScrollToEnd={tableCtx.handleScrollToEnd}
                                  onSortChange={this.handleSortChange}
                                />
                              ),
                          }}
                          backTopSignal={tableCtx.backTopSignal.value}
                          syncAffixOnResize={true}
                        />
                      </div>
                    ),
                  }}
                </TraceExploreLayout>
              )}
          </div>
        </div>

        <RumSpanDetailSlider
          context={detailDrawer.context.value}
          fields={this.detailFields}
          isShow={detailDrawer.isShow.value}
          mode={detailDrawer.mode.value}
          retrievalFieldNames={this.retrievalFieldNames}
          showRecordNavigation={detailDrawer.showRecordNavigation.value}
          onConditionAdd={(key, value) =>
            this.handleRumSpanDetailConditionAdd({ key, method: EMethod.eq, value }, false)
          }
          onNext={detailDrawer.handleNextDetail}
          onPrevious={detailDrawer.handlePreviousDetail}
          onUpdate:isShow={detailDrawer.handleShowChange}
        />

        {this.activeTraceInfo && (
          <TraceSlider
            appName={this.activeTraceInfo.app_name}
            bizId={this.activeTraceInfo.bk_biz_id ?? window.cc_biz_id}
            isShow={true}
            traceId={this.activeTraceInfo.trace_id}
            onSliderClose={() => (this.activeTraceInfo = null)}
          />
        )}

        {/* events 抽屉：贴页面底部弹出，覆盖除平台导航外的整块内容区，不随表格滚动 */}
        {eventsRow ? (
          <RumEventsDrawer
            colKey={eventsDrawerCtx.colKey.value}
            displayFieldKeys={this.columnConfig.displayFields.value}
            fields={this.columnConfig.displayableFields.value}
            isShow={eventsDrawerCtx.show.value}
            row={eventsRow}
            onConditionChange={this.handleConditionChange}
            onUpdate:isShow={(value: boolean) => {
              /* 关闭统一走 closeDrawer：主表激活单元格高亮随抽屉关闭清除，激活行高亮保留（不随关闭清空） */
              if (value) {
                eventsDrawerCtx.show.value = true;
              } else {
                eventsDrawerCtx.closeDrawer();
              }
            }}
          />
        ) : null}

        <EditFavorite
          data={favoriteCtx.editFavoriteData.value}
          isCreate={true}
          isShow={favoriteCtx.editFavoriteShow.value}
          onClose={() => {
            favoriteCtx.editFavoriteShow.value = false;
          }}
          onSuccess={() => {
            favoriteCtx.editFavoriteShow.value = false;
          }}
        />
      </div>
    );
  },
});
