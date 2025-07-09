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
import { computed, defineComponent, toValue, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';
import { useTippy } from 'vue-tippy';

import { bkMessage } from 'monitor-api/utils';
import { copyText } from 'monitor-common/utils';
import { transformLogUrlQuery } from 'monitor-pc/utils';

import { useAlarmCenterStore } from '../../../../store/modules/alarm-center';
import {
  ExploreTableColumnTypeEnum,
  type BaseTableColumn,
} from '../../../trace-explore/components/trace-explore-table/typing';
import { ACTION_STORAGE_KEY } from '../../services/action-services';
import { ALERT_STORAGE_KEY } from '../../services/alert-services';
import { INCIDENT_STORAGE_KEY } from '../../services/incident-services';
import {
  AlarmLevelIconMap,
  type AlarmStorageKey,
  CONTENT_SCROLL_ELEMENT_CLASS_NAME,
  AlertStatusMap,
  EXTEND_INFO_MAP,
  type TableColumnItem,
  type TablePagination,
} from '../../typings';
import CommonTable from './components/common-table';

import type { BkUiSettings } from '@blueking/tdesign-ui/.';
import type { SlotReturnValue } from 'tdesign-vue-next';

import './alarm-table.scss';

export default defineComponent({
  name: 'AlarmTable',
  props: {
    /** 表格列配置 */
    columns: {
      type: Array as PropType<TableColumnItem[]>,
      default: () => [],
    },
    /** 表格分页属性类型 */
    pagination: {
      type: Object as PropType<TablePagination>,
    },
    /** 表格设置属性类型 */
    tableSettings: {
      type: Object as PropType<Omit<BkUiSettings, 'hasCheckAll'>>,
    },
    /** 表格渲染数据 */
    data: {
      type: Array as PropType<Record<string, any>[]>,
      default: () => [],
    },
    /** 表格加载状态 */
    loading: {
      type: Boolean,
      default: false,
    },
    /** 表格排序信息,字符串格式，以id为例：倒序 => -id；正序 => id；*/
    sort: {
      type: [String, Array] as PropType<string | string[]>,
    },
  },
  setup(props) {
    const alarmStore = useAlarmCenterStore();
    const { t } = useI18n();
    /** popover 实例 */
    let popoverInstance = null;
    /** popover 延迟打开定时器 */
    let popoverDelayTimer = null;

    /** 不同视角下获取需要特殊渲染的单元格列 column 配置项的方法集合 */
    const getSpecialRenderColumnsPropFnMap: Record<AlarmStorageKey, () => Record<string, BaseTableColumn>> = {
      [ALERT_STORAGE_KEY]: getAlterSpecialRenderColumnsProps,
      [INCIDENT_STORAGE_KEY]: () => ({}),
      [ACTION_STORAGE_KEY]: getAlterSpecialRenderColumnsProps,
    };

    const transformedColumns = computed(() => {
      const storageKey = alarmStore.alarmService.storageKey;
      const specialRenderColumnsPropsMap = getSpecialRenderColumnsPropFnMap[storageKey]?.() || {};
      return props.columns.map(column => ({
        ...column,
        ...(specialRenderColumnsPropsMap[column.colKey] || {}),
      }));
    });

    /**
     * @description 获取告警table表格列中单元格需要特殊渲染的列配置
     *
     */
    function getAlterSpecialRenderColumnsProps(): Record<string, BaseTableColumn> {
      return {
        alert_name: {
          cellRenderer: row => {
            const rectColor = AlarmLevelIconMap?.[row?.severity]?.iconColor;
            return (
              <div class='explore-col lever-rect-col'>
                <i
                  style={{ '--lever-rect-color': rectColor }}
                  class='lever-rect'
                />
                <div
                  class='lever-rect-text ellipsis-text'
                  onClick={() => handleShowDetail(row.id)}
                  onMouseenter={e => handleAlterNameHover(e, row)}
                  onMouseleave={handleClearTimer}
                >
                  <span>{row?.alert_name}</span>
                </div>
              </div>
            ) as unknown as SlotReturnValue;
          },
        },
        metric: {
          renderType: ExploreTableColumnTypeEnum.TAGS,
          getRenderValue: row => row.metric?.map?.(e => ({ alias: e, value: e })),
        },
        event_count: {
          renderType: ExploreTableColumnTypeEnum.CLICK,
          clickCallback(row) {
            handleShowDetail(row.id);
          },
        },
        create_time: {
          renderType: ExploreTableColumnTypeEnum.TIME,
        },
        begin_time: {
          renderType: ExploreTableColumnTypeEnum.TIME,
        },
        end_time: {
          renderType: ExploreTableColumnTypeEnum.TIME,
        },
        latest_time: {
          renderType: ExploreTableColumnTypeEnum.TIME,
        },
        first_anomaly_time: {
          renderType: ExploreTableColumnTypeEnum.TIME,
        },
        tags: {
          renderType: ExploreTableColumnTypeEnum.TAGS,
          getRenderValue: row => {
            return row.tags?.map?.(e => ({ alias: `${e.key}: ${e.value}`, value: e.value }));
          },
        },
        extend_info: {
          cellRenderer: row =>
            (
              <div class='explore-col'>
                <div
                  class='extend-info-col'
                  onMouseenter={e => handleExtendInfoEnter(e, row.extend_info)}
                  onMouseleave={handleClearTimer}
                >
                  {row.extend_info?.type ? getExtendInfoColumn(row.extend_info, row.bk_biz_id?.toString?.()) : '--'}
                </div>
              </div>
            ) as unknown as SlotReturnValue,
        },
        appointee: {
          renderType: ExploreTableColumnTypeEnum.TAGS,
        },
        assignee: {
          renderType: ExploreTableColumnTypeEnum.TAGS,
        },
        follower: {
          renderType: ExploreTableColumnTypeEnum.TAGS,
        },
        strategy_name: {
          renderType: ExploreTableColumnTypeEnum.LINK,
          getRenderValue: row => ({ url: getStrategyUrl(row.strategy_id, row.bk_biz_id), alias: row.strategy_name }),
        },
        labels: {
          renderType: ExploreTableColumnTypeEnum.TAGS,
        },
        status: {
          renderType: ExploreTableColumnTypeEnum.PREFIX_ICON,
          getRenderValue: row => AlertStatusMap?.[row.status],
        },
      };
    }

    /**
     * @description: 关联信息组件
     *
     */
    function getExtendInfoColumn(extendInfo: Record<string, string>, bizId: string) {
      switch (extendInfo.type) {
        case 'host':
          return [
            <div
              key={'extend-content-1'}
              class='extend-content'
            >{`${t('主机名:')}${extendInfo.hostname || '--'}`}</div>,
            <div
              key={'extend-content-2'}
              class='extend-content'
            >
              <span class='extend-content-message'>{`${t('节点信息:')}${extendInfo.topo_info || '--'}`}</span>
              <span
                class='extend-content-link link-more'
                onClick={() => handleGotoMore(extendInfo, bizId)}
              >
                {t('更多')}
              </span>
            </div>,
          ];
        case 'log_search':
        case 'custom_event':
        case 'bkdata':
          return (
            <span
              class='extend-content-link'
              onClick={() => handleGotoMore(extendInfo, bizId)}
            >
              {EXTEND_INFO_MAP[extendInfo.type] || '--'}
            </span>
          );
      }
      return '--';
    }

    /**
     * @description: 关联信息跳转
     *
     */
    function handleGotoMore(extendInfo: Record<string, any>, bizId: string) {
      const origin = process.env.NODE_ENV === 'development' ? process.env.proxyUrl : location.origin;
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

    /** 关联信息提示信息 */
    function handleExtendInfoEnter(e, info) {
      let tplStr = '--';
      switch (info.type) {
        case 'host':
          tplStr = `<div class="extend-content">${t('主机名:')}${info.hostname || '--'}</div>
            <div class="extend-content">
              <span class="extend-content-message">${t('节点信息:')}${info.topo_info || '--'}</span>
            </div>
          `;
          break;
        case 'log_search':
        case 'custom_event':
        case 'bkdata':
          tplStr = `<span class="extend-content-link">
            ${EXTEND_INFO_MAP[info.type] || '--'}
          </span>`;
          break;
        default:
          break;
      }
      handlePopoverShow(e, tplStr);
    }

    /**
     * @description 告警名称列 hover 展示popover事件
     *
     */
    function handleAlterNameHover(e: MouseEvent, row: Record<string, any>) {
      const content = (
        <div class='alert-name-popover-container'>
          <div class='alert-name-item'>
            <span class='alert-name-item-label'>{t('告警 ID')} : </span>
            <div
              class='alert-name-item-value'
              onClick={() => handleCopy(row?.id)}
            >
              <span class='item-text'>{row?.id || '--'}</span>
              <i class='icon-monitor icon-mc-copy' />
            </div>
          </div>
          <div class='alert-name-item'>
            <span class='alert-name-item-label'>{t('告警策略')} : </span>
            <div class='alert-name-item-value'>
              <a
                style='color: inherit'
                href={getStrategyUrl(row?.strategy_id, row?.bk_biz_id)}
                rel='noreferrer'
                target='_blank'
              >
                <span class='alert-name-item-value'>{row?.strategy_name || '--'}</span>
                <i class='icon-monitor icon-mc-goto' />
              </a>
            </div>
          </div>
        </div>
      );
      handlePopoverShow(e, content);
    }

    /**
     * @description: 展示详情
     *
     */
    function handleShowDetail(id: string) {
      alert(`记录${id}的详情弹窗`);
    }

    /**
     * @description 跳转策略详情页面
     *
     */
    function getStrategyUrl(strategy_id, bk_biz_id) {
      if (!strategy_id) return;
      return `${location.origin}${location.pathname}?bizId=${bk_biz_id}#/strategy-config/detail/${strategy_id}`;
    }

    /**
     * @description 处理复制事件
     *
     */
    function handleCopy(text) {
      copyText(text || '--', msg => {
        bkMessage({
          message: msg,
          theme: 'error',
        });
        return;
      });
      bkMessage({
        message: t('复制成功'),
        theme: 'success',
      });
    }

    /**
     * @description: 展开
     * @param {MouseEvent} e
     * @param {string} content
     */
    function handlePopoverShow(e: MouseEvent, content, customOptions = {}) {
      if (popoverInstance || popoverDelayTimer) {
        handlePopoverHide();
      }
      popoverInstance = useTippy(e.currentTarget, {
        content: toValue(content),
        appendTo: () => document.body,
        animation: false,
        maxWidth: 'none',
        allowHTML: true,
        arrow: true,
        interactive: true,
        theme: 'alarm-center-popover max-width-50vw text-wrap',
        onHidden: () => {
          handlePopoverHide();
        },
        ...customOptions,
      });
      const popoverCache = popoverInstance;
      popoverDelayTimer = setTimeout(() => {
        if (popoverCache === popoverInstance) {
          popoverInstance?.show?.(0);
        } else {
          popoverCache?.hide?.(0);
          popoverCache?.destroy?.();
        }
      }, 500);
    }
    /**
     * @description: 清除popover
     */
    function handlePopoverHide() {
      handleClearTimer();
      popoverInstance?.hide?.(0);
      popoverInstance?.destroy?.();
      popoverInstance = null;
    }

    /**
     * @description: 清除popover延时打开定时器
     *
     */
    function handleClearTimer() {
      popoverDelayTimer && clearTimeout(popoverDelayTimer);
      popoverDelayTimer = null;
    }

    return {
      transformedColumns,
    };
  },
  render() {
    return (
      <CommonTable
        class='alarm-table'
        headerAffixedTop={{
          container: `.${CONTENT_SCROLL_ELEMENT_CLASS_NAME}`,
        }}
        horizontalScrollAffixedBottom={{
          container: `.${CONTENT_SCROLL_ELEMENT_CLASS_NAME}`,
        }}
        tableSettings={{
          ...this.tableSettings,
          hasCheckAll: true,
        }}
        columns={this.transformedColumns}
        data={this.data}
        loading={this.loading}
        pagination={this.pagination}
        sort={this.sort}
        {...this.$emit}
      />
    );
  },
});
