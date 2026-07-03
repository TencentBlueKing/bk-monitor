import { AlertScenario } from '../../alarm-center/components/alarm-table/scenarios/alert-scenario';
import {
  type AlertRowOperationAction,
  type AlertTableItem,
  type TableEmpty,
  AlarmLevelIconMap,
  AlertAllActionEnum,
  AlertStatusMap,
} from '../../alarm-center/typings';
import CollapseTagsMultiRows from '../../trace-explore/components/trace-explore-table/components/table-cell/collapse-tags-multi-rows';
import {
  type BaseTableColumn,
  type TagCellItem,
  ExploreTableColumnTypeEnum,
} from '../../trace-explore/components/trace-explore-table/typing';
import { checkIsRoot } from '../utils';
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
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY ARISING FROM, OUT OF OR IN
 * CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

import type { IUsePopoverTools } from '../../alarm-center/components/alarm-table/hooks/use-popover';
import type { SlotReturnValue } from 'tdesign-vue-next';

/** 故障告警场景额外操作类型 */
export const INCIDENT_ALERT_ACTION = {
  /** 反馈根因 */
  ROOT_CAUSE: 'root_cause',
} as const;

export type IncidentAlertAction =
  | (typeof INCIDENT_ALERT_ACTION)[keyof typeof INCIDENT_ALERT_ACTION]
  | AlertRowOperationAction;

export interface IncidentAlertScenarioContext {
  clickPopoverTools: IUsePopoverTools;
  hoverPopoverTools: IUsePopoverTools;
  handleAlertContentDetailShow: (e: MouseEvent, row: AlertTableItem, colKey: string) => void;
  handleAlertOperationClick: (actionType: IncidentAlertAction, row: AlertTableItem) => void;
  handleAlertSliderShowDetail: (row: AlertTableItem, defaultTab?: string) => void;
  handleRootCauseConfirm: (row: AlertTableItem) => void;
}

/**
 * @class IncidentAlertScenario
 * @classdesc 故障详情页-告警列表场景表格特殊列渲染配置类
 * @extends AlertScenario
 *
 * 在 AlertScenario 基础上增加：
 * 1. alert_name 列增加根因标签（root-cause/root-feed）
 * 2. 操作面板增加"反馈根因"按钮
 * 3. 更多菜单保持：快捷屏蔽、告警分派
 */
export class IncidentAlertScenario extends AlertScenario {
  readonly name: string = 'incident-alert';
  readonly privateClassName: string = 'incident-alert-table';

  constructor(private readonly incidentContext: IncidentAlertScenarioContext) {
    super({
      clickPopoverTools: incidentContext.clickPopoverTools,
      handleAlertContentDetailShow: incidentContext.handleAlertContentDetailShow,
      handleAlertOperationClick: incidentContext.handleAlertOperationClick as (
        actionType: AlertRowOperationAction,
        row: AlertTableItem
      ) => void,
      handleAlertSliderShowDetail: incidentContext.handleAlertSliderShowDetail,
      hoverPopoverTools: incidentContext.hoverPopoverTools,
    });
  }

  getEmptyConfig(): TableEmpty {
    return {
      type: 'search-empty',
      emptyText: window.i18n.t('暂无告警'),
    };
  }

  getColumnsConfig(): Record<string, Partial<BaseTableColumn>> {
    const baseConfig = super.getColumnsConfig();
    return {
      ...baseConfig,
      /** 覆盖 alert_name 列渲染：增加根因标签 */
      alert_name: {
        attrs: { class: 'alarm-first-col' },
        cellRenderer: (row: AlertTableItem) => this.renderAlertNameWithRootCause(row),
      },
      /** 覆盖 metric 列渲染：数据来自 row.metric_display */
      metric: {
        renderType: ExploreTableColumnTypeEnum.TAGS,
        getRenderValue: (row: AlertTableItem) =>
          row.metric_display?.map(item => ({ alias: item.name || item.id, value: item.id })),
        cellSpecificProps: {
          ellipsisTip: (ellipsisList: any[]) => this.handleMetricEllipsisTip(ellipsisList),
          ellipsisTippyOptions: {
            theme: 'dark text-wrap max-width-50vw alarm-center-popover',
          },
        },
      } satisfies BaseTableColumn<ExploreTableColumnTypeEnum.TAGS>,
      /** 覆盖 tags 列：使用独立的故障告警 tags 组件渲染，最大展示4行 */
      tags: {
        cellRenderer: (row: AlertTableItem) => {
          const tags = row.tags?.map?.(e => ({
            alias: `${e.key.replace(/^tags\./, '')}: ${e.value}`,
            value: e.value,
          })) as TagCellItem[];
          if (!tags?.length) return '--';
          return (
            <CollapseTagsMultiRows
              data={tags}
              maxRows={4}
            />
          ) as unknown as SlotReturnValue;
        },
      },
      /** 覆盖 status 列：使用故障场景的操作面板（含反馈根因、告警分派） */
      status: {
        renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
        getRenderValue: (row: AlertTableItem) => AlertStatusMap?.[row.status],
        attrs: { class: 'alert-status-col' },
        suffixSlot: (row: AlertTableItem, column: BaseTableColumn) => this.renderOperatePanel(row, column),
      },
    };
  }

  // ----------------- 故障场景私有渲染方法 -----------------

  /**
   * @description 告警名称列渲染 - 带根因标签
   * @param {AlertTableItem} row 告警项
   * @returns {SlotReturnValue} 渲染dom
   */
  private renderAlertNameWithRootCause(row: AlertTableItem): SlotReturnValue {
    const rectColor = AlarmLevelIconMap?.[row?.severity]?.iconColor;
    const { entity } = row as any;
    const isRoot = checkIsRoot(entity);
    const showRoot = isRoot || (row as any).is_feedback_root;

    return (
      <div class='explore-col lever-rect-col'>
        <i
          style={{ '--lever-rect-color': rectColor }}
          class='lever-rect'
        />
        <div
          class='lever-rect-text ellipsis-text'
          onClick={() => this.incidentContext.handleAlertSliderShowDetail(row)}
          onMouseenter={e => this.handleAlterNameHover(e, row)}
          onMouseleave={this.incidentContext.hoverPopoverTools.clearPopoverTimer}
        >
          <span>{row?.alert_name}</span>
        </div>
        {showRoot && <span class={`${isRoot ? 'root-cause' : 'root-feed'}`}>{window.i18n.t('根因')}</span>}
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description 告警指标(metric) 列溢出的指标hover展示内容
   * @param ellipsisList 溢出的指标列表（TagCellItem 对象数组）
   * @returns {SlotReturnValue} 溢出指标展示渲染内容dom
   */
  protected handleMetricEllipsisTip(ellipsisList: any[]) {
    return (
      <div class='alert-metric-ellipsis-tip-container'>
        {ellipsisList.map((v, i) => (
          <div
            key={`${v?.alias || v}-${i}`}
            class='ellipsis-tip-item'
          >
            <div class='item-prefix'>
              <i class='item-hyphen' />
            </div>
            <div class='item-text'>{v?.alias || v}</div>
          </div>
        ))}
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description 状态(status) 列 插槽 操作面板渲染方法 - 增加"反馈根因"
   * @param {AlertTableItem} row 告警项
   * @param {any} column 触发列的列配置项
   * @returns {SlotReturnValue} 渲染dom
   */
  protected renderOperatePanel(row: AlertTableItem, column?: any) {
    const { status, is_ack: isAck, ack_operator: ackOperator, followerDisabled } = row;
    const colKey = column?.colKey;
    const moreMenuIsActive =
      this.incidentContext.clickPopoverTools?.popoverInstance?.value?.instanceKey === `${row.id}-${colKey}-more`;

    const entity = (row as any)?.entity;
    const isFeedbackRoot = (row as any)?.is_feedback_root;

    return (
      <div class={`operate-panel ${moreMenuIsActive ? 'more-menu-active' : ''}`}>
        {window.enable_create_chat_group ? (
          <span
            class='operate-panel-item icon-monitor icon-we-com'
            v-tippy={{ content: window.i18n.t('一键拉群'), delay: 200 }}
            onClick={() => this.incidentContext.handleAlertOperationClick(AlertAllActionEnum.CHAT, row)}
          />
        ) : null}
        <span
          class={[
            'operate-panel-item icon-monitor icon-duihao',
            { 'is-disable': isAck || ['RECOVERED', 'CLOSED'].includes(status) || followerDisabled },
          ]}
          v-tippy={{
            content:
              isAck || ['RECOVERED', 'CLOSED'].includes(status) || followerDisabled
                ? this.askTipMsg(isAck, status, ackOperator, followerDisabled)
                : window.i18n.t('告警确认'),
            delay: 200,
            allowHTML: false,
          }}
          onClick={() =>
            !isAck &&
            !['RECOVERED', 'CLOSED'].includes(status) &&
            !followerDisabled &&
            this.incidentContext.handleAlertOperationClick(AlertAllActionEnum.CONFIRM, row)
          }
        />
        <span
          class={[
            'operate-panel-item icon-monitor icon-chuli',
            {
              'is-disable': followerDisabled,
            },
          ]}
          v-tippy={{
            content: followerDisabled ? window.i18n.t('关注人禁用此操作') : window.i18n.t('手动处理'),
            delay: 200,
          }}
          onClick={() =>
            !followerDisabled && this.incidentContext.handleAlertOperationClick(AlertAllActionEnum.MANUAL_HANDLING, row)
          }
        />
        {/* 故障特有：反馈根因 */}
        {!!entity && (
          <span
            class={['operate-panel-item', { 'is-disable': entity?.is_root }]}
            v-bk-tooltips={{
              content: isFeedbackRoot ? window.i18n.t('取消反馈根因') : window.i18n.t('反馈根因'),
              trigger: 'hover',
              delay: 200,
              disabled: entity?.is_root,
            }}
            onClick={() => this.incidentContext.handleRootCauseConfirm(row)}
          >
            <i class={['icon-monitor', !isFeedbackRoot ? 'icon-fankuixingenyin' : 'icon-mc-cancel-feedback']} />
          </span>
        )}
        <span
          class={['operate-more']}
          onClick={e => this.handleMoreOperationClick(e, row, column.colKey)}
        >
          <span class='icon-monitor icon-mc-more' />
        </span>
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description 获取更多操作下拉菜单 Menu dom - 快捷屏蔽 + 告警分派
   * @param {AlertTableItem} row 告警项
   * @returns {Element} 更多操作下拉菜单 dom
   */
  protected getMoreMenuDom(row: AlertTableItem) {
    return (
      <div class='alert-table-more-operation-menu'>
        <div
          class={['more-item', { 'is-disable': row?.is_shielded || row?.followerDisabled }]}
          onClick={() =>
            !row?.is_shielded &&
            !row?.followerDisabled &&
            this.incidentContext.handleAlertOperationClick(AlertAllActionEnum.SHIELD, row)
          }
          onMouseenter={(e: MouseEvent) => {
            let content = row?.is_shielded ? `${row.shield_operator?.[0] || ''}${window.i18n.t('已屏蔽')}` : '';
            if (row?.followerDisabled) {
              content = window.i18n.t('关注人禁用此操作');
            }
            this.incidentContext.hoverPopoverTools?.showPopover?.(e, content, {
              theme: 'alarm-center-popover max-width-50vw text-wrap',
            });
          }}
        >
          <span class='icon-monitor icon-mc-notice-shield' />
          <span>{window.i18n.t('快捷屏蔽')}</span>
        </div>

        <div
          class={['more-item', { 'is-disable': row?.followerDisabled }]}
          onClick={() => this.incidentContext.handleAlertOperationClick(AlertAllActionEnum.DISPATCH, row)}
          onMouseenter={(e: MouseEvent) => {
            const content = row?.followerDisabled ? window.i18n.t('关注人禁用此操作') : '';
            this.incidentContext.hoverPopoverTools?.showPopover?.(e, content, {
              theme: 'alarm-center-popover max-width-50vw text-wrap',
            });
          }}
        >
          <span class='icon-monitor icon-fenpai' />
          <span>{window.i18n.t('告警分派')}</span>
        </div>
      </div>
    ) as unknown as Element;
  }

  /**
   * @description alert Table 数据行操作栏中 更多 按钮点击回调
   * @param {MouseEvent} e 鼠标事件
   * @param {AlertTableItem} row 告警项
   * @param {string} colKey 列key
   */
  protected handleMoreOperationClick(e: MouseEvent, row: AlertTableItem, colKey: string) {
    const dom = this.getMoreMenuDom(row);
    this.incidentContext.clickPopoverTools.showPopover(e, dom, `${row.id}-${colKey}-more`, { arrow: false });
  }

  /**
   * @description 获取告警确认文案
   */
  protected askTipMsg(isAak, status, ackOperator, followerDisabled) {
    const statusNames = {
      RECOVERED: window.i18n.t('告警已恢复'),
      CLOSED: window.i18n.t('告警已失效'),
    };
    if (followerDisabled) {
      return window.i18n.t('关注人禁用此操作');
    }
    if (!isAak) {
      return statusNames[status];
    }
    return `${ackOperator || ''}${window.i18n.t('已确认')}`;
  }
}
