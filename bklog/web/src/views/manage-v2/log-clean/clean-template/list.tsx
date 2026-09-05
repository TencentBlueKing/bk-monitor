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

import { computed, defineComponent, nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue';

import http from '@/api';
import {
  CleanTemplateSnapshot,
  CleanTemplateStatus,
  resolveCleanTemplateDraft,
} from '@/views/manage-v2/utils/clean-template';
import LogImport from '@/components/log-import/log-import';
import useLocale from '@/hooks/use-locale';
import useResizeObserver from '@/hooks/use-resize-observe';
import useStore from '@/hooks/use-store';
import useUtils from '@/hooks/use-utils';
import TableComponent from '@/views/manage-v2/log-collection/components/common-comp/table-component';
import { tenantManager, UserInfoLoadedEventData } from '@/views/retrieve-core/tenant-manager';
import { Message } from 'bk-magic-vue';
import { useRouter } from 'vue-router/composables';

import './list.scss';
import DeleteConfirmPopover from './delete-confirm-popover';
import CleanTemplateDetailSlider, { DetailTab } from './detail-slider';
import CleanTemplateExportDialog from './export-dialog';
import CleanTemplateSyncSlider, { SyncTemplateItem } from './sync-slider';

type CleanType = 'bk_log_delimiter' | 'bk_log_json' | 'bk_log_regexp' | 'bk_log_text';

interface CleanTemplateEtlParams extends Record<string, unknown> {
  enable_retain_content?: boolean;
  ext_json_config?: {
    expand_depth?: null | number;
    [key: string]: unknown;
  };
  is_grok?: boolean;
  record_parse_failure?: boolean;
  retain_extra_json?: boolean;
  retain_original_text?: boolean;
  separator?: null | string;
  separator_regexp?: null | string;
}

interface CleanTemplateField {
  alias_name: null | string;
  description: string;
  field_index: null | number;
  field_name: string;
  field_type: string;
  is_analyzed: boolean;
  is_built_in: boolean;
  is_delete: boolean;
  is_dimension: boolean;
  is_time: boolean;
  option: Record<string, unknown>;
}

interface CleanTemplateItem {
  active_collector_count: number;
  alias_settings: null | unknown[];
  bk_biz_id: number;
  clean_template_id: number;
  clean_type: CleanType;
  config_version: number;
  created_at: string;
  created_by: string;
  description: string;
  etl_fields: CleanTemplateField[];
  etl_params: CleanTemplateEtlParams;
  field_count: number;
  name: string;
  related_index_set_count: number;
  snapshot?: CleanTemplateSnapshot<CleanType, CleanTemplateEtlParams, CleanTemplateField> | null;
  status: CleanTemplateStatus;
  updated_at: string;
  updated_by: string;
}

interface CleanTemplateImportData {
  clean_type: CleanType;
  description?: string;
  etl_fields: CleanTemplateField[];
  etl_params: CleanTemplateEtlParams;
  name: string;
}

interface Pagination {
  current: number;
  count: number;
  limit: number;
  limitList: number[];
}

interface SortConfig {
  descending?: boolean;
  sortBy?: string;
}

interface FilterOption {
  label: string;
  value: string;
  key?: string;
}

interface OperatorOptions {
  created_by: string[];
  updated_by: string[];
}

const CLEAN_TYPE_CLASS_MAP: Record<string, string> = {
  bk_log_json: 'is-json',
  bk_log_delimiter: 'is-delimiter',
  bk_log_regexp: 'is-regexp',
};

const CLEAN_TYPE_ICON_MAP: Record<string, string> = {
  bk_log_json: 'bklog-icon bklog-json-fanxuliehua',
  bk_log_delimiter: 'bklog-icon bklog-fengefu',
  bk_log_regexp: 'bklog-icon bklog-zhengzetiqu',
};

const EMPTY_TABLE_HEIGHT = 400;
const TABLE_PAGINATION_HEIGHT = 64;
const CLEAN_TYPES: CleanType[] = ['bk_log_delimiter', 'bk_log_json', 'bk_log_regexp', 'bk_log_text'];

const isCleanTemplateImportData = (data: unknown): data is CleanTemplateImportData => {
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    return false;
  }
  const template = data as Partial<CleanTemplateImportData>;
  return (
    typeof template.name === 'string' &&
    CLEAN_TYPES.includes(template.clean_type as CleanType) &&
    Boolean(template.etl_params) &&
    typeof template.etl_params === 'object' &&
    !Array.isArray(template.etl_params) &&
    Array.isArray(template.etl_fields) &&
    (template.description === undefined || typeof template.description === 'string')
  );
};

export default defineComponent({
  name: 'CleanTemplateV2',
  setup() {
    const { t } = useLocale();
    const { formatResponseListTimeZoneString } = useUtils();
    const router = useRouter();
    const store = useStore();

    const isTableLoading = ref(true);
    const templateList = ref<CleanTemplateItem[]>([]);
    const containerRef = ref<HTMLElement | null>(null);
    const tableContainerRef = ref<HTMLElement | null>(null);
    const tableAreaHeight = ref<number>();
    const createdByFilters = ref<FilterOption[]>([]);
    const updatedByFilters = ref<FilterOption[]>([]);
    const sortConfig = ref<SortConfig>({});
    const emptyType = ref('empty');
    const isFilterSearch = ref(false);
    const isImporting = ref(false);
    const exportDialogVisible = ref(false);
    const syncSliderVisible = ref(false);
    const detailSliderVisible = ref(false);
    const detailInitialTab = ref<DetailTab>('fields');
    const activeDetailTemplate = ref<CleanTemplateItem | null>(null);
    const activeSyncTemplate = ref<SyncTemplateItem | null>(null);
    const params = reactive({
      keyword: '',
      clean_type: '',
      created_by: '',
      updated_by: '',
    });
    const pagination = reactive<Pagination>({
      current: 1,
      count: 0,
      limit: 10,
      limitList: [10, 20, 50, 100],
    });

    const bkBizId = computed(() => store.getters.bkBizId);
    const globalsData = computed(() => store.getters['globals/globalsData'] || {});
    const formatFilters = computed(() => {
      return (globalsData.value.etl_config || []).map((item: { id: string; name: string }) => ({
        label: item.name,
        value: item.id,
      }));
    });
    const tablePagination = computed(() => ({
      current: pagination.current,
      pageSize: pagination.limit,
      pageSizeOptions: pagination.limitList,
      total: pagination.count,
    }));
    const tableFilterValue = computed(() => ({
      clean_type: params.clean_type,
      created_by: params.created_by,
      updated_by: params.updated_by,
    }));
    const tableMaxHeight = computed(() => {
      if (tableAreaHeight.value === undefined) {
        return undefined;
      }
      const paginationHeight = templateList.value.length ? TABLE_PAGINATION_HEIGHT : 0;
      return Math.max(0, tableAreaHeight.value - paginationHeight);
    });
    const emptyTableHeight = computed(() => {
      return tableAreaHeight.value === undefined
        ? EMPTY_TABLE_HEIGHT
        : Math.min(EMPTY_TABLE_HEIGHT, tableAreaHeight.value);
    });
    const getFormatName = (row: CleanTemplateItem) => {
      return globalsData.value.etl_config?.find((item: { id: string }) => item.id === row.clean_type)?.name || '--';
    };

    const calculateTableAreaHeight = () => {
      nextTick(() => {
        if (!containerRef.value || !tableContainerRef.value) {
          return;
        }
        const containerRect = containerRef.value.getBoundingClientRect();
        const tableContainerRect = tableContainerRef.value.getBoundingClientRect();
        const paddingBottom = Number.parseFloat(getComputedStyle(containerRef.value).paddingBottom) || 0;
        tableAreaHeight.value = Math.max(0, Math.floor(containerRect.bottom - tableContainerRect.top - paddingBottom));
      });
    };

    useResizeObserver(() => containerRef.value, calculateTableAreaHeight, false);

    // 用户信息映射（username -> display_name）
    const userDisplayNameMap = ref<Map<string, string>>(new Map());

    /** 同步获取用户显示名称 */
    const getName = (username: string | undefined | null) => {
      if (!username) {
        return <span>--</span>;
      }
      const displayName = userDisplayNameMap.value.get(username) || username;
      return <span>{displayName}</span>;
    };

    /** 从过滤选项数组中提取用户ID */
    const extractUserIds = (items: Array<{ key?: string; [key: string]: unknown }>): string[] => {
      return (items || []).map(item => item.key).filter(Boolean) as string[];
    };

    /** 处理过滤选项，用用户显示名称更新 label */
    const processFilterItemsWithUserInfo = (
      items: FilterOption[],
      userInfoMap: Map<string, { display_name: string }>,
    ): FilterOption[] => {
      return (items || []).map(item => ({
        ...item,
        label: userInfoMap.get(item.key || '')?.display_name || item.label || item.value,
      }));
    };

    /** 监听用户信息更新事件，更新显示名称映射和过滤选项 label */
    const handleUserInfoUpdated = (data: UserInfoLoadedEventData) => {
      const newMap = new Map(userDisplayNameMap.value);
      let hasUpdate = false;
      for (const [bkUsername, userInfo] of data.userInfo.entries()) {
        if (userInfo?.display_name && newMap.get(bkUsername) !== userInfo.display_name) {
          newMap.set(bkUsername, userInfo.display_name);
          hasUpdate = true;
        }
      }
      if (hasUpdate) {
        userDisplayNameMap.value = newMap;

        // 同步更新过滤下拉项的 label（created_by / updated_by）
        const updateFilterItems = (items: FilterOption[]): FilterOption[] => {
          if (!items || items.length === 0) return items;
          let changed = false;
          const next = items.map(item => {
            const displayName = newMap.get(item.key || item.value || '');
            if (displayName && displayName !== item.label) {
              changed = true;
              return { ...item, label: displayName };
            }
            return item;
          });
          return changed ? next : items;
        };

        createdByFilters.value = updateFilterItems(createdByFilters.value);
        updatedByFilters.value = updateFilterItems(updatedByFilters.value);
      }
    };

    const formatOperatorFilters = (operators: string[]): FilterOption[] => {
      return operators.map(operator => ({
        label: operator,
        value: operator,
        key: operator,
      }));
    };

    const getOrdering = () => {
      const { descending, sortBy } = sortConfig.value;
      if (!sortBy) {
        return '';
      }
      return descending ? `-${sortBy}` : sortBy;
    };

    const requestData = async () => {
      isTableLoading.value = true;
      emptyType.value = params.keyword || isFilterSearch.value ? 'search-empty' : 'empty';
      try {
        const ordering = getOrdering();
        const query: Record<string, unknown> = {
          bk_biz_id: bkBizId.value,
          page: pagination.current,
          pagesize: pagination.limit,
          ...(ordering && { ordering }),
        };
        if (params.keyword) query.keyword = params.keyword;
        if (params.clean_type) query.clean_type = params.clean_type;
        if (params.created_by) query.created_by = params.created_by;
        if (params.updated_by) query.updated_by = params.updated_by;
        const res = await http.request('clean/cleanTemplate', {
          query,
        });
        pagination.count = res.data.total;
        const formattedList = formatResponseListTimeZoneString(res.data.list || []) as CleanTemplateItem[];
        templateList.value = formattedList.map(resolveCleanTemplateDraft);

        // 批量获取用户信息，更新显示名称映射
        const userIds = new Set<string>();
        for (const item of formattedList) {
          if (item.created_by) {
            userIds.add(item.created_by);
          }
          if (item.updated_by) {
            userIds.add(item.updated_by);
          }
        }
        if (userIds.size > 0) {
          // 批量获取用户信息，直接用返回值更新显示名称映射
          // （已缓存的用户不会触发 userInfoUpdated 事件，需要同步处理）
          const userInfoMap = await tenantManager.batchGetUserDisplayInfo(Array.from(userIds));
          const newMap = new Map(userDisplayNameMap.value);
          let hasUpdate = false;
          for (const [bkUsername, userInfo] of userInfoMap.entries()) {
            if (userInfo?.display_name && newMap.get(bkUsername) !== userInfo.display_name) {
              newMap.set(bkUsername, userInfo.display_name);
              hasUpdate = true;
            }
          }
          if (hasUpdate) {
            userDisplayNameMap.value = newMap;
          }
        }
      } catch (err) {
        console.warn(err);
      } finally {
        isTableLoading.value = false;
      }
    };

    const requestOperatorOptions = async () => {
      try {
        const res = await http.request('clean/cleanTemplateOperators', {
          query: {
            bk_biz_id: bkBizId.value,
          },
        });
        const operatorOptions = res.data as OperatorOptions;
        const createdByList = formatOperatorFilters(operatorOptions.created_by || []);
        const updatedByList = formatOperatorFilters(operatorOptions.updated_by || []);

        // 提取所有用户ID并去重
        const createdByUserIds = extractUserIds(createdByList);
        const updatedByUserIds = extractUserIds(updatedByList);
        const allUserIds = [...new Set([...createdByUserIds, ...updatedByUserIds])];

        // 批量获取用户信息
        let userInfoMap = new Map<string, { display_name: string }>();
        if (allUserIds.length > 0) {
          userInfoMap = await tenantManager.batchGetUserDisplayInfo(allUserIds);
          // 同步更新显示名称映射（已缓存的用户不会触发 userInfoUpdated 事件）
          const newMap = new Map(userDisplayNameMap.value);
          let hasUpdate = false;
          for (const [bkUsername, userInfo] of userInfoMap.entries()) {
            if (userInfo?.display_name && newMap.get(bkUsername) !== userInfo.display_name) {
              newMap.set(bkUsername, userInfo.display_name);
              hasUpdate = true;
            }
          }
          if (hasUpdate) {
            userDisplayNameMap.value = newMap;
          }
        }

        // 处理过滤选项，添加用户显示名称
        createdByFilters.value = processFilterItemsWithUserInfo(createdByList, userInfoMap);
        updatedByFilters.value = processFilterItemsWithUserInfo(updatedByList, userInfoMap);
      } catch (err) {
        createdByFilters.value = [];
        updatedByFilters.value = [];
        console.warn(err);
      }
    };

    const search = () => {
      pagination.current = 1;
      requestData();
    };

    const handleCreate = () => {
      router.push({
        name: 'clean-template-create',
        query: {
          spaceUid: store.state.spaceUid,
        },
      });
    };

    const handleImport = async (fileContent: unknown) => {
      let importData: unknown;
      try {
        importData = JSON.parse(String(fileContent));
      } catch {
        Message({
          theme: 'warning',
          message: t('请导入正确的JSON格式文件~'),
        });
        return;
      }
      if (!isCleanTemplateImportData(importData)) {
        Message({
          theme: 'warning',
          message: t('请导入正确的JSON格式文件~'),
        });
        return;
      }

      isImporting.value = true;
      try {
        const res = await http.request('clean/createTemplate', {
          data: {
            name: `${t('导入模板')}-${importData.name}`,
            description: importData.description || '',
            bk_biz_id: bkBizId.value,
            clean_type: importData.clean_type,
            etl_params: importData.etl_params,
            etl_fields: importData.etl_fields,
          },
        });
        if (!res.result) {
          return;
        }
        Message({
          theme: 'success',
          message: t('导入成功'),
        });
        pagination.current = 1;
        await Promise.all([requestData(), requestOperatorOptions()]);
      } catch (error) {
        console.warn(error);
      } finally {
        isImporting.value = false;
      }
    };

    const handleEdit = (row: CleanTemplateItem) => {
      router.push({
        name: 'clean-template-edit',
        params: {
          templateId: `${row.clean_template_id}`,
        },
        query: {
          spaceUid: store.state.spaceUid,
          editName: row.name,
        },
      });
    };

    const handleOpenDetailSlider = (row: CleanTemplateItem, initialTab: DetailTab = 'fields') => {
      activeDetailTemplate.value = row;
      detailInitialTab.value = initialTab;
      detailSliderVisible.value = true;
    };

    const handleCloseDetailSlider = () => {
      detailSliderVisible.value = false;
    };

    const handleOpenSyncSlider = (row: SyncTemplateItem) => {
      activeSyncTemplate.value = row;
      syncSliderVisible.value = true;
    };

    const handleCloseSyncSlider = () => {
      syncSliderVisible.value = false;
    };

    const handleDetailEdit = (row: CleanTemplateItem) => {
      handleCloseDetailSlider();
      handleEdit(row);
    };

    const handleDetailSync = (row: SyncTemplateItem) => {
      handleCloseDetailSlider();
      handleOpenSyncSlider(row);
    };

    const requestDelete = async (row: CleanTemplateItem) => {
      const res = await http.request('clean/deleteTemplate', {
        params: {
          clean_template_id: row.clean_template_id,
        },
      });
      if (!res.result) {
        return;
      }
      const targetPage =
        templateList.value.length <= 1 && pagination.current > 1 ? pagination.current - 1 : pagination.current;
      Message({
        theme: 'success',
        message: t('删除成功'),
      });
      if (targetPage !== pagination.current) {
        pagination.current = targetPage;
      }
      await requestData();
    };

    const handleFilterChange = (filterData: Record<string, string>) => {
      params.clean_type = filterData.clean_type || '';
      params.created_by = filterData.created_by || '';
      params.updated_by = filterData.updated_by || '';
      isFilterSearch.value = Boolean(params.clean_type || params.created_by || params.updated_by);
      search();
    };

    const handleSortChange = (sort: SortConfig) => {
      sortConfig.value = sort || {};
      pagination.current = 1;
      requestData();
    };

    const handlePageChange = ({ current, pageSize }: { current: number; pageSize: number }) => {
      const isPageSizeChanged = pagination.limit !== pageSize;
      const nextPage = isPageSizeChanged ? 1 : current;
      if (pagination.current === nextPage && !isPageSizeChanged) {
        return;
      }
      pagination.current = nextPage;
      pagination.limit = pageSize;
      requestData();
    };

    const handleSearchChange = (value: string) => {
      params.keyword = value;
      if (!value && !isTableLoading.value) {
        search();
      }
    };

    const handleOperation = () => {
      params.keyword = '';
      params.clean_type = '';
      params.created_by = '';
      params.updated_by = '';
      isFilterSearch.value = false;
      search();
    };

    const renderName = (row: CleanTemplateItem) => {
      const iconClass = CLEAN_TYPE_ICON_MAP[row.clean_type];
      return (
        <div class='template-info'>
          {iconClass && (
            <div class='template-icon'>
              <i class={iconClass} />
            </div>
          )}
          <div class='template-meta'>
            <button
              class='template-name'
              type='button'
              v-bk-overflow-tips
              onClick={() => handleOpenDetailSlider(row)}
            >
              {row.name}
            </button>
            {row.description && (
              <span
                class='template-description'
                v-bk-overflow-tips
              >
                {row.description}
              </span>
            )}
          </div>
        </div>
      );
    };

    const renderOperatorTime = (operator?: string, time?: string) => (
      <div class='operator-time'>
        {getName(operator)}
        <span>{time || '--'}</span>
      </div>
    );

    const getColumnsFilter = (filterList: FilterOption[]) => ({
      type: 'single',
      list: [{ label: t('全部'), value: '' }, ...filterList],
      confirmEvents: ['onChange'],
      popupProps: {
        overlayInnerClassName: 't-table__list-filter-input--sticky custom-filter-popup',
      },
    });

    const columns = computed(() => [
      {
        title: t('模板名称 / 描述'),
        colKey: 'name',
        minWidth: 200,
        cell: (_h, { row }: { row: CleanTemplateItem }) => renderName(row),
      },
      {
        title: t('清洗方式'),
        colKey: 'clean_type',
        width: 170,
        filter: getColumnsFilter(formatFilters.value),
        cell: (_h, { row }: { row: CleanTemplateItem }) => (
          <span class={['clean-type-tag', CLEAN_TYPE_CLASS_MAP[row.clean_type]]}>{getFormatName(row)}</span>
        ),
      },
      {
        title: t('字段数量'),
        colKey: 'field_count',
        width: 160,
        sorter: true,
        sortType: 'all',
        cell: (_h, { row }: { row: CleanTemplateItem }) => (
          <button
            class='count-text'
            type='button'
            onClick={() => handleOpenDetailSlider(row, 'fields')}
          >
            {row.field_count}
          </button>
        ),
      },
      {
        title: t('关联采集项'),
        colKey: 'active_collector_count',
        width: 160,
        sorter: true,
        sortType: 'all',
        cell: (_h, { row }: { row: CleanTemplateItem }) => (
          <button
            class='count-text'
            type='button'
            onClick={() => handleOpenDetailSlider(row, 'collectors')}
          >
            {row.active_collector_count}
          </button>
        ),
      },
      {
        title: t('创建'),
        colKey: 'created_by',
        width: 190,
        filter: getColumnsFilter(createdByFilters.value),
        cell: (_h, { row }: { row: CleanTemplateItem }) => renderOperatorTime(row.created_by, row.created_at),
      },
      {
        title: t('最近更新'),
        colKey: 'updated_by',
        width: 190,
        filter: getColumnsFilter(updatedByFilters.value),
        cell: (_h, { row }: { row: CleanTemplateItem }) => renderOperatorTime(row.updated_by, row.updated_at),
      },
      {
        title: t('操作'),
        colKey: 'operation',
        width: 180,
        cell: (_h, { row }: { row: CleanTemplateItem }) => (
          <div class='template-operations'>
            <bk-button
              theme='primary'
              text
              onClick={() => handleEdit(row)}
            >
              {t('编辑')}
            </bk-button>
            <span
              v-bk-tooltips={{
                content: t('该模板已同步至关联采集项，无需同步'),
                disabled: row.status === 'DRAFT',
              }}
            >
              <bk-button
                disabled={row.status !== 'DRAFT'}
                theme='primary'
                text
                onClick={() => handleOpenSyncSlider(row)}
              >
                {t('一键同步')}
              </bk-button>
            </span>
            <DeleteConfirmPopover
              templateName={row.name}
              on-confirm={() => requestDelete(row)}
            >
              <bk-button
                theme='primary'
                text
              >
                {t('删除')}
              </bk-button>
            </DeleteConfirmPopover>
          </div>
        ),
      },
    ]);

    onMounted(() => {
      // 监听用户信息更新事件
      tenantManager.on('userInfoUpdated', handleUserInfoUpdated);
      calculateTableAreaHeight();
      Promise.all([requestData(), requestOperatorOptions()]);
    });

    onBeforeUnmount(() => {
      tenantManager.off('userInfoUpdated', handleUserInfoUpdated);
    });

    return () => (
      <section
        class='clean-template-page-v2'
        data-test-id='cleanTemplate_section_cleanTemplateBox'
      >
        <main class='clean-template-content'>
          <div
            ref={containerRef}
            class='clean-template-container-v2'
          >
            <div class='template-toolbar'>
              <div class='template-toolbar-actions'>
                <bk-button
                  data-test-id='cleanTemplateBox_button_addNewCleanTemplate'
                  theme='primary'
                  onClick={handleCreate}
                >
                  {t('新建')}
                </bk-button>
                <LogImport
                  disabled={isImporting.value}
                  onChange={handleImport}
                >
                  <bk-button
                    data-test-id='cleanTemplateBox_button_importCleanTemplate'
                    loading={isImporting.value}
                  >
                    {t('导入')}
                  </bk-button>
                </LogImport>
                <bk-button
                  data-test-id='cleanTemplateBox_button_exportCleanTemplate'
                  onClick={() => (exportDialogVisible.value = true)}
                >
                  {t('导出')}
                </bk-button>
              </div>
              <bk-input
                class='template-search'
                data-test-id='cleanTemplateBox_input_cleanTemplateSearch'
                placeholder={t('搜索 模板名称')}
                right-icon='bk-icon icon-search'
                value={params.keyword}
                clearable
                on-right-icon-click={search}
                onChange={handleSearchChange}
                onEnter={search}
              />
            </div>

            <div
              ref={tableContainerRef}
              class='template-table-container'
            >
              <TableComponent
                columns={columns.value}
                data={templateList.value}
                data-test-id='cleanTemplateBox_table_cleanTemplateTable'
                emptyType={emptyType.value}
                filterValue={tableFilterValue.value}
                height={templateList.value.length ? undefined : emptyTableHeight.value}
                loading={isTableLoading.value}
                maxHeight={tableMaxHeight.value}
                pagination={templateList.value.length ? tablePagination.value : undefined}
                rowHeight={64}
                rowKey='clean_template_id'
                sortConfig={sortConfig.value}
                on-empty-click={handleOperation}
                on-filter-change={handleFilterChange}
                on-page-change={handlePageChange}
                on-sort-change={handleSortChange}
              />
            </div>
          </div>
        </main>
        <CleanTemplateSyncSlider
          isShow={syncSliderVisible.value}
          template={activeSyncTemplate.value}
          on-close={handleCloseSyncSlider}
          on-complete={requestData}
        />
        <CleanTemplateDetailSlider
          initialTab={detailInitialTab.value}
          isShow={detailSliderVisible.value}
          template={activeDetailTemplate.value}
          on-close={handleCloseDetailSlider}
          on-delete={(row: CleanTemplateItem) => {
            handleCloseDetailSlider();
            requestDelete(row);
          }}
          on-edit={handleDetailEdit}
          on-sync={handleDetailSync}
        />
        <CleanTemplateExportDialog
          bkBizId={bkBizId.value}
          visible={exportDialogVisible.value}
          on-close={() => (exportDialogVisible.value = false)}
        />
      </section>
    );
  },
});
