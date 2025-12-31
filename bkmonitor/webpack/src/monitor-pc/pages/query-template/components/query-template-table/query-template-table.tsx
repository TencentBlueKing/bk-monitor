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

import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { formatWithTimezone } from 'monitor-common/utils/timezone';
import loadingIcon from 'monitor-ui/chart-plugins/icons/spinner.svg';

import EmptyStatus from '../../../../components/empty-status/empty-status';
import TableSkeleton from '../../../../components/skeleton/table-skeleton';
import { TABLE_DEFAULT_DISPLAY_FIELDS, TABLE_FIXED_DISPLAY_FIELDS, TemplateDetailTabEnum } from '../../constants';
import TemplateDetail from '../../detail/template-detail';
import DeleteConfirm, { type DeleteConfirmEvent } from './components/delete-confirm';

import type {
  IPagination,
  ITableSettingChangeEvent,
  ITableSettingSize,
  ITableSort,
  QueryTemplateListItem,
} from '../../typings';
import type { TemplateDetailTabEnumType } from '../../typings/constants';

import './query-template-table.scss';

interface QueryTemplateTableEmits {
  /** 清空筛选条件 */
  onClearSearch: () => void;
  /** 表格当前页码变化时的回调 */
  onCurrentPageChange: (currentPage: number) => void;
  /** 删除查询模板事件回调 */
  onDeleteTemplate: (templateId: string, confirmEvent: DeleteConfirmEvent) => void;
  /** 将url中自动显示详情侧弹抽屉的参数配置清除 */
  onDisabledAutoShowSlider: () => void;
  /** 表格每页条数变化时的回调 */
  onPageSizeChange: (pageSize: number) => void;
  /** 表格排序变化后回调 */
  onSortChange: (sort: `-${string}` | string) => void;
}

interface QueryTemplateTableProps {
  /** 页码 */
  current: number;
  /** 空数据类型 */
  emptyType: 'empty' | 'search-empty';
  /** 表格加载状态 */
  loading: boolean;
  /** 每页条数 */
  pageSize: number;
  /** 排序 */
  sort: `-${string}` | string;
  /** 表格数据 */
  tableData: QueryTemplateListItem[];
  /** 总数 */
  total: number;
}

@Component
export default class QueryTemplateTable extends tsc<QueryTemplateTableProps, QueryTemplateTableEmits> {
  @Ref('tableRef') tableRef: Record<string, any>;
  @Ref('deleteConfirmTipRef') deleteConfirmTipRef: InstanceType<typeof DeleteConfirm>;

  /** 页码 */
  @Prop({ type: Number }) current: number;
  /** 表格加载状态 */
  @Prop({ type: Boolean }) loading: boolean;
  /** 每页条数 */
  @Prop({ type: Number, default: 50 }) pageSize: number;
  /** 排序 */
  @Prop({ type: String }) sort: `-${string}` | string;
  /** 表格数据 */
  @Prop({ type: Array, default: () => [] }) tableData: QueryTemplateListItem[];
  /** 总数 */
  @Prop({ type: Number }) total: number;
  /** 空数据类型 */
  @Prop({ type: String, default: 'empty' }) emptyType: 'empty' | 'search-empty';

  /** 模板详情 - 侧弹抽屉显示状态 */
  sliderShow = false;
  /** 模板详情 - 侧弹抽屉显示时默认激活的 tab 面板 */
  sliderActiveTab: TemplateDetailTabEnumType = null;
  /** 模板详情 - 当前需要显示详情信息的数据 id */
  sliderActiveId: QueryTemplateListItem['id'] = '';
  /** 是否出于请求删除接口中状态 */
  isDeleteActive = false;
  /** 删除二次确认 popover 实例 */
  deletePopoverInstance = null;
  /** 删除二次确认 popover 延迟打开定时器 */
  deletePopoverDelayTimer = null;
  /** 表格展示的列id数据 */
  displayFields = TABLE_DEFAULT_DISPLAY_FIELDS;
  /** 表格尺寸 */
  tableSize: ITableSettingSize = 'small';
  /** 表格所有列配置 */
  allTableColumns = {
    name: {
      id: 'name',
      label: this.$t('模板名称'),
      minWidth: 180,
      fixed: 'left',
      formatter: this.clickShowSlicerColRenderer,
    },
    alias: {
      id: 'alias',
      label: this.$t('模板别名'),
      minWidth: 180,
    },
    description: {
      id: 'description',
      label: this.$t('模板说明'),
      minWidth: 220,
    },
    create_user: {
      id: 'create_user',
      label: this.$t('创建人'),
      width: 100,
      formatter: this.userColRenderer,
    },
    create_time: {
      id: 'create_time',
      label: this.$t('创建时间'),
      sortable: true,
      width: 180,
      formatter: this.timeColRenderer,
    },
    update_user: {
      id: 'update_user',
      label: this.$t('更新人'),
      width: 100,
      formatter: this.userColRenderer,
    },
    update_time: {
      id: 'update_time',
      label: this.$t('更新时间'),
      sortable: true,
      width: 180,
      formatter: this.timeColRenderer,
    },
    relation_config_count: {
      id: 'relation_config_count',
      label: this.$t('消费场景'),
      align: 'right',
      width: 120,
      formatter: this.relationCountColRenderer,
    },
    operator: {
      id: 'operator',
      label: this.$t('操作'),
      width: 100,
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
    return this.displayFields.map(field => this.allTableColumns[field]);
  }
  /** 表格setting的可配置 显示/隐藏 的列配置 */
  get tableSettingFields() {
    return Object.values(this.allTableColumns).map(column => ({
      id: column.id,
      label: column.label,
      disabled: TABLE_FIXED_DISPLAY_FIELDS.includes(column.id),
    }));
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
   * @description: 表格排序变化后回调
   */
  @Emit('sortChange')
  handleSortChange(sortEvent: ITableSort) {
    if (!sortEvent?.prop) return '';
    return sortEvent.order === 'descending' ? `-${sortEvent.prop}` : sortEvent.prop;
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
   * @description 将url中自动显示详情侧弹抽屉的参数配置清除
   */
  @Emit('disabledAutoShowSlider')
  handleDisabledAutoShowSlider() {
    return;
  }
  /**
   * @description: 清空筛选条件
   */
  @Emit('clearSearch')
  clearSearch() {
    return;
  }

  mounted() {
    this.tableRef?.$el.addEventListener('wheel', this.handlePopoverHide);
    this.handleAutoShowSliderForMounted();
  }
  beforeDestroy() {
    this.tableRef?.$el.removeEventListener('wheel', this.handlePopoverHide);
  }

  /**
   * @description: 挂载时期校验url是否需要显示侧弹抽屉
   */
  handleAutoShowSliderForMounted() {
    const { sliderShow, sliderActiveId } = this.$route.query;
    if (!sliderShow || !sliderActiveId) return;
    this.sliderActiveTab = TemplateDetailTabEnum.CONFIG;
    this.sliderActiveId = sliderActiveId as string;
    this.sliderShow = Boolean(sliderShow);
  }

  /**
   * @description: 显示 删除二次确认 popover
   * @param {MouseEvent} e
   */
  handleDeletePopoverShow(e: MouseEvent, row) {
    if (this.isDeleteActive) return;
    if (this.deletePopoverInstance || this.deletePopoverDelayTimer) {
      this.handlePopoverHide();
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
        this.handlePopoverHide();
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
  handlePopoverHide() {
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
  handleDeleteTemplateConfirm(templateId: QueryTemplateListItem['id'], confirmEvent: DeleteConfirmEvent) {
    this.isDeleteActive = true;
    confirmEvent?.confirmPromise
      ?.then(() => {
        this.isDeleteActive = false;
        this.handlePopoverHide();
      })
      .catch(() => {
        this.isDeleteActive = false;
      });
    this.$emit('deleteTemplate', templateId, confirmEvent);
  }

  /**
   * @description: 表格setting配置确认后回调
   * @param settingEvent 表格设置变更事件对象
   */
  handleSettingChange(settingEvent: ITableSettingChangeEvent) {
    this.displayFields = settingEvent.fields?.map(item => item.id);
    this.tableSize = settingEvent.size;
  }

  /**
   * @description: 打开/关闭 侧弹详情抽屉面板
   */
  handleSliderShowChange(
    isShow: boolean,
    showEvent?: {
      columnKey?: string;
      id: string;
    }
  ) {
    const { sliderShow, sliderActiveId } = this.$route.query;
    let sliderTab = null;
    if (isShow) {
      sliderTab = showEvent?.columnKey === 'name' ? TemplateDetailTabEnum.CONFIG : TemplateDetailTabEnum.CONSUME;
    } else if (sliderShow && sliderActiveId) {
      this.handleDisabledAutoShowSlider();
    }
    this.sliderActiveTab = sliderTab;
    this.sliderActiveId = showEvent?.id;
    this.sliderShow = isShow;
  }

  /**
   * @description 跳转至 编辑查询模板 页面
   */
  jumpToEditPage(id: string) {
    this.$router.push({
      name: 'query-template-edit',
      params: {
        id,
      },
    });
  }

  /**
   * @description: 当删除按钮不可操作时，获取删除提示文案
   */
  getDeleteTip(row) {
    if (row?.relation_config_count > 0) {
      return this.$t('当前仍然有关联的消费场景，无法删除') as string;
    }
    if (row?.bk_biz_id === 0) {
      return this.$t('全局模板无法删除') as string;
    }
    if (row?.bk_biz_id !== this.$store.getters.bizId) {
      const bizId = row?.bk_biz_id;
      const bizName = this.$store.getters.bizIdMap.get(bizId)?.name;
      const url = `${location.origin}${location.pathname}?bizId=${bizId}${location.hash}`;
      return (
        <i18n
          class='text'
          path='模板属于业务 {0}，无法删除'
        >
          <a
            style='color: #3a84ff'
            href={url}
            rel='noreferrer'
            target='_blank'
          >
            {bizName}
          </a>
        </i18n>
      );
    }
    return this.$t('无法删除');
  }

  /**
   * @description: 当编辑按钮不可操作时，获取编辑提示文案
   */
  getEditTip(row) {
    if (row?.bk_biz_id === 0) {
      return this.$t('全局模板无法编辑') as string;
    }
    if (row?.bk_biz_id !== this.$store.getters.bizId) {
      const bizId = row?.bk_biz_id;
      const bizName = this.$store.getters.bizIdMap.get(bizId)?.name;
      const url = `${location.origin}${location.pathname}?bizId=${bizId}${location.hash}`;

      return (
        <i18n
          class='text'
          path='模板属于业务 {0}，无法编辑'
        >
          <a
            style='color: #3a84ff'
            href={url}
            rel='noreferrer'
            target='_blank'
          >
            {bizName}
          </a>
        </i18n>
      );
    }
    return this.$t('无法编辑');
  }

  /**
   * @description: 消费场景 列渲染
   * 由于消费场景列是异步请求，所以需要使用增加 loading 状态交互过渡
   */
  relationCountColRenderer(row, column) {
    if (row.relation_config_count == null) {
      return (
        <div class='relation-count-col'>
          <img
            class='loading-svg'
            alt=''
            src={loadingIcon}
          />
        </div>
      );
    }

    if (!row.relation_config_count) {
      return row.relation_config_count;
    }
    return this.clickShowSlicerColRenderer(row, column);
  }

  /**
   * @description: 表格 点击打开侧弹详情抽屉面板 列渲染
   */
  clickShowSlicerColRenderer(row, column) {
    const columnKey = column.columnKey;
    const showSliderOption = {
      columnKey: columnKey,
      id: row.id,
    };
    let alias = row?.[columnKey];
    if (columnKey === 'relation_config_count') {
      alias ||= 0;
    }
    return (
      <span
        class={'click-show-slicer-col'}
        onClick={() => this.handleSliderShowChange(true, showSliderOption)}
      >
        {alias}
      </span>
    );
  }

  /**
   * @description 用户名 列渲染（兼容多租户）
   */
  userColRenderer(row, column) {
    const colKey = column.columnKey;
    return <bk-user-display-name user-id={row[colKey]} />;
  }
  timeColRenderer(row, column) {
    return <span>{formatWithTimezone(row[column.columnKey])}</span>;
  }
  /**
   * @description: 表格 操作 列渲染
   */
  operatorColRenderer(row) {
    const canDelete = row?.can_delete && row?.relation_config_count === 0;

    return (
      <div class='operator-col'>
        <bk-popover
          disabled={row?.can_edit}
          placement='right'
        >
          <bk-button
            disabled={!row?.can_edit}
            text={true}
            onClick={() => this.jumpToEditPage(row.id)}
          >
            {this.$t('编辑')}
          </bk-button>
          <span slot='content'>{this.getEditTip(row)}</span>
        </bk-popover>
        <bk-popover
          disabled={canDelete}
          placement='right'
        >
          <bk-button
            disabled={!canDelete}
            text={true}
            onClick={(e: MouseEvent) => this.handleDeletePopoverShow(e, row)}
          >
            {this.$t('删除')}
          </bk-button>
          <span slot='content'>{this.getDeleteTip(row)}</span>
        </bk-popover>
      </div>
    );
  }

  defaultRenderer(row, column) {
    return row[column.columnKey] || '--';
  }

  transformColumn(column) {
    return (
      <bk-table-column
        key={`column_${column.id}`}
        width={column.width}
        align={column.align}
        class-name={`${column.align ?? 'left'}-align-cell`}
        column-key={column.id}
        fixed={column.fixed}
        formatter={column.formatter || this.defaultRenderer}
        label={column.label}
        min-width={column.minWidth}
        prop={column.id}
        render-header={column?.renderHeader ? () => column.renderHeader(column) : undefined}
        resizable={column.resizable ?? true}
        show-overflow-tooltip={true}
        sortable={column?.sortable && 'custom'}
      />
    );
  }

  render() {
    return (
      <div class='query-template-container'>
        <bk-table
          ref='tableRef'
          height='100%'
          class={`query-template-table ${this.tableLoadingActiveClassConfig}`}
          auto-scroll-to-top={true}
          border={false}
          data={this.tableData}
          default-sort={this.tableSort}
          outer-border={false}
          pagination={this.pagination}
          size={this.tableSize}
          on-page-change={this.handleCurrentPageChange}
          on-page-limit-change={this.handlePageSizeChange}
          on-sort-change={this.handleSortChange}
        >
          {this.tableColumns.map(column => this.transformColumn(column))}
          <bk-table-column type='setting'>
            <bk-table-setting-content
              fields={this.tableSettingFields}
              selected={this.tableColumns}
              size={this.tableSize}
              on-setting-change={this.handleSettingChange}
            />
          </bk-table-column>
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
          class={`query-template-table-skeleton ${this.tableLoadingActiveClassConfig}`}
          type={2}
        />
        <div style='display: none'>
          <DeleteConfirm
            ref='deleteConfirmTipRef'
            templateId={this.deletePopoverInstance?.deleteConfirmConfig?.id}
            templateName={this.deletePopoverInstance?.deleteConfirmConfig?.templateName}
            onCancel={this.handlePopoverHide}
            onConfirm={this.handleDeleteTemplateConfirm}
          />
          <TemplateDetail
            defaultActiveTab={this.sliderActiveTab}
            sliderShow={this.sliderShow}
            templateId={this.sliderActiveId}
            onDeleteTemplate={(templateId, confirmEvent) => this.$emit('deleteTemplate', templateId, confirmEvent)}
            onEdit={this.jumpToEditPage}
            onSliderShowChange={this.handleSliderShowChange}
          />
        </div>
      </div>
    );
  }
}
