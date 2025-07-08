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
  EventStatusMap,
  type TableColumnItem,
} from '../../typings';
import CommonTable from './components/common-table';

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
     * @description 将 string[] 类型数据转换成 tag 列所需结构数据
     * @param row
     * @param column
     * @returns
     */
    function convertStringArrayToTags(row, column) {
      return row[column.colKey]?.map?.(e => ({ alias: e, value: e }));
    }

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
          clickCallback(row, column, event) {},
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
          renderType: ExploreTableColumnTypeEnum.TAGS,
          getRenderValue(row) {
            const tagInfo = EventStatusMap?.[row.status];
            if (!tagInfo) return;
            return [tagInfo];
          },
        },
      };
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
        columns={this.transformedColumns}
        {...this.$attrs}
      />
    );
  },
});
