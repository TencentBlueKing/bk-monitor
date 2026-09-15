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
import { type ComputedRef, type Ref, computed, inject, onUnmounted, shallowRef } from 'vue';

import { Message } from 'bkui-vue';
import { getLogFields, getPanelDetail } from 'monitor-api/modules/incident';
import { createUserConfig, listUserConfig, partialUpdateUserConfig } from 'monitor-api/modules/model';
import { copyText } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import {
  type TClickMenuOpt,
  EClickMenuType,
} from '../../../alarm-center/common-detail/components/panel-log/log-table/typing';
import { normalizeEventTableRow, normalizeLogFieldsPayload, resolveLogDisplayFields } from '../utils';

import type { IncidentDetailData } from '../../failure-topo/types';
import type { IOpenDrawerContext } from '../interaction-handler';

/** 事件表格侧滑每页条数（与 EventTable 默认 limit 对齐） */
const EVENT_DRAWER_PAGE_SIZE = 30;
/**
 * 日志表格侧滑每页条数。
 * 必须与 LogTableNew 内部 limit（默认 30）一致，
 * 这样预拉 / getFieldsData / getTableData 共用同一缓存 key，只打一次 panel_detail。
 */
const LOG_DRAWER_PAGE_SIZE = 30;
const EMPTY_SORT_LIST: Array<[string, string]> = [];

/**
 * drawer-detail 渲染上下文。
 * 由 useDrawerDetail().getRenderContext() 生成，供 drawer-detail.tsx 的 renderDrawerDetail 消费。
 * 所有 ref/computed 均已解包为值，渲染函数无需访问 .value。
 */
export interface DrawerRenderContext {
  columnConfigEnabled: boolean;
  currentDrawerContext: IOpenDrawerContext | null;
  defaultDisplayFields: string[];
  displayColumnFields: string[];
  drawerErrorMessage: string;
  drawerRenderKey: number;
  eventTableSliderShowMask: boolean;
  logAllowedMenuTypes: EClickMenuType[];
  logHeaderAffixedTop: { container: () => HTMLElement | null; offsetTop: number };
  logSliderShowMask: boolean;
  logTableRefreshKey: string;
  showEventTableSideslider: boolean;
  showLogSideslider: boolean;
  tableColumnsSetting: Array<{ id: string; name: string; type?: any }>;
  /** 事件侧滑关闭回调（onClosed） */
  closeEventTableSlider: () => void;
  eventScrollContainer: () => HTMLElement | null;
  getEventTableData: (params: {
    limit: number;
    offset: number;
    sort: string[];
    sources: string[];
  }) => Promise<{ data: any[]; total: number }>;
  getLogFieldsData: () => Promise<ReturnType<typeof normalizeLogFieldsPayload>>;
  getLogTableData: (params: {
    offset?: number;
    size?: number;
    sortList?: Array<[string, string]>;
  }) => Promise<Record<string, any>>;
  handleAddField: (fieldName: string) => void;
  handleDisplayColumnFieldsChange: (val: string[]) => void;
  handleLogClickMenu: (opt: TClickMenuOpt) => void;
  handleRemoveField: (fieldName: string) => void;
  setEventScrollBodyRef: (element: HTMLElement | null) => void;
  setLogScrollBodyRef: (element: HTMLElement | null) => void;
  /** 日志侧滑 isShow 同步回调（onUpdate:isShow） */
  setLogSidesliderShow: (value: boolean) => void;
  t: (key: string) => string;
}

/**
 * 日志 / 事件表格侧滑的状态与逻辑。
 * mask computed 依赖主文件的 showSideSlider / showAllEventsSideslider，因此由主文件定义后传入。
 * 主文件的 beforeCloseModuleSlider / beforeCloseAllEventsSlider 通过返回的 showLogSideslider /
 * showEventTableSideslider 访问本 composable 的显隐状态，实现多层 mask 联动。
 */
export function useDrawerDetail(options: {
  eventTableSliderShowMask: ComputedRef<boolean>;
  logSliderShowMask: ComputedRef<boolean>;
}) {
  const { t } = useI18n();
  const route = useRoute();
  const bkzIds = inject<Ref<string[]>>('bkzIds');
  const incidentDetail = inject<Ref<IncidentDetailData>>('incidentDetail');
  const incidentDetailData: Ref<IncidentDetailData> = computed(() => incidentDetail.value);

  // 是否展示日志侧滑
  const showLogSideslider = shallowRef(false);
  // 是否展示事件表格侧滑
  const showEventTableSideslider = shallowRef(false);
  // 当前详情侧滑上下文及分页缓存，detail_ref 始终原样回传
  const currentDrawerContext = shallowRef<IOpenDrawerContext | null>(null);
  const drawerPayloadCache = new Map<string, Promise<Record<string, any>>>();
  // 仅管理故障诊断侧滑的请求，避免修改公共日志/事件表格组件的行为
  const drawerRequestControllers = new Map<string, AbortController>();
  // 切换或关闭侧滑时递增，用于隔离旧请求返回后的异步回调
  let drawerContextVersion = 0;
  const drawerRenderKey = shallowRef(0);
  // 侧滑详情请求错误信息
  const drawerErrorMessage = shallowRef('');
  const displayColumnFields = shallowRef<string[]>([]);
  const tableColumnsSetting = shallowRef<Array<{ id: string; name: string; type?: any }>>([]);
  const logTableRefreshKey = shallowRef('');
  const logDefaultDisplayFields = shallowRef<string[]>([]);
  const logCapabilities = shallowRef({ column_config: true, sort: true });
  const logConfigId = shallowRef<number | string>('');
  const logConfigKey = shallowRef('');
  const logConfigReadFailed = shallowRef(false);
  const logFieldsCache = new Map<string, Promise<Record<string, any>>>();
  // 内层滚动容器：无 padding，表格在此竖向滚动；表头吸顶 / 横向吸底都相对它
  const logScrollBodyRef = shallowRef<HTMLElement | null>(null);
  const setLogScrollBodyRef = (element: HTMLElement | null) => {
    logScrollBodyRef.value = element;
  };
  const logHeaderAffixedTop = {
    offsetTop: 0,
    container: () => logScrollBodyRef.value,
  };
  const eventScrollBodyRef = shallowRef<HTMLElement | null>(null);
  const setEventScrollBodyRef = (element: HTMLElement | null) => {
    eventScrollBodyRef.value = element;
  };
  const eventScrollContainer = () => eventScrollBodyRef.value;

  /**
   * 使当前侧滑的所有请求失效。
   * 先递增版本号再取消请求，确保已经进入微任务队列的旧回调也不会更新新侧滑状态。
   */
  const cancelDrawerRequests = () => {
    drawerContextVersion += 1;
    for (const controller of drawerRequestControllers.values()) {
      controller.abort();
    }
    drawerRequestControllers.clear();
    drawerPayloadCache.clear();
  };

  let logConfigRequestSeq = 0;
  /** 把字段配置请求纳入侧滑取消范围，关闭或切换侧滑时和 panel_detail 一起中止 */
  const trackDrawerRequest = () => {
    const key = `log-config:${++logConfigRequestSeq}`;
    const controller = new AbortController();
    drawerRequestControllers.set(key, controller);
    return { key, controller };
  };
  const releaseDrawerRequest = (key: string, controller: AbortController) => {
    if (drawerRequestControllers.get(key) === controller) drawerRequestControllers.delete(key);
  };

  /** 获取侧滑详情数据，同一侧滑、分页、容量和排序只发起一次请求。 */
  const fetchDrawerPayload = (
    page: number,
    pageSize: number,
    sortList: Array<[string, string]> = EMPTY_SORT_LIST
  ): Promise<Record<string, any>> => {
    const context = currentDrawerContext.value;
    if (!context?.detailRef) {
      return Promise.resolve<Record<string, any>>({});
    }

    const requestVersion = drawerContextVersion;
    const normalizedSortList = sortList
      .filter(item => item?.[0])
      .map(([field, direction]) => [field, direction === 'desc' ? 'desc' : 'asc'] as [string, string]);
    const cacheKey = `${requestVersion}:${context.drawerType}:${page}:${pageSize}:${JSON.stringify(normalizedSortList)}`;
    const cached = drawerPayloadCache.get(cacheKey);
    if (cached) return cached;

    const incidentId = Number(incidentDetailData.value?.incident_id);
    const incidentTaskId =
      context.detailRef.incident_task_id ??
      route.query.incident_task_id ??
      incidentDetailData.value?.extra_info?.task_id;

    if (!incidentId || !incidentTaskId) {
      const message = t('缺少故障分析任务信息，无法打开详情');
      if (requestVersion === drawerContextVersion) {
        drawerErrorMessage.value = message;
      }
      return Promise.reject(new Error(message));
    }

    const controller = new AbortController();
    drawerRequestControllers.set(cacheKey, controller);
    const requestParams = {
      bk_biz_id: Number(bkzIds.value[0]),
      incident_id: incidentId,
      incident_task_id: Number(incidentTaskId),
      drawer_type: context.drawerType,
      detail_ref: context.detailRef,
      page,
      page_size: pageSize,
      sort_list: normalizedSortList,
    };
    const requestPromise: Promise<Record<string, any>> = getPanelDetail(requestParams, {
      signal: controller.signal,
    })
      .then((res: any) => {
        if (res?.drawer_type && res.drawer_type !== context.drawerType) {
          throw new Error(t('侧滑详情类型不匹配'));
        }
        if (requestVersion === drawerContextVersion) {
          drawerErrorMessage.value = '';
        }
        return (res?.payload || {}) as Record<string, any>;
      })
      .catch(err => {
        if (drawerPayloadCache.get(cacheKey) === requestPromise) drawerPayloadCache.delete(cacheKey);
        if (drawerRequestControllers.get(cacheKey) === controller) drawerRequestControllers.delete(cacheKey);
        if (requestVersion === drawerContextVersion && !controller.signal.aborted) {
          const message = err?.message || t('获取侧滑详情失败');
          drawerErrorMessage.value = message;
          Message({ message, theme: 'error' });
        }
        throw err;
      });
    drawerPayloadCache.set(cacheKey, requestPromise);
    return requestPromise;
  };

  const getLogConfigKey = (queryContext: Record<string, any>) => {
    const bizId = queryContext?.bk_biz_id ?? bkzIds.value[0];
    const indexSetId = queryContext?.index_set_id;
    return indexSetId ? `incident_log_drawer:v1:biz:${bizId}:index_set:${indexSetId}` : '';
  };

  const loadLogColumnConfig = async (queryContext: Record<string, any>, requestVersion: number) => {
    const key = getLogConfigKey(queryContext);
    // 侧滑已经切走时，不能清掉新侧滑刚写上的 key / id
    if (requestVersion !== drawerContextVersion) return undefined;
    logConfigKey.value = key;
    logConfigId.value = '';
    logConfigReadFailed.value = false;
    if (!key) return undefined;

    const { key: controllerKey, controller } = trackDrawerRequest();
    try {
      const records = await listUserConfig({ key }, { reject403: true, needMessage: false, signal: controller.signal });
      if (controller.signal.aborted || requestVersion !== drawerContextVersion || key !== logConfigKey.value) {
        return undefined;
      }
      const record = records?.[0];
      logConfigId.value = record?.id || '';
      if (!record?.value) return undefined;
      const config = JSON.parse(record.value);
      return Array.isArray(config?.displayFields) ? config.displayFields : undefined;
    } catch (error) {
      if (controller.signal.aborted || requestVersion !== drawerContextVersion) return undefined;
      if (key === logConfigKey.value) logConfigReadFailed.value = true;
      console.error(error);
      return undefined;
    } finally {
      releaseDrawerRequest(controllerKey, controller);
    }
  };

  /** 保存当前侧滑的日志字段。侧滑关闭时请求会被取消，返回后不再写配置 id。 */
  const persistLogColumnConfig = async (displayFields: string[]) => {
    const key = logConfigKey.value;
    const requestVersion = drawerContextVersion;
    if (!key || logConfigReadFailed.value || !logCapabilities.value.column_config) return false;
    const value = JSON.stringify({ version: 1, displayFields });
    const configId = logConfigId.value;
    const { key: controllerKey, controller } = trackDrawerRequest();
    try {
      if (!configId) {
        const created = await createUserConfig(
          { key, value },
          { reject403: true, needMessage: false, signal: controller.signal }
        );
        if (controller.signal.aborted || requestVersion !== drawerContextVersion || key !== logConfigKey.value) {
          return false;
        }
        logConfigId.value = created?.id || '';
      } else {
        await partialUpdateUserConfig(
          configId,
          { value },
          { reject403: true, needMessage: false, signal: controller.signal }
        );
      }
      return !controller.signal.aborted && requestVersion === drawerContextVersion && Boolean(logConfigId.value);
    } catch (error) {
      if (controller.signal.aborted || requestVersion !== drawerContextVersion) return false;
      Message({ message: t('保存日志字段配置失败'), theme: 'error' });
      console.error(error);
      return false;
    } finally {
      releaseDrawerRequest(controllerKey, controller);
    }
  };

  /** 应用字段接口返回的系统默认字段和故障专用用户字段。 */
  const applyLogFieldsConfig = (rawPayload: Record<string, any>, customDisplayFields?: string[]) => {
    const normalizedPayload = normalizeLogFieldsPayload(rawPayload);
    const fields = normalizedPayload.fields || [];
    const fieldNames = new Set(fields.map((item: { field_name: string }) => item.field_name));
    const defaultDisplayFields = normalizedPayload.display_fields || fields.map(item => item.field_name);
    const selectedDisplayFields = (customDisplayFields || []).filter(field => fieldNames.has(field));
    logDefaultDisplayFields.value = [...defaultDisplayFields];
    displayColumnFields.value = selectedDisplayFields.length ? selectedDisplayFields : [...defaultDisplayFields];
    logCapabilities.value = {
      column_config: rawPayload.capabilities?.column_config !== false,
      sort: rawPayload.capabilities?.sort !== false,
    };
    tableColumnsSetting.value = fields.map(
      (item: { field_name: string; field_type?: string; query_alias?: string }) => ({
        id: item.field_name,
        name: item.query_alias || item.field_name,
        type: item.field_type,
      })
    );
    return normalizedPayload;
  };

  /**
   * 实时回查用 panel_detail 的 query_context.index_set_id 再查字段，不拼接日志查询条件。
   * 聚类样本已带 fields，没有索引集，直接使用本次详情。
   */
  const getLogFieldsData = async () => {
    const rawPayload = await fetchDrawerPayload(1, LOG_DRAWER_PAGE_SIZE);
    let fieldsPayload = rawPayload;
    if (rawPayload.log_scope !== 'cluster_samples') {
      const queryContext = rawPayload.query_context || {};
      const cacheKey = `${drawerContextVersion}:${JSON.stringify(queryContext)}`;
      let fieldsRequest = logFieldsCache.get(cacheKey);
      if (!fieldsRequest) {
        const indexSetId = queryContext.index_set_id;
        if (!indexSetId) throw new Error(t('日志查询上下文缺少索引集信息'));
        fieldsRequest = getLogFields(indexSetId, {
          bk_biz_id: queryContext.bk_biz_id,
          start_time: queryContext.start_time,
          end_time: queryContext.end_time,
          is_realtime: 'True',
        }).then((res: any) => ({
          ...rawPayload,
          ...(res?.fields ? res : res?.data || {}),
          query_context: queryContext,
        }));
        logFieldsCache.set(cacheKey, fieldsRequest);
        // 失败不能留在缓存里，否则表格重试会一直命中同一次拒绝
        void fieldsRequest.catch(() => {
          if (logFieldsCache.get(cacheKey) === fieldsRequest) logFieldsCache.delete(cacheKey);
        });
      }
      fieldsPayload = await fieldsRequest;
    }
    const normalized = normalizeLogFieldsPayload(fieldsPayload);
    if (rawPayload.capabilities?.sort === false) {
      normalized.fields = normalized.fields.map(field => ({ ...field, es_doc_values: false }));
    }
    return normalized;
  };

  /** 根据 LogTableNew 的 offset 换算详情接口页码。 */
  const getLogTableData = async ({ offset = 0, size = LOG_DRAWER_PAGE_SIZE, sortList = EMPTY_SORT_LIST }) => {
    return fetchDrawerPayload(Math.floor(offset / size) + 1, size, sortList);
  };
  const handleDisplayColumnFieldsChange = (val: string[]) => {
    const nextFields = resolveLogDisplayFields(val, logDefaultDisplayFields.value);
    displayColumnFields.value = nextFields;
    void persistLogColumnConfig(nextFields);
  };
  // 日志表格字段隐藏（expand-content 中 icon-mc-invisible 点击）
  const handleRemoveField = (fieldName: string) => {
    const nextFields = resolveLogDisplayFields(
      displayColumnFields.value.filter(item => item !== fieldName),
      logDefaultDisplayFields.value
    );
    displayColumnFields.value = nextFields;
    void persistLogColumnConfig(nextFields);
  };
  // 日志表格字段展示（expand-content 中 icon-mc-visual 点击）
  const handleAddField = (fieldName: string) => {
    if (displayColumnFields.value.includes(fieldName)) {
      return;
    }
    const nextFields = [...displayColumnFields.value, fieldName];
    displayColumnFields.value = nextFields;
    void persistLogColumnConfig(nextFields);
  };
  // 日志侧滑表格只允许"复制"菜单项
  const logAllowedMenuTypes = [EClickMenuType.Copy];
  // 日志表格右键菜单回调（处理复制逻辑）
  const handleLogClickMenu = (opt: TClickMenuOpt) => {
    if (opt.type === EClickMenuType.Copy) {
      const copied = copyText(opt.value, msg => {
        Message({
          message: msg,
          theme: 'error',
        });
      });
      if (!copied) return;
      Message({
        message: t('复制成功'),
        theme: 'success',
      });
    }
  };

  /** 按 drawer_type 打开事件/日志侧滑，detail_ref 原样回传详情接口 */
  const onOpenDrawer = async (context: IOpenDrawerContext) => {
    // trace 走页面跳转，不打开事件侧滑，也不请求侧滑详情
    if (context.drawerType === 'trace') {
      return;
    }

    // 新侧滑打开前先取消旧请求，并重置上一侧滑遗留的字段和错误状态。
    cancelDrawerRequests();
    currentDrawerContext.value = context;
    const requestVersion = drawerContextVersion;
    drawerErrorMessage.value = '';
    drawerRenderKey.value += 1;
    logDefaultDisplayFields.value = [];
    displayColumnFields.value = [];
    tableColumnsSetting.value = [];
    logFieldsCache.clear();
    logConfigKey.value = '';
    logConfigId.value = '';
    logConfigReadFailed.value = false;
    logCapabilities.value = { column_config: true, sort: true };
    logTableRefreshKey.value = String(drawerRenderKey.value);

    if (context.drawerType === 'log') {
      // 日志侧滑先展示，LogTableNew 会在接口请求期间显示自身的表格骨架屏。
      showEventTableSideslider.value = false;
      showLogSideslider.value = true;
      void getLogFieldsData()
        .then(async payload => {
          const customDisplayFields = await loadLogColumnConfig(payload.query_context || {}, requestVersion);
          if (requestVersion === drawerContextVersion) applyLogFieldsConfig(payload, customDisplayFields);
        })
        .catch(() => {
          // 请求错误由侧滑或表格状态展示，侧滑保持打开。
        });
      return;
    }

    // 互斥：打开事件侧滑前关闭日志侧滑
    showLogSideslider.value = false;
    showEventTableSideslider.value = false;

    try {
      // 事件侧滑仍需等待详情接口返回后再展示
      await fetchDrawerPayload(1, EVENT_DRAWER_PAGE_SIZE);
    } catch {
      // 接口失败时仍打开侧滑展示错误态，禁止降级为页面跳转
    }

    if (requestVersion === drawerContextVersion && context.drawerType === 'event') {
      showEventTableSideslider.value = true;
    }
  };

  /**
   * 事件表格直接消费 panel_detail 的 payload.list，
   * 不根据 query_config 再发起事件检索请求。
   * 请求异常继续向 EventTable 透传，由表格展示错误态，而不是伪装成空数据。
   */
  const getEventTableData = async (params: { limit: number; offset: number; sort: string[]; sources: string[] }) => {
    // 事件侧滑固定 page_size=30，与日志侧滑分页常量隔离
    const pageSize = EVENT_DRAWER_PAGE_SIZE;
    const payload = await fetchDrawerPayload(Math.floor(params.offset / pageSize) + 1, pageSize);
    const list = (payload.list || []).map((item, index) => normalizeEventTableRow(item, params.offset + index));
    return {
      data: list,
      // 分页总数优先使用 query_config.total
      total: payload.query_config?.total ?? payload.total ?? list.length,
    };
  };

  // 关闭回调统一走这里，确保遮罩、ESC 和侧滑自身关闭都能取消请求。
  const closeLogTableSlider = () => {
    if (currentDrawerContext.value?.drawerType === 'log') {
      cancelDrawerRequests();
    }
    showLogSideslider.value = false;
  };
  const setLogSidesliderShow = (value: boolean) => {
    if (value) {
      showLogSideslider.value = true;
    } else {
      closeLogTableSlider();
    }
  };
  const closeEventTableSlider = () => {
    eventScrollBodyRef.value?.scrollTo({ top: 0, left: 0, behavior: 'auto' });
    if (currentDrawerContext.value?.drawerType === 'event') {
      cancelDrawerRequests();
    }
    showEventTableSideslider.value = false;
  };

  /** 生成渲染上下文：所有 ref/computed 解包为值，渲染函数无需访问 .value */
  const getRenderContext = (): DrawerRenderContext => ({
    showLogSideslider: showLogSideslider.value,
    showEventTableSideslider: showEventTableSideslider.value,
    logSliderShowMask: options.logSliderShowMask.value,
    eventTableSliderShowMask: options.eventTableSliderShowMask.value,
    currentDrawerContext: currentDrawerContext.value,
    drawerErrorMessage: drawerErrorMessage.value,
    drawerRenderKey: drawerRenderKey.value,
    displayColumnFields: displayColumnFields.value,
    defaultDisplayFields: logDefaultDisplayFields.value,
    columnConfigEnabled: logCapabilities.value.column_config,
    tableColumnsSetting: tableColumnsSetting.value,
    logTableRefreshKey: logTableRefreshKey.value,
    logHeaderAffixedTop,
    setLogScrollBodyRef,
    eventScrollContainer,
    setEventScrollBodyRef,
    logAllowedMenuTypes,
    t,
    getLogFieldsData,
    getLogTableData,
    getEventTableData,
    handleLogClickMenu,
    handleAddField,
    handleRemoveField,
    handleDisplayColumnFieldsChange,
    setLogSidesliderShow,
    closeEventTableSlider,
  });

  // 页面销毁时取消尚未完成的侧滑请求，避免离开故障诊断后继续更新状态
  onUnmounted(cancelDrawerRequests);

  return {
    // 显隐状态：主文件 beforeCloseModuleSlider / beforeCloseAllEventsSlider 访问
    showLogSideslider,
    showEventTableSideslider,
    // 入口：shootingModule config 的 onOpenDrawer 用
    onOpenDrawer,
    // 渲染上下文工厂：主文件 render 调用后传给 renderDrawerDetail
    getRenderContext,
    // 关闭侧滑时取消故障诊断详情请求
    closeLogTableSlider,
    closeEventTableSlider,
  };
}
