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

import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';
import TableSkeleton from 'monitor-pc/components/skeleton/table-skeleton';

import { AlarmTemplateTypeEnum, AlarmTemplateTypeMap, TABLE_DEFAULT_DISPLAY_FIELDS } from '../../constant';
import AlarmDeleteConfirm, { type AlarmDeleteConfirmEvent } from '../alarm-delete-confirm/alarm-delete-confirm';
import DetectionAlgorithmsGroup from '../detection-algorithms-group/detection-algorithms-group';

import type { AlarmTemplateListItem } from '../../typing';

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
  /** 删除查询模板事件回调 */
  onDeleteTemplate: (templateId: AlarmTemplateListItem['id'], confirmEvent: AlarmDeleteConfirmEvent) => void;
  /** 下发事件回调 */
  onDispatch: (templateId: AlarmTemplateListItem['id']) => void;
  /** 编辑告警模板事件回调 */
  onEditTemplate: (templateId: AlarmTemplateListItem['id']) => void;
}

interface AlarmTemplateTableProps {
  /** 空数据类型 */
  emptyType: 'empty' | 'search-empty';
  /** 表格加载状态 */
  loading: boolean;
  /** 表格数据 */
  tableData: AlarmTemplateListItem[];
}

@Component
export default class AlarmTemplateTable extends tsc<AlarmTemplateTableProps, AlarmTemplateTableEmits> {
  @Ref('tableRef') tableRef: Record<string, any>;
  @Ref('deleteConfirmTipRef') deleteConfirmTipRef: InstanceType<typeof AlarmDeleteConfirm>;

  /** 表格加载状态 */
  @Prop({ type: Boolean }) loading: boolean;
  /** 表格数据 */
  @Prop({ type: Array, default: () => [] }) tableData: AlarmTemplateListItem[];
  /** 空数据类型 */
  @Prop({ type: String, default: 'empty' }) emptyType: 'empty' | 'search-empty';

  /** 是否出于请求删除接口中状态 */
  isDeleteActive = false;
  /** 删除二次确认 popover 实例 */
  deletePopoverInstance = null;
  /** 删除二次确认 popover 延迟打开定时器 */
  deletePopoverDelayTimer = null;
  /** 表格所有列配置 */
  allTableColumns = {
    name: {
      id: 'name',
      label: this.$t('模板名称'),
      minWidth: 180,
      fixed: 'left',
      showOverflowTooltip: false,
      formatter: this.nameColRenderer,
    },
    category: {
      id: 'category',
      label: this.$t('模板类型'),
      minWidth: 110,
    },
    update_time: {
      id: 'update_time',
      label: this.$t('最近更新'),
      minWidth: 210,
      showOverflowTooltip: false,
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
      width: 220,
      resizable: false,
      showOverflowTooltip: false,
      formatter: this.algorithmsColRenderer,
    },
    user_group_list: {
      id: 'user_group_list',
      label: this.$t('告警组'),
      width: 100,
      // formatter: this.userColRenderer,
    },
    is_enabled: {
      id: 'is_enabled',
      label: this.$t('启用 / 禁用'),
      width: 120,
      formatter: this.switcherColRenderer,
    },
    is_auto_apply: {
      id: 'is_auto_apply',
      label: this.$t('自动下发'),
      width: 120,
      formatter: this.switcherColRenderer,
    },
    operator: {
      id: 'operator',
      label: this.$t('操作'),
      width: 160,
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
    return TABLE_DEFAULT_DISPLAY_FIELDS.map(field => this.allTableColumns[field]);
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
   * @description 删除告警模板事件回调
   */
  @Emit('deleteTemplate')
  handleDeleteTemplate(id: AlarmTemplateListItem['id']) {
    return id;
  }

  /**
   * @description: 清空筛选条件
   */
  @Emit('clearSearch')
  clearSearch() {
    return;
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

  mounted() {
    this.tableRef?.$el.addEventListener('wheel', this.handlePopoverHide);
  }
  beforeDestroy() {
    this.tableRef?.$el.removeEventListener('wheel', this.handlePopoverHide);
  }

  /**
   * @description: 显示 删除二次确认 popover
   * @param {MouseEvent} e
   */
  handleDeletePopoverShow(e: MouseEvent, row: AlarmTemplateListItem) {
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
    // @ts-ignore
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
  handleDeleteTemplateConfirm(templateId: AlarmTemplateListItem['id'], confirmEvent: AlarmDeleteConfirmEvent) {
    this.isDeleteActive = true;
    confirmEvent?.promiseEvent
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
   * @description: switcher 状态改变回调(启用/停止 & 自动下发)
   */
  handleSwitcherChange(
    templateId: AlarmTemplateListItem['id'],
    value: boolean,
    columnKey: 'is_auto_apply' | 'is_enabled'
  ) {
    let successCallback = null;
    let errorCallback = null;
    const promiseEvent = new Promise((res, rej) => {
      successCallback = res;
      errorCallback = rej;
    })
      .then(() => {
        this.loading = false;
      })
      .catch(() => {
        this.loading = false;
      });
    this.handleBatchUpdate(templateId, { [columnKey]: value }, { promiseEvent, successCallback, errorCallback });
    return promiseEvent;
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
        >
          <span>{row?.name}</span>
        </div>
        <div
          class='alarm-tag'
          v-bk-tooltips={{ content: this.$t('查看各服务告警情况') }}
        >
          <i class='icon-monitor icon-gaojing3' />
          <span class='alarm-count'>2</span>
        </div>
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
          <span>{row?.update_time || '--'}</span>
        </div>
      </div>
    );
  }

  /**
   * @description: 表格 关联服务 列渲染
   */
  appliedServiceNamesColRenderer(row: AlarmTemplateListItem) {
    if (!row?.applied_service_names?.length) return '--';
    return (
      <div class='applied-service-name-col'>
        <div
          class='first-service-name'
          v-bk-overflow-tips
        >
          <span>{row?.applied_service_names?.[0] || '--'}</span>
        </div>
        {row?.applied_service_names?.length > 1 && (
          <div
            class='service-name-ellipsis-tag'
            v-bk-tooltips={{ content: this.$t('查看全部关联服务') }}
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
  algorithmsColRenderer(row: AlarmTemplateListItem) {
    return (
      <div class='algorithms-col'>
        <DetectionAlgorithmsGroup algorithms={row?.algorithms} />
        <div class='edit-btn'>
          <i class='icon-monitor icon-bianji' />
        </div>
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
          pre-check={() => this.handleSwitcherChange(row.id, value, columnKey)}
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
        <i class='more-btn icon-monitor icon-gengduo1' />
      </div>
    );
  }

  defaultRenderer(row: AlarmTemplateListItem, column) {
    return row[column.columnKey] || '--';
  }

  transformColumn(column) {
    return (
      <bk-table-column
        key={`column_${column.id}`}
        width={column.width}
        align={column.align}
        column-key={column.id}
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
      <div class='alarm-template-container'>
        <bk-table
          ref='tableRef'
          height='100%'
          class={`alarm-template-table ${this.tableLoadingActiveClassConfig}`}
          auto-scroll-to-top={true}
          border={false}
          data={this.tableData}
          outer-border={false}
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
            onCancel={this.handlePopoverHide}
            onConfirm={this.handleDeleteTemplateConfirm}
          />
        </div>
      </div>
    );
  }
}
