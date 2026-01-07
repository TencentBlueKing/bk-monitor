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

import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from 'monitor-common/utils';
import { formatWithTimezone } from 'monitor-common/utils/timezone';
import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';
import { DEFAULT_TIME_RANGE } from 'monitor-pc/components/time-range/utils';
import { isEnFn } from 'monitor-pc/utils';

import {
  ALARM_TEMPLATE_TABLE_FILTER_FIELDS,
  AlarmTemplateDetailTabEnum,
  AlarmTemplateTableFieldToFilterFieldMap,
  AlarmTemplateTypeEnum,
  AlarmTemplateTypeMap,
  DISABLE_TARGET_DOM,
  SCROLL_CONTAINER_DOM,
  TABLE_DEFAULT_DISPLAY_FIELDS,
} from '../../constant';
import AlarmDeleteConfirm, { type AlarmDeleteConfirmEvent } from '../alarm-delete-confirm/alarm-delete-confirm';
import AlarmTemplateConfigDialog, {
  type AlarmTemplateConfigDialogProps,
} from '../alarm-template-config-dialog/alarm-template-config-dialog';
import CollapseTags from '../collapse-tags/collapse-tags';
import DetectionAlgorithmsGroup from '../detection-algorithms-group/detection-algorithms-group';

import type {
  AlarmTemplateConditionParamItem,
  AlarmTemplateDetailTabEnumType,
  AlarmTemplateField,
  AlarmTemplateListItem,
  AlarmTemplateOptionsItem,
  ITableSort,
} from '../../typing';
import type { IPagination } from 'monitor-pc/pages/query-template/typings';

import './alarm-template-table.scss';

interface AlarmTemplateTableEmits {
  /** 批量/单个模板内属性更新事件回调 */
  onBatchUpdate: (
    templateId: AlarmTemplateListItem['id'],
    updateValue: Partial<AlarmTemplateListItem>,
    promiseEvent: AlarmDeleteConfirmEvent
  ) => void;
  /** 清空筛选条件 */
  onClearSearch: () => void;
  /** 克隆事件回调 */
  onCloneTemplate: (templateId: AlarmTemplateListItem['id']) => void;
  /** 表格当前页码变化时的回调 */
  onCurrentPageChange: (currentPage: number) => void;
  /** 删除查询模板事件回调 */
  onDeleteTemplate: (templateId: AlarmTemplateListItem['id'], confirmEvent: AlarmDeleteConfirmEvent) => void;
  /** 下发事件回调 */
  onDispatch: (templateId: AlarmTemplateListItem['id']) => void;
  /** 编辑告警模板事件回调 */
  onEditTemplate: (templateId: AlarmTemplateListItem['id']) => void;
  /** 筛选条件变更事件回调 */
  onFilterChange: (filters: AlarmTemplateConditionParamItem[]) => void;
  /** 表格每页条数变化时的回调 */
  onPageSizeChange: (pageSize: number) => void;
  /** 行勾选事件回调 */
  onSelectedChange: (selectedRowKeys: AlarmTemplateListItem['id'][]) => void;
  /** 打开告警模板详情抽屉页 */
  onShowDetail: (showDetailEvent: {
    id: AlarmTemplateListItem['id'];
    sliderActiveTab: AlarmTemplateDetailTabEnumType;
  }) => void;
  /** 表格排序变化后回调 */
  onSortChange: (sort: `-${string}` | string) => void;
}

interface AlarmTemplateTableProps {
  /** 当前应用名称 */
  appName: string;
  /** 当前页码 */
  current: number;
  /** 空数据类型 */
  emptyType: 'empty' | 'search-empty';
  /** 表格加载状态 */
  loading: boolean;
  /** 每页条数 */
  pageSize: number;
  /** 搜索关键字 */
  searchKeyword: AlarmTemplateConditionParamItem[];
  /** 表格已勾选的数据行id */
  selectedRowKeys: AlarmTemplateListItem['id'][];
  /** 候选值映射表 */
  selectOptionMap: Record<AlarmTemplateField, AlarmTemplateOptionsItem[]>;
  /** 排序 */
  sort: `-${string}` | string;
  /** 表格数据 */
  tableData: AlarmTemplateListItem[];
  /** 总数 */
  total: number;
  switchChangeFn?: (
    id: AlarmTemplateListItem['id'] | AlarmTemplateListItem['id'][],
    updateValue: Partial<AlarmTemplateListItem>
  ) => Promise<unknown>;
}

@Component
export default class AlarmTemplateTable extends tsc<AlarmTemplateTableProps, AlarmTemplateTableEmits> {
  @Ref('deleteConfirmTipRef') deleteConfirmTipRef: InstanceType<typeof AlarmDeleteConfirm>;

  /** 当前应用名称 */
  @Prop({ type: String }) appName: string;
  /** 当前页码 */
  @Prop({ type: Number }) current: number;
  /** 每页条数 */
  @Prop({ type: Number, default: 50 }) pageSize: number;
  /** 总数 */
  @Prop({ type: Number }) total: number;
  /** 表格加载状态 */
  @Prop({ type: Boolean }) loading: boolean;
  /** 表格数据 */
  @Prop({ type: Array, default: () => [] }) tableData: AlarmTemplateListItem[];
  /** 空数据类型 */
  @Prop({ type: String, default: 'empty' }) emptyType: 'empty' | 'search-empty';
  /** 搜索关键字 */
  @Prop({ type: Array, default: () => [] }) searchKeyword!: AlarmTemplateConditionParamItem[];
  /** 表格已勾选的数据行id */
  @Prop({ type: Array, default: () => [] }) selectedRowKeys: AlarmTemplateListItem['id'][];
  /** 候选值映射表 */
  @Prop({ type: Object, default: () => {} }) selectOptionMap: Record<AlarmTemplateField, AlarmTemplateOptionsItem[]>;
  /** 排序 */
  @Prop({ type: String }) sort: `-${string}` | string;
  /** 切换模板状态事件回调 */
  @Prop({ type: Function }) switchChangeFn: (
    id: AlarmTemplateListItem['id'] | AlarmTemplateListItem['id'][],
    updateValue: Partial<AlarmTemplateListItem>
  ) => Promise<unknown>;

  isEn = isEnFn();

  /** 强制刷新表格(主要处理表格表头筛选没有响应式问题) */
  refreshKey = random(8);
  /** dialog 弹窗所需配置项 */
  templateDialogConfig: AlarmTemplateConfigDialogProps = null;
  /** 是否出于请求删除接口中状态 */
  isDeleteActive = false;
  /** 删除二次确认 popover 实例 */
  deletePopoverInstance = null;
  /** 删除二次确认 popover 延迟打开定时器 */
  deletePopoverDelayTimer = null;
  /** 滚动容器Dom实例 */
  scrollContainer: HTMLElement = null;
  /** 滚动结束后回调逻辑执行计时器  */
  scrollTimer = null;
  /** 表格所有列配置 */
  allTableColumns = {
    name: {
      id: 'name',
      label: this.$t('模板名称'),
      minWidth: 220,
      fixed: 'left',
      showOverflowTooltip: false,
      formatter: this.nameColRenderer,
    },
    system: {
      id: 'system',
      label: this.$t('模板类型'),
      minWidth: 110,
      // filters: [],
      filterMultiple: true,
      formatter: (row, column) => row?.[column.columnKey]?.alias || '--',
    },
    update_time: {
      id: 'update_time',
      label: this.$t('最近更新'),
      minWidth: 210,
      showOverflowTooltip: false,
      sortable: true,
      formatter: this.updateTimeColRenderer,
    },
    applied_service_names: {
      id: 'applied_service_names',
      label: this.$t('关联服务'),
      width: 250,
      showOverflowTooltip: false,
      formatter: this.appliedServiceNamesColRenderer,
    },
    algorithms: {
      id: 'algorithms',
      label: this.$t('检测规则'),
      width: 400,
      resizable: false,
      showOverflowTooltip: false,
      formatter: this.algorithmsColRenderer,
    },
    user_group_list: {
      id: 'user_group_list',
      label: this.$t('告警组'),
      width: 258,
      // filters: [],
      filterMultiple: true,
      showOverflowTooltip: false,
      formatter: this.userGroupColRenderer,
    },
    is_enabled: {
      id: 'is_enabled',
      label: this.$t('启用 / 禁用'),
      width: 120,
      // filters: [],
      // filterMultiple: false,
      filterMultiple: true,
      formatter: this.switcherColRenderer,
    },
    is_auto_apply: {
      id: 'is_auto_apply',
      label: this.$t('自动下发'),
      width: 120,
      // filters: [],
      // filterMultiple: false,
      filterMultiple: true,
      formatter: this.switcherColRenderer,
    },
    operator: {
      id: 'operator',
      label: this.$t('操作'),
      width: this.isEn ? 240 : 160,
      resizable: false,
      fixed: 'right',
      formatter: this.operatorColRenderer,
    },
  };

  /** loading状态激活时 表格 和 骨架屏 类名 */
  get tableLoadingActiveClassConfig() {
    return this.loading ? 'table-loading-active' : '';
  }
  /** 表格展示的列配置数组 */
  get tableColumns() {
    return TABLE_DEFAULT_DISPLAY_FIELDS.map(field => {
      const columnItem = { ...this.allTableColumns[field] };
      if (ALARM_TEMPLATE_TABLE_FILTER_FIELDS.has(columnItem.id)) {
        const selectOptionsItem = this.selectOptionMap?.[AlarmTemplateTableFieldToFilterFieldMap?.[field] ?? field];
        const filters =
          selectOptionsItem?.map?.(e => ({
            text: e.name,
            value: typeof e.id === 'boolean' ? `${e.id}` : e.id,
            originValue: e.id,
          })) ||
          columnItem?.filters ||
          [];
        if (filters.length > 1) {
          columnItem.filters = filters;
        } else {
          delete columnItem.filters;
        }
      }
      return columnItem;
    });
  }
  /** 表格排序，将字符串形式转换为 ITableSort 形式  */
  get tableSort(): ITableSort {
    if (!this.sort) {
      return {
        prop: '',
        order: null,
      };
    }
    // 解析排序规则字符串
    const isDescending = this.sort.startsWith('-');
    const sortField = isDescending ? this.sort.slice(1) : this.sort;
    return {
      prop: sortField,
      order: isDescending ? 'descending' : 'ascending',
    };
  }

  /** 表格分页器配置 */
  get pagination(): IPagination {
    return {
      current: this.current,
      limit: this.pageSize,
      count: this.total,
      showTotalCount: true,
    };
  }

  /**
   * @description 行勾选事件回调
   */
  @Emit('selectedChange')
  handleSelectedChange(selectedRow: AlarmTemplateListItem[]) {
    return selectedRow?.map(e => e?.id);
  }
  /**
   * @description 表格列筛选事件回调
   */
  @Emit('filterChange')
  handleFilterChange(filter: Record<string, string[]>) {
    const filters = structuredClone(this.searchKeyword || []);
    const targetItem = Object.entries(filter)[0];
    const targetKey = AlarmTemplateTableFieldToFilterFieldMap?.[targetItem[0]] ?? targetItem[0];
    const targetValue = targetItem[1];
    /**
     * 这里需要对值进行判断,因为这里值的原始值可能是布尔类型
     */
    const columns = this.tableColumns.find(item => item.id === targetKey);
    const value = targetValue.map(item => {
      return columns.filters.find(filter => filter.value === item).originValue;
    });
    const targetIndex = filters.findIndex(e => e.key === targetKey);
    if (targetIndex > -1) {
      if (value?.length === 0) {
        filters.splice(targetIndex, 1);
      } else {
        filters[targetIndex].value = value;
      }
    } else if (value?.length > 0) {
      filters.push({ key: targetKey, value: value });
    }
    return filters;
  }
  /**
   * @description 下发事件回调
   */
  @Emit('dispatch')
  handleDispatch(id: AlarmTemplateListItem['id']) {
    return id;
  }

  /**
   * @description 编辑告警模板事件回调
   */
  @Emit('editTemplate')
  handleEditTemplate(id: AlarmTemplateListItem['id']) {
    return id;
  }

  /**
   * @description 克隆告警模板事件回调
   */
  @Emit('cloneTemplate')
  handleCloneTemplate(id: AlarmTemplateListItem['id']) {
    return id;
  }

  /**
   * @description 打开告警模板详情抽屉页
   */
  @Emit('showDetail')
  handleShowDetail(id: AlarmTemplateListItem['id'], sliderActiveTab: AlarmTemplateDetailTabEnumType) {
    return { id, sliderActiveTab };
  }

  /**
   * @description 删除告警模板事件回调
   */
  @Emit('deleteTemplate')
  handleDeleteTemplate(id: AlarmTemplateListItem['id']) {
    return id;
  }

  /**
   * @description 表格当前页码变化时的回调
   */
  @Emit('currentPageChange')
  handleCurrentPageChange(currentPage: number) {
    return currentPage;
  }

  /**
   * @description 表格每页条数变化时的回调
   */
  @Emit('pageSizeChange')
  handlePageSizeChange(pageSize: number) {
    return pageSize;
  }

  /**
   * @description: 清空筛选条件
   */
  @Emit('clearSearch')
  clearSearch() {
    return;
  }

  /**
   * @description: 表格排序变化后回调
   */
  @Emit('sortChange')
  handleSortChange(sortEvent: ITableSort) {
    if (!sortEvent?.prop) return '';
    return sortEvent.order === 'descending' ? `-${sortEvent.prop}` : sortEvent.prop;
  }

  /**
   * @description 批量/单个模板内属性更新事件回调
   */
  handleBatchUpdate(
    templateId: AlarmTemplateListItem['id'],
    updateValue: Partial<AlarmTemplateListItem>,
    promiseEvent?: AlarmDeleteConfirmEvent
  ) {
    this.$emit('batchUpdate', templateId, updateValue, promiseEvent);
  }

  @Watch('tableData')
  handleDataChange() {
    this.removeScrollListener();
    this.refreshKey = random(8);
    this.$nextTick(() => {
      this.addScrollListener();
    });
  }

  mounted() {
    this.addScrollListener();
  }
  beforeDestroy() {
    this.removeScrollListener();
  }

  /**
   * @description 添加滚动监听
   */
  addScrollListener() {
    this.removeScrollListener();
    this.scrollContainer = this.$el.querySelector(SCROLL_CONTAINER_DOM);
    this.scrollContainer.addEventListener('scroll', this.handleScroll);
  }

  /**
   * @description 移除滚动监听
   */
  removeScrollListener() {
    if (!this.scrollContainer) return;
    this.scrollContainer.removeEventListener('scroll', this.handleScroll);
    this.scrollTimer && clearTimeout(this.scrollTimer);
    this.scrollContainer = null;
  }

  /**
   * @description 处理滚动事件
   */
  handleScroll() {
    this.handleDeletePopoverHide();
    const childrenArr = this.$el.querySelectorAll(DISABLE_TARGET_DOM);
    if (!childrenArr?.length) {
      return;
    }
    const setDomPointerEvents = (val: 'auto' | 'none') => {
      // @ts-expect-error
      for (const children of childrenArr) {
        children.style.pointerEvents = val;
      }
    };
    setDomPointerEvents('none');
    this.scrollTimer && clearTimeout(this.scrollTimer);
    this.scrollTimer = setTimeout(() => {
      setDomPointerEvents('auto');
    }, 600);
  }

  /**
   * @description: 显示 删除二次确认 popover
   * @param {MouseEvent} e
   */
  handleDeletePopoverShow(e: MouseEvent, row: AlarmTemplateListItem) {
    if (this.isDeleteActive) return;
    if (this.deletePopoverInstance || this.deletePopoverDelayTimer) {
      this.handleDeletePopoverHide();
    }
    if (this.deletePopoverInstance?.deleteConfirmConfig?.id === row.id) {
      return;
    }
    const instance = this.$bkPopover(e.currentTarget, {
      content: this.deleteConfirmTipRef.$el,
      trigger: 'click',
      animation: false,
      placement: 'bottom',
      maxWidth: 'none',
      arrow: true,
      boundary: 'window',
      interactive: true,
      theme: 'light padding-0 border-1',
      onHide: () => {
        return !this.isDeleteActive;
      },
      onHidden: () => {
        this.handleDeletePopoverHide();
      },
    });
    // @ts-expect-error
    instance.deleteConfirmConfig = {
      id: row.id,
      templateName: row.name,
    };
    this.deletePopoverInstance = instance;
    const popoverCache = this.deletePopoverInstance;
    this.deletePopoverDelayTimer = setTimeout(() => {
      if (popoverCache === this.deletePopoverInstance) {
        this.deletePopoverInstance?.show?.(0);
      } else {
        popoverCache?.hide?.(0);
        popoverCache?.destroy?.();
      }
    }, 300);
  }

  /**
   * @description: 清除popover
   */
  handleDeletePopoverHide() {
    if (this.isDeleteActive) return;
    this.handleClearTimer();
    this.deletePopoverInstance?.hide?.(0);
    this.deletePopoverInstance?.destroy?.();
    this.deletePopoverInstance = null;
  }
  /**
   * @description: 清除popover延时打开定时器
   *
   */
  handleClearTimer() {
    this.deletePopoverDelayTimer && clearTimeout(this.deletePopoverDelayTimer);
    this.deletePopoverDelayTimer = null;
  }

  /**
   * @description: 删除模板确认回调
   */
  handleDeleteTemplateConfirm(templateId: AlarmTemplateListItem['id'], confirmEvent: AlarmDeleteConfirmEvent) {
    this.isDeleteActive = true;
    confirmEvent?.promiseEvent
      ?.then(() => {
        this.isDeleteActive = false;
        this.handleDeletePopoverHide();
      })
      .catch(() => {
        this.isDeleteActive = false;
      });
    this.$emit('deleteTemplate', templateId, confirmEvent);
  }

  /**
   * @description: switcher 状态改变回调(启用/停止 & 自动下发)
   */
  handleSwitcherChange(row: AlarmTemplateListItem, value: boolean, columnKey: 'is_auto_apply' | 'is_enabled') {
    const subTitleTextMap = {
      is_auto_apply: {
        true: this.$t('开启「自动下发」功能后，新增服务将自动配置该策略并生效'),
        false: this.$t('关闭「自动下发」功能，新增服务将不会自动配置该策略'),
      },
      is_enabled: {
        true: this.$t('开启后，该策略模板可以下发到需要的服务'),
        false: this.$t('禁用后，该策略模板不可被下发到服务'),
      },
    };
    return new Promise((resolve, reject) => {
      const h = this.$createElement;
      this.$bkInfo({
        title: value ? this.$t('是否开启该功能?') : this.$t('是否关闭该功能?'),
        okText: this.$t('确定'),
        cancelText: this.$t('取消'),
        width: 480,
        extCls: 'alarm-template-container-table-switcher-info',
        confirmLoading: true,
        subHeader: h(
          'div',
          {
            style: {
              display: 'flex',
              'flex-direction': 'column',
              'align-items': 'flex-start',
            },
          },
          [
            h(
              'div',
              {
                style: {
                  color: '#313238',
                  'font-size': '14px',
                  'line-height': '22px',
                  'margin-bottom': '16px',
                  'word-break': 'break-word',
                },
              },
              `${this.$t('模板')}: ${row?.name}`
            ),
            h(
              'div',
              {
                style: {
                  'min-height': '46px',
                  background: '#F5F7FA',
                  display: 'flex',
                  'font-size': '14px',
                  alignItems: 'center',
                  color: '#4D4F56',
                  'line-height': '22px',
                  'justify-content': 'flex-start',
                  'border-radius': '2px',
                  width: '100%',
                  padding: '12px 16px',
                  'word-break': 'break-word',
                },
              },
              `${value ? subTitleTextMap[columnKey].true : subTitleTextMap[columnKey].false}`
            ),
          ]
        ),
        closeFn: () => {
          reject('close');
          return true;
        },
        cancelFn: () => {
          reject('cancel');
          return true;
        },
        confirmFn: async () => {
          const success = await this.switchChangeFn?.(row.id, { [columnKey]: value }).catch(() => {
            return false;
          });
          if (success) {
            resolve(true);
          } else {
            reject('error');
          }
          return !!success;
        },
      });
    });
  }

  /**
   * @description : 打开/关闭 dialog 弹窗
   */
  handleDialogConfigChange(dialogConfig: AlarmTemplateConfigDialogProps) {
    this.templateDialogConfig = dialogConfig;
  }

  /**
   * @description: 跳转服务详情页
   * @param serviceName 服务名
   */
  handleGoService(serviceName: string) {
    const { from, to } = this.$route.query;
    let urlStr = `${window.__BK_WEWEB_DATA__?.parentRoute || ''}service/?filter-service_name=${serviceName}&filter-app_name=${this.appName}`;
    urlStr += `&from=${from || DEFAULT_TIME_RANGE[0]}&to=${to || DEFAULT_TIME_RANGE[1]}`;
    const { href } = this.$router.resolve({
      path: urlStr,
    });
    const url = location.href.replace(location.pathname, '/').replace(location.hash, '') + href;
    window.open(url);
  }

  /**
   * @description: 当删除按钮不可操作时，获取删除提示文案
   */
  getDeleteTip(row: AlarmTemplateListItem) {
    if (row?.type === AlarmTemplateTypeEnum.INNER) {
      return this.$t('内置策略不可删除') as string;
    }
    if (row?.applied_service_names?.length > 0) {
      return this.$t('该模板已下发服务，不可删除') as string;
    }
    return '';
  }

  /**
   * @description: 表格 模板名称 列渲染
   */
  nameColRenderer(row: AlarmTemplateListItem) {
    return (
      <div class='name-col'>
        <div class='type-icon'>
          <i
            class={['icon-monitor', AlarmTemplateTypeMap[row?.type || AlarmTemplateTypeEnum.INNER].icon]}
            v-bk-tooltips={{ content: AlarmTemplateTypeMap[row?.type || AlarmTemplateTypeEnum.INNER].name }}
          />
        </div>
        <div
          class='name-text'
          v-bk-overflow-tips
          onClick={() => this.handleShowDetail(row.id, AlarmTemplateDetailTabEnum.BASE_INFO)}
        >
          <span>{row?.name}</span>
        </div>
        {row?.alert_number ? (
          <div
            class='alarm-tag'
            v-bk-tooltips={{ content: this.$t('查看各服务告警情况') }}
            onClick={() => this.handleShowDetail(row.id, AlarmTemplateDetailTabEnum.RELATE_SERVICE_ALARM)}
          >
            <i class='icon-monitor icon-gaojing3' />
            <span class='alarm-count'>{row?.alert_number}</span>
          </div>
        ) : null}
      </div>
    );
  }

  /**
   * @description: 表格 最近更新 列渲染
   */
  updateTimeColRenderer(row: AlarmTemplateListItem) {
    return (
      <div class='update-time-col'>
        <div
          class='update-user'
          v-bk-overflow-tips
        >
          <bk-user-display-name user-id={row?.update_user} />
        </div>
        <div
          class='update-time'
          v-bk-overflow-tips
        >
          <span>{formatWithTimezone(row?.update_time) || '--'}</span>
        </div>
      </div>
    );
  }

  /**
   * @description: 表格 关联服务 列渲染
   */
  appliedServiceNamesColRenderer(row: AlarmTemplateListItem) {
    if (!row?.applied_service_names?.length) return '--';
    const firstServiceName = row?.applied_service_names?.[0];
    return (
      <div class='applied-service-name-col'>
        <div
          class='first-service-name'
          v-bk-overflow-tips
          onClick={() => this.handleShowDetail(row.id, AlarmTemplateDetailTabEnum.RELATE_SERVICE_ALARM)}
        >
          <span>{firstServiceName || '--'}</span>
        </div>
        {row?.applied_service_names?.length > 1 && (
          <div
            class='service-name-ellipsis-tag'
            v-bk-tooltips={{ content: this.$t('查看全部关联服务') }}
            onClick={() => this.handleShowDetail(row.id, AlarmTemplateDetailTabEnum.RELATE_SERVICE_ALARM)}
          >
            <span class='ellipsis-count'>{`+ ${row?.applied_service_names?.length - 1}`}</span>
          </div>
        )}
      </div>
    );
  }
  /**
   * @description: 表格 检测规则 列渲染
   */
  algorithmsColRenderer(row: AlarmTemplateListItem, column) {
    const columnKey = column.columnKey;
    const value = row[columnKey];
    return (
      <div class='algorithms-col'>
        <DetectionAlgorithmsGroup
          algorithms={value}
          connector={row.detect?.connector}
        />
        <div
          class='edit-btn'
          onClick={() =>
            this.handleDialogConfigChange({ templateId: row.id, activeType: columnKey, defaultValue: value, row })
          }
        >
          <i class='icon-monitor icon-bianji' />
        </div>
      </div>
    );
  } /**
   * @description: 表格 用户组 列渲染
   */
  userGroupColRenderer(row: AlarmTemplateListItem, column) {
    const columnKey = column.columnKey;
    const value = row[columnKey] || [];
    return (
      <div class='user-group-list-col'>
        <CollapseTags
          scopedSlots={{
            after: () => (
              <div
                class='edit-btn'
                onClick={() =>
                  this.handleDialogConfigChange({ templateId: row.id, activeType: columnKey, defaultValue: value, row })
                }
              >
                <i class='icon-monitor icon-bianji' />
              </div>
            ),
            customTag: (tag, index) => (
              <bk-tag
                key={index}
                class='user-group-item'
                v-bk-overflow-tips
              >
                {tag}
              </bk-tag>
            ),
          }}
          data={value?.map(e => e.name) || []}
        />
      </div>
    );
  }

  /**
   * @description 表格 switcher 按钮列渲染（启用/停止 & 自动下发）
   */
  switcherColRenderer(row: AlarmTemplateListItem, column) {
    const columnKey = column.columnKey;
    const value = row?.[columnKey];
    const switcherDisabled = columnKey === 'is_auto_apply' && !row?.is_enabled;
    return (
      <div class={['switcher-col', `${columnKey}-col`]}>
        <bk-switcher
          v-bk-tooltips={{ content: this.$t('该模板已禁用，无法下发'), disabled: !switcherDisabled }}
          disabled={switcherDisabled}
          pre-check={lastValue => this.handleSwitcherChange(row, lastValue, columnKey)}
          size='small'
          theme='primary'
          value={value}
        />
      </div>
    );
  }

  /**
   * @description: 表格 操作 列渲染
   */
  operatorColRenderer(row: AlarmTemplateListItem) {
    // 1. 内置策略不可删除
    // 2. 克隆策略，已下发，不可以删除
    const deleteDisabledTip = this.getDeleteTip(row);
    return (
      <div class='operator-col'>
        <span v-bk-tooltips={{ content: this.$t('该模板已禁用，无法下发'), disabled: row?.is_enabled }}>
          <bk-button
            disabled={!row?.is_enabled}
            text={true}
            onClick={() => this.handleDispatch(row.id)}
          >
            {this.$t('下发')}
          </bk-button>
        </span>
        <bk-button
          text={true}
          onClick={() => this.handleEditTemplate(row.id)}
        >
          {this.$t('编辑')}
        </bk-button>
        <bk-button
          text={true}
          onClick={() => this.handleCloneTemplate(row.id)}
        >
          {this.$t('克隆')}
        </bk-button>
        <bk-popover
          tippy-options={{
            theme: 'light padding-0 apm-alarm-template-popover',
            arrow: false,
            distance: 6,
            onHide: () => this.deletePopoverInstance?.deleteConfirmConfig?.id !== row?.id,
            // onHidden: () => this.handleAllPopoverHide(),
            // onShown: instance => {
            //   this.moreOperationPopoverInstance = instance;
            // },
          }}
          placement='bottom-end'
        >
          <i class='more-btn icon-monitor icon-gengduo1' />
          <div slot='content'>
            <ul class='more-btn-list'>
              <li
                class={[
                  'more-btn-item delete-btn',
                  { 'is-active': this.deletePopoverInstance?.deleteConfirmConfig?.id === row?.id },
                  {
                    'is-disabled': deleteDisabledTip,
                  },
                ]}
                v-bk-tooltips={{ content: deleteDisabledTip, disabled: !deleteDisabledTip }}
              >
                <div onClick={e => !deleteDisabledTip && this.handleDeletePopoverShow(e, row)}>{this.$t('删除')}</div>
              </li>
            </ul>
          </div>
        </bk-popover>
      </div>
    );
  }

  defaultRenderer(row: AlarmTemplateListItem, column) {
    return row[column.columnKey] || '--';
  }

  transformColumn(column) {
    let filteredValue = null;
    if (ALARM_TEMPLATE_TABLE_FILTER_FIELDS.has(column.id)) {
      const filterField = AlarmTemplateTableFieldToFilterFieldMap?.[column.id] ?? column.id;
      const value = this.searchKeyword.find(item => item.key === filterField)?.value || [];
      /** table组件对于布尔值的筛选功能会出现bug，需要处理成其他类型 */
      filteredValue = value.map(item => (typeof item === 'boolean' ? `${item}` : item));
    }
    return (
      <bk-table-column
        key={`column_${column.id}`}
        width={column.width}
        align={column.align}
        column-key={column.id}
        filter-multiple={column.filterMultiple}
        filtered-value={filteredValue}
        filters={column.filters}
        fixed={column.fixed}
        formatter={column.formatter || this.defaultRenderer}
        label={column.label}
        min-width={column.minWidth}
        prop={column.id}
        render-header={column?.renderHeader ? () => column.renderHeader(column) : undefined}
        resizable={column.resizable ?? true}
        show-overflow-tooltip={column.showOverflowTooltip ?? true}
        sortable={column?.sortable && 'custom'}
      />
    );
  }
  render() {
    return (
      <div class={`alarm-template-container ${!this.selectedRowKeys?.length ? 'not-selected' : 'has-selected'} `}>
        <bk-table
          key={this.refreshKey}
          height='100%'
          class={`alarm-template-table ${this.tableLoadingActiveClassConfig}`}
          auto-scroll-to-top={true}
          border={false}
          data={this.tableData}
          default-sort={this.tableSort}
          outer-border={false}
          pagination={this.pagination}
          on-filter-change={this.handleFilterChange}
          on-page-change={this.handleCurrentPageChange}
          on-page-limit-change={this.handlePageSizeChange}
          on-selection-change={this.handleSelectedChange}
          on-sort-change={this.handleSortChange}
        >
          <bk-table-column
            selectable={row => row?.is_enabled}
            type='selection'
          />
          {this.tableColumns.map(column => this.transformColumn(column))}
          <EmptyStatus
            slot='empty'
            textMap={{
              empty: this.$t('暂无数据'),
            }}
            type={this.emptyType}
            onOperation={this.clearSearch}
          />
        </bk-table>
        <TableSkeleton
          class={`alarm-template-table-skeleton ${this.tableLoadingActiveClassConfig}`}
          type={2}
        />
        <div style='display: none'>
          <AlarmDeleteConfirm
            ref='deleteConfirmTipRef'
            templateId={this.deletePopoverInstance?.deleteConfirmConfig?.id}
            templateName={this.deletePopoverInstance?.deleteConfirmConfig?.templateName}
            onCancel={this.handleDeletePopoverHide}
            onConfirm={this.handleDeleteTemplateConfirm}
          />
          <AlarmTemplateConfigDialog
            activeType={this.templateDialogConfig?.activeType}
            defaultValue={this.templateDialogConfig?.defaultValue}
            row={this.templateDialogConfig?.row}
            templateId={this.templateDialogConfig?.templateId}
            onCancel={() => this.handleDialogConfigChange(null)}
            onConfirm={this.handleBatchUpdate}
          />
        </div>
      </div>
    );
  }
}
