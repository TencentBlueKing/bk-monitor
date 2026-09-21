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
import { computed, defineComponent, onBeforeUnmount, onMounted, shallowRef, useTemplateRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import RetrievalFilter from '../../components/retrieval-filter/retrieval-filter';
import { type IHandleGetUserConfig, EMethod, EMode } from '../../components/retrieval-filter/typing';
import {
  mergeWhereList,
  traceWhereChangeFormatter,
  traceWhereFormatter,
} from '../../components/retrieval-filter/utils';
import { handleTransformToTimestamp } from '../../components/time-range/utils';
import useUserConfig from '../../hooks/useUserConfig';
import { updateTimezone } from '../../i18n/dayjs';
import { useRumExploreStore } from '../../store/modules/rum-explore';
import FavoriteBox, { EditFavorite } from '../trace-explore/components/favorite-box';
import TraceExploreLayout from '../trace-explore/components/trace-explore-layout';
import { safeParseJsonValueForWhere } from '../trace-explore/utils';
import RumDimensionPanel from './components/rum-dimension-panel';
import RumExploreHeader from './components/rum-explore-header';
import RumExploreTable from './components/rum-explore-table';
import RumExploreView from './components/rum-explore-view/rum-explore-view';
import RumSpanTypeFilter from './components/rum-span-type-filter';
import {
  useRumColumnConfig,
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
  RUM_DETAIL_SPAN_TYPES,
  RUM_RESIDENT_SETTING_KEY,
  RumModeEnum,
  SPAN_TYPE_FIELD,
} from './constants';
import RumSpanDetailSlider from './detail';
import { getApplicationList } from './services/rum-application';
import EmptyStatus from '@/components/empty-status/empty-status';

import type { ConditionChangeEvent } from '../trace-explore/typing';
import type { IRumDetailContext } from './detail';
import type { IRumApplication, IRumColumnLayoutPreset } from './typings';

import './rum-explore.scss';

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

    const isCollapsed = shallowRef(false);
    /** Span 详情抽屉的上下文，为 null 时抽屉关闭 */
    const detailContext = shallowRef<IRumDetailContext | null>(null);
    const detailShow = shallowRef(false);
    const applicationLoading = shallowRef(false);
    const applicationList = shallowRef<IRumApplication[]>([]);
    const thumbtackList = shallowRef<string[]>([]);
    const defaultApplication = shallowRef('');

    const viewConfigCtx = useRumViewConfig();
    const spanTypeCtx = useRumSpanType(viewConfigCtx.viewConfig);
    const queryCtx = useRumQuery({ extraFilters: spanTypeCtx.spanTypeFilters });
    // 先恢复 URL，再初始化依赖应用的配置，避免沿用上一次进入页面的应用。
    queryCtx.initFromUrl();
    const tableCtx = useRumTableData(queryCtx.commonParams);
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

    /** 详情抽屉对应的表格高亮行：上一个 / 下一个切换与关闭抽屉时跟随 detailContext 同步 */
    const detailActiveRowKeys = computed<string[]>(() =>
      detailContext.value?.record_id ? [detailContext.value.record_id] : []
    );

    /** 当前视角的列布局预设（默认列宽 / 固定列）：列配置与列设置面板共用同一份声明 */
    const layoutPreset = computed<IRumColumnLayoutPreset>(() => RUM_COLUMN_LAYOUT_PRESET[store.mode] ?? {});

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

    /** 自动刷新 */
    let autoRefreshTimer: number = null;
    watch(
      () => store.refreshInterval,
      interval => {
        window.clearInterval(autoRefreshTimer);
        if (!(interval > 0)) return;
        autoRefreshTimer = window.setInterval(() => tableCtx.fetchList(), interval);
      },
      { immediate: true }
    );

    async function fetchApplicationList() {
      applicationLoading.value = true;
      const list = await getApplicationList().catch(() => []);
      applicationLoading.value = false;
      applicationList.value = list;
      store.appList = list;
      if (store.appName && list.some(item => item.app_name === store.appName)) return;
      const preferred = defaultApplication.value || thumbtackList.value[0];
      store.appName = list.some(item => item.app_name === preferred) ? preferred : list[0]?.app_name || '';
    }

    async function fetchUserConfig() {
      await Promise.all([
        getDefaultAppConfig<string>(RUM_EXPLORE_DEFAULT_APPLICATION).then(res => {
          defaultApplication.value = res || '';
        }),
        getThumbtackConfig<string[]>(RUM_EXPLORE_APPLICATION_THUMBTACK).then(res => {
          thumbtackList.value = res || [];
        }),
      ]);
    }

    function handleAppNameChange() {
      queryCtx.where.value = [];
      queryCtx.commonWhere.value = [];
      setDefaultAppConfig(JSON.stringify(store.appName));
      queryCtx.handleQuery();
    }

    function handleModeChange() {
      // 切换场景：排序重置为「未设置」，回落到新场景视图配置的 default_sort
      store.userSort = null;
      queryCtx.handleQuery();
    }

    function handleSpanTypeChange(type: string) {
      spanTypeCtx.setSpanType(type);
      // setSpanType 是 toggle 语义（再次点击已选中的类型会切回「全部」），判断必须基于切换后的 activeSpanType，不能用入参 type
      const activeType = spanTypeCtx.activeSpanType.value;
      // 切回「全部」清空常驻条件；具体类型只保留可见常驻字段的交集，空配置也必须清空。
      if (activeType === ALL_SPAN_TYPE) {
        queryCtx.commonWhere.value = [];
      } else {
        queryCtx.commonWhere.value = queryCtx.commonWhere.value.filter(w =>
          spanTypeResidentFields.value.includes(w.key)
        );
      }
      queryCtx.handleQuery();
    }

    async function handleThumbtackChange(list: string[]) {
      thumbtackList.value = list;
      await setThumbtackConfig(JSON.stringify(list));
    }

    /** 维度面板与表格单元格触发的条件追加 */
    function handleConditionChange(condition: ConditionChangeEvent, isFromDimensionFilterPanel = true) {
      const { key, method: operator, value } = condition;
      const field = viewConfigCtx.viewConfig.value.fields.find(item => item.name === key);
      /** 范围值 */
      const isRangeValue =
        (field.field_display_type === 'duration' && field.field_unit !== 'vital') || field.field_unit === 'bytes';
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
      if (queryCtx.filterMode.value === EMode.ui) {
        query.where = encodeURIComponent(
          JSON.stringify(
            mergeWhereList(
              queryCtx.where.value,
              [
                {
                  key,
                  operator,
                  value: isRangeValue && matched ? [matched[1], matched[2]] : safeParseJsonValueForWhere(value),
                },
              ],
              isFromDimensionFilterPanel
            )
          )
        );
      } else {
        // 语句模式：默认拼等值/取反子句，区间值改用 ES 的 range 语法
        let endStr = `${operator === EMethod.eq ? '' : 'NOT '}${key} : "${value || ''}"`;
        if (isRangeValue && matched) {
          endStr = `${key} : [${matched[1]} TO ${matched[2] || matched[1]}]`;
        }
        query.queryString = encodeURIComponent(
          queryCtx.queryString.value ? `${queryCtx.queryString.value} AND ${endStr}` : endStr
        );
      }
      // 复用当前查询态另开一页：新页走 initFromUrl 还原，故不改动本页 store
      window.open(router.resolve({ path: route.path, query }).href, '_blank');
    }

    /**
     * 打开 Span 详情：详情所需的应用、记录 ID、类型与时间都能从列表行与当前查询条件里取到，
     * 不额外请求列表接口。
     */
    function handleOpenDetail(row: Record<string, unknown>) {
      const [startTime, endTime] = handleTransformToTimestamp(store.timeRange);
      detailContext.value = {
        app_name: store.appName,
        record_id: String(row?.span_id ?? ''),
        span_type: String(row?.[SPAN_TYPE_FIELD] ?? ''),
        start_time: startTime,
        end_time: endTime,
      };
      detailShow.value = true;
      queryCtx.setUrlParams({
        detailShow: encodeURIComponent(JSON.stringify(detailShow.value)),
        detailContext: encodeURIComponent(JSON.stringify(detailContext.value)),
      });
    }

    const handleSpanDetailShowChange = (show: boolean) => {
      detailShow.value = show;
      if (!show) detailContext.value = null;
      queryCtx.setUrlParams({
        detailShow: encodeURIComponent(JSON.stringify(detailShow.value)),
        detailContext: encodeURIComponent(JSON.stringify(detailContext.value)),
      });
    };

    /**
     * 详情抽屉「上一条 / 下一条」共用逻辑：从当前记录出发按 step 方向查找相邻的可展示详情记录，
     * 跳过非详情展示的 span 类型，循环到头后从另一头继续；转完一圈仍没找到则停留在当前记录。
     */
    function handleStepDetail(step: -1 | 1) {
      const tableData = tableCtx.tableData.value;
      if (!tableData.length) return;
      const currentIndex = Math.max(
        0,
        tableData.findIndex(item => item.span_id === detailContext.value?.record_id)
      );
      // 最多回绕一整圈，offset 走到与起点重合即说明没有其他可展示详情的记录
      for (let offset = 1; offset <= tableData.length; offset++) {
        const index = (currentIndex + step * offset + tableData.length) % tableData.length;
        if (index === currentIndex) return;
        if (RUM_DETAIL_SPAN_TYPES.has(tableData[index][SPAN_TYPE_FIELD] ?? '')) {
          handleOpenDetail(tableData[index]);
          return;
        }
      }
    }

    const handlePreviousDetail = () => handleStepDetail(-1);

    const handleNextDetail = () => handleStepDetail(1);

    function handleSortChange(sort: string | string[]) {
      tableCtx.handleSortChange(sort);
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

    onMounted(async () => {
      updateTimezone(store.timezone);
      await fetchUserConfig();
      await fetchApplicationList();
      queryCtx.handleQuery();
      const query = route.query as Record<string, string>;
      if (query.detailShow) {
        detailShow.value = JSON.parse(decodeURIComponent(query.detailShow));
      }
      if (query.detailContext) {
        detailContext.value = JSON.parse(decodeURIComponent(query.detailContext));
      }
    });

    onBeforeUnmount(() => {
      window.clearInterval(autoRefreshTimer);
    });

    return {
      t,
      route,
      store,
      applicationList,
      applicationLoading,
      columnConfig,
      detailContext,
      detailShow,
      detailActiveRowKeys,
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
      spanTypeCtx,
      tableCtx,
      thumbtackList,
      viewConfigCtx,
      retrievalFields,
      getFieldValues,
      getResidentConfig,
      getResidentConfigCustom,
      setResidentConfig,
      handleAppNameChange,
      handleConditionChange,
      handleModeChange,
      handleOpenDetail,
      handleSortChange,
      handleSpanTypeChange,
      handleThumbtackChange,
      handleCreateApp,
      tagValueDisplayFormatter,
      handlePreviousDetail,
      handleNextDetail,
      handleRumSpanDetailConditionAdd,
      handleSpanDetailShowChange,
    };
  },
  render() {
    const { favoriteCtx, queryCtx, spanTypeCtx, tableCtx, viewConfigCtx } = this;

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
            onChange={favoriteCtx.applyFavorite}
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
            {viewConfigCtx.loading.value ? (
              <div class='skeleton-element filter-skeleton' />
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
                handleSetUserConfig={this.setResidentConfig}
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
                onCommonWhereChange={value => {
                  queryCtx.commonWhere.value = value;
                  queryCtx.handleQuery();
                }}
                onCopyWhere={queryCtx.copyWhere}
                onFavorite={isEdit => favoriteCtx.saveFavorite(isEdit, () => this.favoriteBoxRef?.refreshGroupList())}
                onModeChange={queryCtx.modeChange}
                onQueryStringChange={queryCtx.queryStringChange}
                onSearch={queryCtx.handleQuery}
                onShowResidentBtnChange={queryCtx.showResidentChange}
                onWhereChange={queryCtx.whereChange}
              />
            )}
            {!this.applicationLoading && !this.applicationList.length && (
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
            {!this.applicationLoading && !!this.applicationList.length && (
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
                      loading={viewConfigCtx.loading.value}
                      timeRange={this.store.timeRange}
                      onClose={() => {
                        this.isCollapsed = true;
                      }}
                      onConditionChange={this.handleConditionChange}
                    />
                  ),
                  default: () => (
                    <div class='result-panel'>
                      <RumExploreView
                        ref='rumExploreViewRef'
                        v-slots={{
                          affixedTop: () => (
                            <RumSpanTypeFilter
                              list={spanTypeCtx.chipList.value}
                              loading={viewConfigCtx.loading.value}
                              value={spanTypeCtx.activeSpanType.value}
                              onChange={this.handleSpanTypeChange}
                            />
                          ),
                          default: () => (
                            <RumExploreTable
                              headerAffixedTop={{
                                container: () => this.rumExploreViewRef?.$el,
                                // span 模式下表格上方有 RumSpanTypeFilter 吸顶区域（高度 56px：padding 12 + chip 32 + padding 12）
                                offsetTop: this.isSpanMode ? 56 : 0,
                              }}
                              baseColumns={this.columnConfig.baseColumns.value}
                              commonParams={queryCtx.commonParams.value}
                              data={tableCtx.tableData.value}
                              defaultActiveRowKeys={this.detailActiveRowKeys}
                              defaultFieldKeys={this.columnConfig.defaultDisplayFields.value}
                              displayableFields={this.columnConfig.displayableFields.value}
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
                              onClearFilter={queryCtx.clearQuery}
                              onColumnResizeChange={width => this.columnConfig.updateColumnResizeWidth(width)}
                              onConditionChange={this.handleConditionChange}
                              onDisplayFieldChange={fields => this.columnConfig.updateDisplayFields(fields)}
                              onOpenDetail={this.handleOpenDetail}
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
          context={this.detailContext}
          fields={viewConfigCtx.viewConfig.value.fields}
          isShow={this.detailShow}
          mode={this.store.mode}
          onConditionAdd={(key, value) =>
            this.handleRumSpanDetailConditionAdd({ key, method: EMethod.eq, value }, false)
          }
          onNext={this.handleNextDetail}
          onPrevious={this.handlePreviousDetail}
          onUpdate:isShow={this.handleSpanDetailShowChange}
        />

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
