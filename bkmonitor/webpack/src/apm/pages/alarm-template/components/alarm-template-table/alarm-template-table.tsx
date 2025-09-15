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
import loadingIcon from 'monitor-ui/chart-plugins/icons/spinner.svg';

import { AlarmTemplateDetailTabEnum, TABLE_DEFAULT_DISPLAY_FIELDS } from '../../constant';
import { type AlarmTemplateDetailTabEnumType, type AlarmTemplateListItem } from '../../typeing';
import AlarmDeleteConfirm, { type AlarmDeleteConfirmEvent } from '../alarm-delete-confirm/alarm-delete-confirm';

import './alarm-template-table.scss';

interface AlarmTemplateTableEmits {
  /** 清空筛选条件 */
  onClearSearch: () => void;
  /** 删除查询模板事件回调 */
  onDeleteTemplate: (templateId: string, confirmEvent: AlarmDeleteConfirmEvent) => void;
}

interface AlarmTemplateTableProps {
  /** 空数据类型 */
  emptyType: 'empty' | 'search-empty';
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
  /** 总数 */
  @Prop({ type: Number }) total: number;
  /** 空数据类型 */
  @Prop({ type: String, default: 'empty' }) emptyType: 'empty' | 'search-empty';

  /** 模板详情 - 侧弹抽屉显示状态 */
  sliderShow = false;
  /** 模板详情 - 侧弹抽屉显示时默认激活的 tab 面板 */
  sliderActiveTab: AlarmTemplateDetailTabEnumType = null;
  /** 模板详情 - 当前需要显示详情信息的数据 id */
  sliderActiveId: AlarmTemplateListItem['id'] = null;
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
      formatter: this.clickShowSlicerColRenderer,
    },
    category: {
      id: 'category',
      label: this.$t('模板类型'),
      minWidth: 180,
    },
    update_time: {
      id: 'update_time',
      label: this.$t('最近更新'),
      minWidth: 220,
    },
    applied_service_names: {
      id: 'applied_service_names',
      label: this.$t('关联服务'),
      width: 100,
      formatter: this.userColRenderer,
    },
    algorithms: {
      id: 'algorithms',
      label: this.$t('检测规则'),
      sortable: true,
      width: 180,
    },
    user_group_list: {
      id: 'user_group_list',
      label: this.$t('告警组'),
      width: 100,
      formatter: this.userColRenderer,
    },
    is_enabled: {
      id: 'is_enabled',
      label: this.$t('启用 / 禁用'),
      sortable: true,
      width: 180,
    },
    is_auto_apply: {
      id: 'is_auto_apply',
      label: this.$t('自动下发'),
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
    return TABLE_DEFAULT_DISPLAY_FIELDS.map(field => this.allTableColumns[field]);
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
  }
  beforeDestroy() {
    this.tableRef?.$el.removeEventListener('wheel', this.handlePopoverHide);
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
   * @description: 打开/关闭 侧弹详情抽屉面板
   */
  handleSliderShowChange(
    isShow: boolean,
    showEvent?: {
      ActiveSliderTab?: AlarmTemplateDetailTabEnumType;
      id: AlarmTemplateListItem['id'];
    }
  ) {
    let sliderTab = null;
    if (isShow) {
      sliderTab = showEvent?.ActiveSliderTab || AlarmTemplateDetailTabEnum.BASE_INFO;
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
      name: 'alarm-template-edit',
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
          {/* <TemplateDetail
            defaultActiveTab={this.sliderActiveTab}
            sliderShow={this.sliderShow}
            templateId={this.sliderActiveId}
            onDeleteTemplate={(templateId, confirmEvent) => this.$emit('deleteTemplate', templateId, confirmEvent)}
            onEdit={this.jumpToEditPage}
            onSliderShowChange={this.handleSliderShowChange}
          /> */}
        </div>
      </div>
    );
  }
}
