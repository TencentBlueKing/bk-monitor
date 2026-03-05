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

import { bkMessage } from 'monitor-api/utils';
import { copyText } from 'monitor-common/utils';
import { transformLogUrlQuery } from 'monitor-pc/utils';

import {
  type BaseTableColumn,
  type TableCellRenderContext,
  ExploreTableColumnTypeEnum,
} from '../../../../trace-explore/components/trace-explore-table/typing';
import { ALERT_STORAGE_KEY } from '../../../services/alert-services';
import {
  type AlertRowOperationAction,
  type AlertTableItem,
  type TableEmpty,
  AlarmLevelIconMap,
  AlertAllActionEnum,
  AlertDataTypeMap,
  AlertStatusMap,
  AlertTargetTypeMap,
  EXTEND_INFO_MAP,
} from '../../../typings';
import { BaseScenario } from './base-scenario';

import type { IUsePopoverTools } from '../hooks/use-popover';
import type { SlotReturnValue } from 'tdesign-vue-next';
import type { TippyContent } from 'vue-tippy';

/**
 * @class AlertScenario
 * @classdesc 告警场景表格特殊列渲染配置类
 * @extends BaseScenario
 */
export class AlertScenario extends BaseScenario {
  readonly name = ALERT_STORAGE_KEY;
  readonly privateClassName = 'alert-table';

  constructor(
    private readonly context: {
      clickPopoverTools: IUsePopoverTools;
      handleAlertContentDetailShow: (e: MouseEvent, row: AlertTableItem, colKey: string) => void;
      handleAlertOperationClick: (actionType: AlertRowOperationAction, row: AlertTableItem) => void;
      handleAlertSliderShowDetail: (id: string, defaultTab?: string) => void;
      hoverPopoverTools: IUsePopoverTools;
    }
  ) {
    super();
  }

  getEmptyConfig(): TableEmpty {
    return {
      type: 'search-empty',
      emptyText: window.i18n.t('当前检索范围，暂无告警'),
    };
  }

  getColumnsConfig(): Record<string, Partial<BaseTableColumn>> {
    const columns: Record<string, Partial<BaseTableColumn>> = {
      /** 告警状态(alert_status) 列 */
      alert_name: {
        attrs: { class: 'alarm-first-col' },
        cellRenderer: row => this.renderAlertName(row),
      },
      /** 告警指标(metric) 列 */
      metric: {
        renderType: ExploreTableColumnTypeEnum.TAGS,
        cellSpecificProps: {
          ellipsisTip: this.handleMetricEllipsisTip,
          ellipsisTippyOptions: {
            theme: 'dark text-wrap max-width-50vw alarm-center-popover',
          },
        },
      } satisfies BaseTableColumn<ExploreTableColumnTypeEnum.TAGS>,
      /** 关联事件(event_count) 列 */
      event_count: {
        renderType: ExploreTableColumnTypeEnum.CLICK,
        getRenderValue: row => (row.event_count > 0 ? row.event_count : undefined),
        clickCallback: row => {
          this.context.handleAlertSliderShowDetail(row.id, 'event');
        },
      },
      /** 首次异常时间(first_anomaly_time) 列 */
      first_anomaly_time: {
        renderType: ExploreTableColumnTypeEnum.TIME,
      },
      /** 告警内容(description) 列 */
      description: {
        cellRenderer: (row, column, renderCtx) => this.renderDescription(row, column, renderCtx),
        getRenderValue: row => ({ prefixIcon: AlertDataTypeMap[row.data_type]?.prefixIcon, alias: row.description }),
      },
      /** 监控目标(target_key) 列 */
      target_key: {
        renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
        getRenderValue: row => ({
          prefixIcon: AlertTargetTypeMap[row.target_type]?.prefixIcon,
          alias: row?.extend_info?.topo_info ? `${row?.extend_info?.topo_info} ${row.target_key}` : row.target_key,
        }),
      },
      /** 维度(tags) 列 */
      tags: {
        renderType: ExploreTableColumnTypeEnum.TAGS,
        getRenderValue: row => {
          return row.tags?.map?.(e => ({ alias: `${e.key}: ${e.value}`, value: e.value }));
        },
      },
      /** 关联信息(extend_info) 列 */
      extend_info: {
        cellRenderer: row => this.renderExtendInfo(row),
      },
      /** 负责人(appointee) 列 */
      appointee: {
        renderType: ExploreTableColumnTypeEnum.USER_TAGS,
      },
      /** 通知人(assignee) 列 */
      assignee: {
        renderType: ExploreTableColumnTypeEnum.USER_TAGS,
      },
      /** 关注人(follower) 列 */
      follower: {
        renderType: ExploreTableColumnTypeEnum.USER_TAGS,
      },
      /** 策略名称(strategy_name) 列 */
      strategy_name: {
        renderType: ExploreTableColumnTypeEnum.LINK,
        getRenderValue: row => ({ url: this.getStrategyUrl(row.strategy_id, row.bk_biz_id), alias: row.strategy_name }),
      },
      /** 策略标签(labels) 列 */
      labels: {
        renderType: ExploreTableColumnTypeEnum.TAGS,
      },
      /** 状态(status) 列 */
      status: {
        renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
        getRenderValue: row => AlertStatusMap?.[row.status],
        attrs: { class: 'alert-status-col' },
        suffixSlot: (row, column) => this.renderOperatePanel(row, column),
      },
    };

    return columns;
  }

  // ----------------- 告警场景私有渲染方法 -----------------
  /**
   * @description 告警名称(alert_name) 列渲染方法
   * @param {AlertTableItem} row 告警项
   * @returns {SlotReturnValue} 渲染dom
   */
  private renderAlertName(row: AlertTableItem): SlotReturnValue {
    const rectColor = AlarmLevelIconMap?.[row?.severity]?.iconColor;
    return (
      <div class='explore-col lever-rect-col'>
        <i
          style={{ '--lever-rect-color': rectColor }}
          class='lever-rect'
        />
        <div
          class='lever-rect-text ellipsis-text'
          onClick={() => this.context.handleAlertSliderShowDetail(row.id)}
          onMouseenter={e => this.handleAlterNameHover(e, row)}
          onMouseleave={this.context.hoverPopoverTools.clearPopoverTimer}
        >
          <span>{row?.alert_name}</span>
        </div>
      </div>
    ) as unknown as SlotReturnValue;
  }
  /**
   * @description 关联信息(extend_info) 列渲染方法
   * @param {AlertTableItem} row 告警项
   * @returns {SlotReturnValue} 渲染dom
   */
  private renderExtendInfo(row: AlertTableItem): SlotReturnValue {
    return (
      <div class='explore-col alert-extend-info-col'>
        <div
          onMouseenter={e => this.handleExtendInfoHover(e, row.extend_info)}
          onMouseleave={this.context.hoverPopoverTools.clearPopoverTimer}
        >
          {row.extend_info?.type ? this.getExtendInfoColumn(row) : '--'}
        </div>
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description 告警内容(description) 列渲染方法
   * @param {AlertTableItem} row 告警项
   * @param {BaseTableColumn} column 触发列的列配置项
   * @param {TableCellRenderContext} renderCtx 列渲染上下文
   * @returns {SlotReturnValue} 渲染dom
   */
  private renderDescription(
    row: AlertTableItem,
    column: BaseTableColumn,
    renderCtx: TableCellRenderContext
  ): SlotReturnValue {
    const item = column?.getRenderValue?.(row, column);
    return (
      <div class='explore-col explore-prefix-icon-col alert-description-col'>
        <i class={`prefix-icon ${item?.prefixIcon}`} />
        <div
          class={`${renderCtx.isEnabledCellEllipsis(column)} description-click`}
          onClick={(e: MouseEvent) => this.context.handleAlertContentDetailShow(e, row, column.colKey)}
        >
          <span>{item.alias || '--'}</span>
        </div>
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description 状态(status) 列 插槽 操作面板渲染方法
   * @param {AlertTableItem} row 告警项
   * @param {BaseTableColumn} column 触发列的列配置项
   * @returns {SlotReturnValue} 渲染dom
   */
  private renderOperatePanel(row: AlertTableItem, column?: BaseTableColumn) {
    const { status, is_ack: isAck, ack_operator: ackOperator, followerDisabled } = row;
    const colKey = column?.colKey;
    const moreMenuIsActive =
      this.context.clickPopoverTools?.popoverInstance?.value?.instanceKey === `${row.id}-${colKey}-more`;
    return (
      <div class={`operate-panel ${moreMenuIsActive ? 'more-menu-active' : ''}`}>
        {window.enable_create_chat_group ? (
          <span
            class='operate-panel-item icon-monitor icon-we-com'
            v-tippy={{ content: window.i18n.t('一键拉群'), delay: 200 }}
            onClick={() => this.context.handleAlertOperationClick(AlertAllActionEnum.CHAT, row)}
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
            this.context.handleAlertOperationClick(AlertAllActionEnum.CONFIRM, row)
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
            !followerDisabled && this.context.handleAlertOperationClick(AlertAllActionEnum.MANUAL_HANDLING, row)
          }
        />
        <span
          class={['operate-more']}
          onClick={e => this.handleMoreOperationClick(e, row, column.colKey)}
        >
          <span class='icon-monitor icon-mc-more' />
        </span>
      </div>
    ) as unknown as SlotReturnValue;
  }

  // ----------------- 告警场景私有逻辑方法 -----------------
  /**
   * @description 告警名称(alert_name) 列 hover事件
   * @param {MouseEvent} e 鼠标事件
   * @param {AlertTableItem} row 告警项
   */
  private handleAlterNameHover(e: MouseEvent, row: AlertTableItem) {
    const content = (
      <div class='alert-name-popover-container'>
        <div class='alert-name-item'>
          <span class='alert-name-item-label'>{window.i18n.t('告警 ID')} : </span>
          <div
            class='alert-name-item-value'
            onClick={() => this.handleCopy(row?.id)}
          >
            <span class='item-text'>{row?.id || '--'}</span>
            <i class='icon-monitor icon-mc-copy' />
          </div>
        </div>
        <div class='alert-name-item'>
          <span class='alert-name-item-label'>{window.i18n.t('告警策略')} : </span>
          <div class='alert-name-item-value'>
            <a
              style='color: inherit'
              href={this.getStrategyUrl(row?.strategy_id, row?.bk_biz_id)}
              rel='noreferrer'
              target='_blank'
            >
              <span class='alert-name-item-value'>{row?.strategy_name || '--'}</span>
              <i class='icon-monitor icon-mc-goto' />
            </a>
          </div>
        </div>
      </div>
    ) as unknown as TippyContent;
    this.context.hoverPopoverTools.showPopover(e, content);
  }

  /**
   * @description 告警指标(metric) 列溢出的指标hover展示内容
   * @param ellipsisList 溢出的指标列表
   * @returns {SlotReturnValue} 溢出指标展示渲染内容dom
   */
  private handleMetricEllipsisTip(ellipsisList: string[]) {
    return (
      <div class='alert-metric-ellipsis-tip-container'>
        {ellipsisList.map((v, i) => (
          <div
            key={`${v}-${i}`}
            class='ellipsis-tip-item'
          >
            <div class='item-prefix'>
              <i class='item-hyphen' />
            </div>
            <div class='item-text'>{v}</div>
          </div>
        ))}
      </div>
    ) as unknown as SlotReturnValue;
  }

  /**
   * @description 关联信息(extend_info) 列 hover事件
   * @param {MouseEvent} e 鼠标事件
   * @param {any} info 关联信息
   */
  private handleExtendInfoHover(e: MouseEvent, info: any) {
    let content = '--';
    switch (info.type) {
      case 'host':
        content = `<div class="extend-content">${window.i18n.t('主机名:')}${info.hostname || '--'}</div>
            <div class="extend-content">
              <span class="extend-content-message">${window.i18n.t('节点信息:')}${info.topo_info || '--'}</span>
            </div>
          `;
        break;
      case 'log_search':
      case 'custom_event':
      case 'bkdata':
        content = `<span class="extend-content-link">
            ${EXTEND_INFO_MAP[info.type] || '--'}
          </span>`;
        break;
      default:
        break;
    }

    const tplStr = `<div class='extend-info-popover-container'>
        ${content}
      </div>`;
    this.context.hoverPopoverTools.showPopover(e, tplStr, {
      allowHTML: true,
    });
  }

  /**
   * @description 关联信息(extend_info) 列 不同类型需要展示不同的内容
   * @param {AlertTableItem} row 告警项
   */
  private getExtendInfoColumn(row: AlertTableItem) {
    const extendInfo = row.extend_info;
    const bizId = row.bk_biz_id?.toString?.();
    switch (extendInfo.type) {
      case 'host':
        return [
          <div
            key={'extend-content-1'}
            class='extend-content'
          >{`${window.i18n.t('主机名:')}${extendInfo.hostname || '--'}`}</div>,
          <div
            key={'extend-content-2'}
            class='extend-content'
          >
            <span class='extend-content-message'>{`${window.i18n.t('节点信息:')}${extendInfo.topo_info || '--'}`}</span>
            <span
              class='extend-content-link link-more'
              onClick={() => this.handleGotoMore(extendInfo, bizId)}
            >
              {window.i18n.t('更多')}
            </span>
          </div>,
        ];
      case 'log_search':
      case 'custom_event':
      case 'bkdata':
        return (
          <span
            class='extend-content-link'
            onClick={() => this.handleGotoMore(extendInfo, bizId)}
          >
            {EXTEND_INFO_MAP[extendInfo.type] || '--'}
          </span>
        );
    }
    return '--';
  }

  /**
   * @method handleGotoMore 关联信息(extend_info) 列 click 事件
   * @description 处理不同类型的跳转逻辑
   * @param {Record<string, any>} extendInfo 关联信息
   * @param {string} bizId 业务ID
   */
  private handleGotoMore(extendInfo: Record<string, any>, bizId: string) {
    const origin = process.env.NODE_ENV === 'development' ? process.env.proxyUrl.replace(/\/$/, '') : location.origin;
    switch (extendInfo.type) {
      // 监控主机监控详情
      case 'host': {
        const detailId =
          extendInfo.bk_host_id ??
          `${extendInfo.ip}-${extendInfo.bk_cloud_id === undefined ? 0 : extendInfo.bk_cloud_id}`;
        window.open(
          `${origin}${location.pathname.toString().replace('fta/', '')}?bizId=${bizId}#/performance/detail/${detailId}`,
          '_blank'
        );
        return;
      }
      // 监控数据检索
      case 'bkdata': {
        const targets = [{ data: { query_configs: extendInfo.query_configs } }];
        window.open(
          `${origin}${location.pathname
            .toString()
            .replace(
              'fta/',
              ''
            )}?bizId=${bizId}#/data-retrieval/?targets=${encodeURIComponent(JSON.stringify(targets))}`,
          '_blank'
        );
        return;
      }
      // 日志检索
      case 'log_search': {
        const retrieveParams = {
          // 检索参数
          bizId,
          keyword: extendInfo.query_string, // 搜索关键字
          addition: extendInfo.agg_condition || [],
        };
        const queryStr = transformLogUrlQuery(retrieveParams);
        const url = `${window.bk_log_search_url}#/retrieve/${extendInfo.index_set_id}${queryStr}`;
        window.open(url);
        return;
      }
      // 监控自定义事件
      case 'custom_event': {
        const id = extendInfo.bk_event_group_id;
        window.open(
          `${origin}${location.pathname
            .toString()
            .replace('fta/', '')}?bizId=${bizId}#/custom-escalation-detail/event/${id}`,
          '_blank'
        );
        return;
      }
    }
  }

  /**
   * @description 处理复制事件
   * @param {string} text 复制文本
   */
  private handleCopy(text) {
    copyText(text || '--', msg => {
      bkMessage({
        message: msg,
        theme: 'error',
      });
      return;
    });
    bkMessage({
      message: window.i18n.t('复制成功'),
      theme: 'success',
    });
  }

  /**
   * @description 拼接 策略详情 页面url
   * @param {string} strategy_id 策略ID
   * @param {string} bk_biz_id 业务ID
   */
  private getStrategyUrl(strategy_id, bk_biz_id) {
    if (!strategy_id) return;
    return `${location.origin}${location.pathname}?bizId=${bk_biz_id}#/strategy-config/detail/${strategy_id}`;
  }

  /**
   * @description 获取告警确认文案
   * @param {boolean} isAak 是否确认
   * @param {string} status 告警状态
   * @param {string} ackOperator 确认人
   * @param {boolean} followerDisabled 是否关注人
   * @return {string} 告警确认提示文案
   */
  private askTipMsg(isAak, status, ackOperator, followerDisabled) {
    const statusNames = {
      RECOVERED: window.i18n.t('告警已恢复'),
      CLOSED: window.i18n.t('告警已关闭'),
    };
    if (followerDisabled) {
      return window.i18n.t('关注人禁用此操作');
    }
    if (!isAak) {
      return statusNames[status];
    }
    return `${ackOperator || ''}${window.i18n.t('已确认')}`;
  }

  /**
   * @description 获取更多操作下拉菜单 Menu dom
   * @param {AlertTableItem} row 告警项
   * @returns {Element} 更多操作下拉菜单 dom
   */
  private getMoreMenuDom(row: AlertTableItem) {
    return (
      <div class='alert-table-more-operation-menu'>
        <div
          class={['more-item', { 'is-disable': row?.is_shielded || row?.followerDisabled }]}
          onClick={() =>
            !row?.is_shielded &&
            !row?.followerDisabled &&
            this.context.handleAlertOperationClick(AlertAllActionEnum.SHIELD, row)
          }
          onMouseenter={(e: MouseEvent) => {
            let content = row?.is_shielded ? `${row.shield_operator?.[0] || ''}${window.i18n.t('已屏蔽')}` : '';
            if (row?.followerDisabled) {
              content = window.i18n.t('关注人禁用此操作');
            }
            this.context.hoverPopoverTools?.showPopover?.(e, content, {
              theme: 'alarm-center-popover max-width-50vw text-wrap',
            });
          }}
        >
          <span class='icon-monitor icon-mc-notice-shield' />
          <span>{window.i18n.t('快捷屏蔽')}</span>
        </div>

        <div
          class={['more-item', { 'is-disable': row?.followerDisabled }]}
          onClick={() => this.context.handleAlertOperationClick(AlertAllActionEnum.DISPATCH, row)}
          onMouseenter={(e: MouseEvent) => {
            const content = row?.followerDisabled ? window.i18n.t('关注人禁用此操作') : '';
            this.context.hoverPopoverTools?.showPopover?.(e, content, {
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
  private handleMoreOperationClick(e: MouseEvent, row: AlertTableItem, colKey: string) {
    const dom = this.getMoreMenuDom(row);
    this.context.clickPopoverTools.showPopover(e, dom, `${row.id}-${colKey}-more`, { arrow: false });
  }
}
