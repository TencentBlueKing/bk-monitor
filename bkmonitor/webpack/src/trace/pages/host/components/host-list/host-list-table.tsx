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

import {
  type PropType,
  computed,
  defineComponent,
  nextTick,
  onBeforeUnmount,
  onMounted,
  shallowRef,
  useTemplateRef,
} from 'vue';

import { type BkUiSettings, type TableSort, PrimaryTable } from '@blueking/tdesign-ui';
import { useResizeObserver } from '@vueuse/core';
import { Checkbox, Pagination } from 'bkui-vue';
import { openAlarmCenter } from 'monitor-common/utils/alarm-center-router';
import tippy, { type Instance, type SingleTarget } from 'tippy.js';
import { useI18n } from 'vue-i18n';

import AcrossPageSelection, {
  type SelectTypeEnum,
  SelectType,
} from '../../../../components/across-page-selection/across-page-selection';
import TagOverflow from '../../../../components/tag-overflow/tag-overflow';
import { useTableEllipsis } from '../../../../hooks/use-table-popover';
import { usePopover } from '../../../alarm-center/components/alarm-table/hooks/use-popover';
import {
  type IHostColumnConfig,
  HOST_LIST_COLUMNS,
  HOST_LIST_ELLIPSIS_CELL_CLASS,
  HOST_LIST_PAGE_SIZE_LIST,
  HOST_METRIC_HEADER_ICON_MAP,
  HOST_STATUS_MAP,
  HOST_STATUS_TIPS_MAP,
  PROCESS_STATUS_TIPS_MAP,
} from '../../constants/host-list';
import AbnormalTips from './abnormal-tips/index';
import HostListIpStatusTips from './host-list-ip-status-tips';
import HostListSelectionTips from './host-list-selection-tips';
import UnresolveList from './unresolve-list/index';
import ExploreTableEmpty from '@/pages/trace-explore/components/trace-explore-table/components/explore-table-empty';

import type { IHostAlarmCount, IHostComponent, IStatusTipsConfig } from '../../types/host';
import type { IHostListRow } from '../../types/host-list';
import type { SlotReturnValue } from 'tdesign-vue-next';
import type { TippyContent } from 'vue-tippy';

import './host-list-table.scss';

/** 告警等级 → 色块背景色（对齐 performance-table alarmColorMap） */
const ALARM_LEVEL_COLOR: Record<number, string> = {
  1: '#ea3636',
  2: '#ff8000',
  3: '#ffd000',
};

/** 指标进度条颜色阈值 */
const getProgressColor = (value: number) => {
  if (value > 80) return '#EA3636';
  return '#2CAF5E';
};

/**
 * 取告警色块背景色：取有告警数且等级最高（level 最小）的颜色
 * 对齐 performance-table getStatusLabelBgColor
 */
const getAlarmColor = (alarmCount: IHostAlarmCount[]) => {
  if (!alarmCount?.length) {
    return '';
  }
  const top = alarmCount.reduce<null | { color: string; level: number }>((min, cur) => {
    return cur.count && (!min || cur.level < min.level)
      ? { color: ALARM_LEVEL_COLOR[cur.level] || '', level: cur.level }
      : min;
  }, null);
  return top?.color || '';
};

export default defineComponent({
  name: 'HostListTable',
  props: {
    /** 当前页数据 */
    data: {
      type: Array as PropType<IHostListRow[]>,
      default: () => [],
    },
    /** 展示列 id 列表 */
    visibleColumns: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /** 总条数 */
    total: {
      type: Number,
      default: 0,
    },
    /** 当前页码 */
    page: {
      type: Number,
      default: 1,
    },
    /** 每页条数 */
    pageSize: {
      type: Number,
      default: 50,
    },
    /** 排序（`-key` 倒序 / `key` 正序） */
    sort: {
      type: String,
      default: '',
    },
    /** 选中行 key 集合（Set，O(1) 判定；其余场景按需转数组） */
    selectedRowKeys: {
      type: Set as PropType<Set<number | string>>,
      default: () => new Set(),
    },
    /** 全选框状态：由父组件计算后下发，对齐 performance-table 的 allCheckValue */
    selectType: {
      type: Number as PropType<SelectTypeEnum>,
      default: SelectType.UN_SELECTED,
    },
    /** 指标数据加载中（指标列展示骨架） */
    metricLoading: {
      type: Boolean,
      default: false,
    },
    /** 置顶配置 */
    markValue: {
      type: Object as PropType<Record<string, number>>,
      default: () => ({}),
    },
    /** 表格空数据类型 */
    emptyType: {
      type: String as PropType<'empty' | 'search-empty'>,
      default: 'empty',
    },
  },
  emits: {
    sortChange: (_v: string) => true,
    clearFilter: () => true,
    pageChange: (_v: number) => true,
    pageSizeChange: (_v: number) => true,
    headerSelect: (_type: SelectTypeEnum) => true,
    rowCheck: (_id: string, _checked: boolean) => true,
    columnsChange: (_cols: string[]) => true,
    selectIpCell: (_row: IHostListRow) => true,
    ipMark: (_row: IHostListRow) => true,
    processClick: (_row: IHostListRow, _processId: string) => true,
  },
  setup(props, { emit }) {
    const { t, locale } = useI18n();
    const popover = usePopover();
    const tableRef = useTemplateRef<HTMLElement>('table');
    const bodyRef = useTemplateRef<HTMLElement>('body');
    const ipStatusTipsRef = useTemplateRef<InstanceType<typeof HostListIpStatusTips>>('ipStatusTips');
    const ipStatusTipsRow = shallowRef<IHostListRow | null>(null);
    const tipsContentRef = useTemplateRef<HTMLElement>('tipsContent');
    const unresolveContentRef = useTemplateRef<HTMLElement>('unresolveContent');

    /** 表格体最大高度（自适应屏幕，表内滚动，表头/分页不滚走） */
    const bodyHeight = shallowRef(400);
    /** 进程异常 tip 数据 */
    const tipsData = shallowRef<IStatusTipsConfig>({
      tipsText: '',
      linkText: '',
      linkUrl: '',
      docLink: '',
    });
    /** 未恢复告警 tip 列表 */
    const unresolveList = shallowRef<IHostAlarmCount[]>([]);
    let tipsPopoverInstance: Instance | null = null;
    let unresolvePopoverInstance: Instance | null = null;

    /** 监听整个表格容器高度，扣除分页区域后作为表格内容最大高度 */
    useResizeObserver(tableRef, entries => {
      const height = entries[0]?.contentRect?.height;
      if (height) {
        // 扣除分页高度（约 32px）+ margin-top（12px）+ 缓冲
        bodyHeight.value = Math.max(height - 44, 200);
      }
    });

    const { initListeners: initEllipsisListeners } = useTableEllipsis(bodyRef, {
      trigger: { selector: `.${HOST_LIST_ELLIPSIS_CELL_CLASS}` },
    });

    const destroyTipsPopover = () => {
      tipsPopoverInstance?.hide();
      tipsPopoverInstance?.destroy();
      tipsPopoverInstance = null;
    };

    const destroyUnresolvePopover = () => {
      unresolvePopoverInstance?.hide();
      unresolvePopoverInstance?.destroy();
      unresolvePopoverInstance = null;
    };

    onMounted(async () => {
      await nextTick();
      initEllipsisListeners();
    });

    onBeforeUnmount(() => {
      destroyTipsPopover();
      destroyUnresolvePopover();
    });

    /** 未恢复告警 hover 弹窗（对齐 performance-table handleUnresolveEnter） */
    const handleUnresolveEnter = async (row: IHostListRow, e: MouseEvent) => {
      if (!row.alarm_count?.length || !unresolveContentRef.value) {
        return;
      }
      const target = e.currentTarget as SingleTarget;
      unresolveList.value = row.alarm_count;
      destroyUnresolvePopover();
      await nextTick();
      if (!unresolveContentRef.value) return;
      unresolvePopoverInstance = tippy(target, {
        content: unresolveContentRef.value,
        trigger: 'manual',
        placement: 'right',
        theme: 'dark',
        arrow: true,
        maxWidth: 520,
        appendTo: () => document.body,
        onHidden: instance => {
          if (unresolvePopoverInstance !== instance) return;
          instance.destroy();
          unresolvePopoverInstance = null;
        },
      });
      unresolvePopoverInstance.show();
    };

    const handleUnresolveLeave = () => {
      destroyUnresolvePopover();
    };

    /** 点击告警数跳转告警中心（对齐 performance-table handleGoEventCenter） */
    const handleGoEventCenter = (row: IHostListRow) => {
      if (!row.bk_host_innerip || !row.totalAlarmCount) return;
      const localeStr = String(locale.value || '').toLowerCase();
      const isZh = ['zh', 'zhcn', 'zh-cn'].includes(localeStr.replace('_', '-'));
      openAlarmCenter({
        from: 'now-7d',
        to: 'now',
        queryString: isZh ? `目标IP : ${row.bk_host_innerip}` : `ip : ${row.bk_host_innerip}`,
        activeFilterId: 'NOT_SHIELDED_ABNORMAL',
      });
    };

    /**
     * 进程/主机状态 tip（对齐 performance-table handleTipsMouseenter）
     * Thread：异常(1) / 无数据(2)；noProcess：暂无进程引导；Host：无Agent(2) / 无数据上报(3)
     */
    const handleTipsMouseenter = (
      e: MouseEvent,
      item: Partial<IHostComponent> | Partial<IHostListRow>,
      type: 'Host' | 'noProcess' | 'Thread'
    ) => {
      if (type === 'Thread' && [1, 2].includes(item.status as number)) {
        const config = PROCESS_STATUS_TIPS_MAP[item.status as number] || {};
        tipsData.value = {
          tipsText: config.tipsText || '',
          linkText: config.linkText || '',
          linkUrl: config.linkUrl || '',
          docLink: config.docLink || '',
        };
      } else if (type === 'Host' && [2, 3].includes(item.status as number)) {
        const config = HOST_STATUS_TIPS_MAP[item.status as number] || {};
        tipsData.value = {
          tipsText: config.tipsText || '',
          linkText: config.linkText || '',
          linkUrl: config.linkUrl || '',
          docLink: config.docLink || '',
        };
      } else if (type === 'noProcess') {
        tipsData.value = {
          tipsText: t('若添加进程，请前往配置平台 - 业务拓扑，在对应模块下新增') as string,
          linkText: '',
          linkUrl: '',
          docLink: 'processPortMonitor',
        };
      } else {
        return;
      }

      if (tipsPopoverInstance || !tipsContentRef.value) {
        return;
      }

      tipsPopoverInstance = tippy(e.currentTarget as SingleTarget, {
        content: tipsContentRef.value,
        trigger: 'mouseenter',
        placement: 'top',
        theme: 'dark',
        arrow: true,
        interactive: true,
        appendTo: () => document.body,
        onHidden: instance => {
          if (tipsPopoverInstance !== instance) return;
          instance.destroy();
          tipsPopoverInstance = null;
        },
      });
      tipsPopoverInstance.show();
    };

    /** 排序转换为 tdesign 数组形式 */
    const tableSort = computed<TableSort>(() => {
      if (!props.sort) return [];
      const descending = props.sort.startsWith('-');
      return [{ sortBy: descending ? props.sort.slice(1) : props.sort, descending }];
    });

    /** 字段设置：全部字段 + 当前展示字段 */
    const tableSettings = computed<BkUiSettings>(() => ({
      fields: HOST_LIST_COLUMNS.map(column => ({ label: t(column.name), field: column.id, disabled: column.disabled })),
      checked: props.visibleColumns,
    }));

    /** 点击 IP 单元格时触发 selectIpCell 事件，由父组件处理拓扑树聚焦 */
    const handleSelectIpCell = (row: IHostListRow) => {
      emit('selectIpCell', row);
    };

    /** 普通文本溢出单元格（配合 useTableEllipsis 事件委托，溢出时弹 tooltip） */
    const renderEllipsisCell = (value: unknown) => (
      <span class={HOST_LIST_ELLIPSIS_CELL_CLASS}>{value === 0 || value ? value : '--'}</span>
    );

    /** IP 状态图标（对齐 performance-table handleIpStatusData） */
    const getIpStatusIcon = (ignoreMonitoring?: boolean, isShielding?: boolean): string => {
      if (ignoreMonitoring) return 'icon-celvepingbi';
      if (isShielding) return 'icon-menu-shield';
      return '';
    };

    // --- 单元格渲染器 ---
    const renderIpCell = (row: IHostListRow) => {
      const icon = getIpStatusIcon(row.ignore_monitoring, row.is_shielding);
      const isMarked = !!props.markValue?.[row.rowId];

      return (
        <div class='host-table-ip-cell'>
          <span
            class={`host-table-ip ${HOST_LIST_ELLIPSIS_CELL_CLASS}`}
            onClick={() => handleSelectIpCell(row)}
          >
            {row.display_name || row.bk_host_innerip || '--'}
          </span>
          {icon && (
            <i
              class={['icon-monitor', icon, 'host-table-ip-status']}
              onMouseenter={async (event: MouseEvent) => {
                ipStatusTipsRow.value = row;
                await nextTick();
                const inst = ipStatusTipsRef.value;
                if (inst) {
                  popover.showPopover(event, () => inst.$el as unknown as TippyContent, {
                    placement: 'right',
                    theme: 'light',
                    arrow: true,
                  });
                }
              }}
              onMouseleave={() => {
                popover.clearPopoverTimer();
              }}
            />
          )}
          {locale.value !== 'enUS' ? (
            <svg
              class={['host-table-ip-mark', isMarked ? 'path-primary' : 'path-default']}
              viewBox='0 0 28 16'
              onClick={(e: MouseEvent) => {
                e.stopPropagation();
                e.preventDefault();
                emit('ipMark', row);
              }}
            >
              <path d='M26,0H2C0.9,0,0,0.9,0,2v12c0,1.1,0.9,2,2,2h24c1.1,0,2-0.9,2-2V2C28,0.9,27.1,0,26,0z' />
              <path
                d='M5.1,11.3h1V7.5h2.6V7.1H5.3V6.3h3.4V5.9H5.7V4h7.7v2h-3.3v0.4h3.6v0.8h-3.6v0.4h2.8v3.8h1v0.8H5.1V11.3z M6.8,5.2h1.1V4.7H6.8V5.2z M11.7,8.2H7.3v0.3h4.4V8.2z M7.3,9.5h4.4V9.1H7.3V9.5z M7.3,10.4h4.4V10H7.3V10.4z M7.3,11.3h4.4v-0.3H7.3V11.3z M9,5.2h1.1V4.7H9V5.2z M12.2,5.2V4.7h-1.1v0.5H12.2z'
                fill='#FFFFFF'
              />
              <path
                d='M14.1,4.1h3.1v1.2h-0.8v5.4c0,0.4-0.1,0.6-0.2,0.8c-0.1,0.2-0.3,0.3-0.5,0.4s-0.7,0.1-1.4,0.1c0-0.4-0.1-0.7-0.2-1.1c0.3,0,0.5,0,0.8,0c0.2,0,0.4-0.1,0.4-0.4V5.3h-1.1V4.1z M19.4,7.5h1.2c0,0.9-0.1,1.6-0.2,2.1c0.8,0.5,1.7,1.1,2.5,1.7l-0.7,0.9c-0.6-0.5-1.3-1-2.2-1.7c-0.4,0.7-1.2,1.2-2.5,1.7c-0.2-0.3-0.4-0.7-0.7-1.1c0.6-0.2,1.2-0.4,1.6-0.7c0.4-0.3,0.7-0.7,0.8-1.1C19.3,8.9,19.4,8.3,19.4,7.5z M17.4,4h5.4v1.1h-2.3l-0.2,0.8h2.2v4h-1.2V7h-2.7v3h-1.2V5.9h1.5l0.2-0.8h-1.7V4z'
                fill='#FFFFFF'
              />
            </svg>
          ) : (
            <svg
              class={['host-table-ip-mark-en', isMarked ? 'path-primary' : 'path-default']}
              viewBox='0 0 28 16'
              onClick={(e: MouseEvent) => {
                e.stopPropagation();
                e.preventDefault();
                emit('ipMark', row);
              }}
            >
              <g>
                <path d='M13.7,5.7c-0.5,0-1,0.2-1.3,0.6C12,6.8,11.8,7.4,11.9,8c0,0.6,0.1,1.1,0.5,1.6c0.3,0.4,0.8,0.7,1.3,0.6c0.5,0,1-0.2,1.3-0.6c0.3-0.5,0.5-1.1,0.5-1.7c0-0.6-0.1-1.2-0.5-1.7C14.7,5.9,14.2,5.7,13.7,5.7z' />
                <path d='M20.2,5.7h-0.6v2.2h0.6c0.9,0,1.3-0.4,1.3-1.1C21.5,6,21.1,5.7,20.2,5.7z' />
                <path d='M26,0H2C0.9,0,0,0.9,0,2v12c0,1.1,0.9,2,2,2h24c1.1,0,2-0.9,2-2V2C28,0.9,27.1,0,26,0z M10.2,5.8H8.3v5.6H6.8V5.8H4.9V4.6h5.3V5.8z M16.1,10.5c-0.6,0.7-1.5,1-2.4,1c-0.9,0-1.8-0.3-2.4-1c-0.6-0.7-0.9-1.5-0.9-2.4c0-1,0.3-1.9,0.9-2.6c0.6-0.7,1.5-1,2.5-1c0.9,0,1.7,0.3,2.3,1C16.7,6.2,17,7,17,7.9C17,8.9,16.7,9.8,16.1,10.5z M22.3,8.4C21.7,8.9,21,9.1,20.3,9l-0.8,0v2.4h-1.5V4.6h2.3c1.7,0,2.5,0.7,2.5,2.1C23.1,7.4,22.8,8,22.3,8.4z' />
              </g>
            </svg>
          )}
        </div>
      );
    };

    const renderStatusCell = (row: IHostListRow) => {
      if (props.metricLoading && row.status === undefined) {
        return <div class='host-table-skeleton' />;
      }
      const config = HOST_STATUS_MAP[row.status];
      if (!config) {
        return <span>--</span>;
      }
      const needTips = [2, 3].includes(row.status);
      return (
        <div class='host-table-status'>
          <div
            style={{ backgroundColor: config.backgroundColor }}
            class='host-table-status__dot-wrapper'
          >
            <div
              style={{ backgroundColor: config.color }}
              class='host-table-status__dot'
            />
          </div>

          <span onMouseenter={e => needTips && handleTipsMouseenter(e, row, 'Host')}>{t(config.name)}</span>
        </div>
      );
    };

    const renderAlarmCell = (row: IHostListRow) => {
      if (props.metricLoading && !row.alarm_count) {
        return <div class='host-table-skeleton' />;
      }
      const hasAlarm = !!row.totalAlarmCount;
      return (
        <span
          style={{ backgroundColor: getAlarmColor(row.alarm_count) || undefined }}
          class={['host-table-alarm', { 'host-table-alarm--unresolve': hasAlarm }]}
          onClick={() => handleGoEventCenter(row)}
          onMouseenter={e => hasAlarm && handleUnresolveEnter(row, e)}
          onMouseleave={() => hasAlarm && handleUnresolveLeave()}
        >
          {row.totalAlarmCount >= 0 ? row.totalAlarmCount : '--'}
        </span>
      );
    };

    const renderMetricCell = (row: IHostListRow, key: string) => {
      if (props.metricLoading) {
        return <div class='host-table-skeleton' />;
      }
      const value = Number(row[key as keyof IHostListRow] ?? 0);
      if (!(value > 0)) {
        return <span class='host-table-metric__empty'>--</span>;
      }
      return (
        <div class='host-table-metric'>
          <span class='host-table-metric__value'>{`${+value.toFixed(2)}%`}</span>
          <div class='host-table-metric__bar'>
            <div
              style={{ width: `${Math.min(value, 100)}%`, backgroundColor: getProgressColor(value) }}
              class='host-table-metric__bar-inner'
            />
          </div>
        </div>
      );
    };

    const renderProcessCell = (row: IHostListRow) => {
      const components = row.component || [];
      return (
        <TagOverflow
          class='host-table-process'
          getLabel={item => (item as IHostComponent).display_name}
          list={components}
          overflowClass='host-table-process__tag host-table-process__tag--3'
          recalcKey={props.visibleColumns.join(',')}
        >
          {{
            default: ({ item, index }: { index: number; item: IHostComponent }) => (
              <span
                key={`${item.display_name}__${index}`}
                class={[
                  'host-table-process__tag',
                  item.status === -1 ? 'host-table-process__tag--default' : `host-table-process__tag--${item.status}`,
                ]}
                onClick={() => emit('processClick', row, item.display_name)}
                onMouseenter={e => handleTipsMouseenter(e, item, 'Thread')}
              >
                {item.display_name}
              </span>
            ),
            empty: () => (
              <span
                class='host-table-process__empty'
                onMouseenter={e => handleTipsMouseenter(e, {}, 'noProcess')}
              >
                {t('暂无进程')}
              </span>
            ),
          }}
        </TagOverflow>
      );
    };

    /** 指标列表头：固定聚合图标 + 标题（样式保持新版纵向布局，逻辑对齐旧版固定显示） */
    const renderMetricHeader = (column: IHostColumnConfig) => {
      const iconClass = HOST_METRIC_HEADER_ICON_MAP[column.id];
      return (
        <div class='host-table-metric-header'>
          {iconClass && <i class={['icon-monitor', iconClass, 'host-table-metric-header__agg']} />}
          <span class={['host-table-metric-header__title', HOST_LIST_ELLIPSIS_CELL_CLASS]}>{t(column.name)}</span>
        </div>
      );
    };

    /** 渲染 checkbox 头 */
    const renderCheckboxHeader = () => {
      return (
        <AcrossPageSelection
          class='across-page-selection'
          value={props.selectType}
          onChange={(type: SelectTypeEnum) => {
            emit('headerSelect', type);
          }}
        />
      );
    };

    const renderCheckboxCell = (row: IHostListRow) => {
      return (
        <Checkbox
          modelValue={props.selectedRowKeys.has(String(row.id))}
          onChange={(isChecked: boolean) => emit('rowCheck', row.id, isChecked)}
        />
      );
    };

    /** 构建某一列的 tdesign 配置 */
    const buildColumn = (config: IHostColumnConfig) => {
      let title = () => <span class={HOST_LIST_ELLIPSIS_CELL_CLASS}>{t(config.name)}</span>;
      if (config.type === 'checkbox') {
        title = () => renderCheckboxHeader();
      } else if (config.type === 'metric') {
        title = () => renderMetricHeader(config);
      }
      const base: Record<string, unknown> = {
        colKey: config.id,
        title,
        minWidth: config.minWidth,
        width: config.width,
        sorter: config.sortable,
        ellipsis: false,
        fixed: config.fixed,
      };
      base.cell = (_: unknown, { row }: { row: IHostListRow }) => {
        switch (config.type) {
          case 'ip':
            return renderIpCell(row);
          case 'status':
            return renderStatusCell(row);
          case 'alarm':
            return renderAlarmCell(row);
          case 'metric':
            return renderMetricCell(row, config.id);
          case 'process':
            return renderProcessCell(row);
          case 'cluster':
            return renderEllipsisCell(row.clusterNames);
          case 'module':
            return renderEllipsisCell(row.moduleNames);
          case 'checkbox':
            return renderCheckboxCell(row);
          default:
            return renderEllipsisCell(row[config.id as keyof IHostListRow]);
        }
      };
      return base;
    };

    /** 表格列：选择列 + 展示列 */
    const tableColumns = computed(() => {
      const dataColumns = props.visibleColumns
        .map(id => HOST_LIST_COLUMNS.find(column => column.id === id))
        .filter((column): column is IHostColumnConfig => !!column)
        .map(buildColumn);
      return dataColumns;
      // return [selectionColumn, ...dataColumns];
    });

    const handleSortChange = (sortEvent: TableSort) => {
      const target = Array.isArray(sortEvent) ? sortEvent[0] : sortEvent;
      emit('sortChange', target?.sortBy ? `${target.descending ? '-' : ''}${target.sortBy}` : '');
    };

    return () => (
      <div
        ref='table'
        class='host-list-table'
      >
        <div
          ref='body'
          class={['host-list-table__body', !props.data.length ? 'host-list-table__body--empty' : '']}
        >
          <PrimaryTable
            class={props.data.length === 0 ? 'host-list-table--empty' : ''}
            v-slots={{
              empty: () => (
                <ExploreTableEmpty
                  showOperation={props.emptyType === 'search-empty'}
                  type={props.emptyType}
                  onClearFilter={() => emit('clearFilter')}
                />
              ),
            }}
            firstFullRow={
              props.selectedRowKeys.size
                ? () =>
                    (
                      <HostListSelectionTips
                        selectedCount={props.selectedRowKeys.size}
                        onClearAll={() => emit('headerSelect', SelectType.UN_SELECTED)}
                      />
                    ) as unknown as SlotReturnValue
                : null
            }
            bkUiSettings={tableSettings.value}
            columns={tableColumns.value}
            data={props.data}
            disableDataPage={true}
            hover={true}
            maxHeight={bodyHeight.value}
            needCustomScroll={false}
            reserveSelectedRowOnPaginate={true}
            resizable={true}
            rowKey='id'
            showSortColumnBgColor={true}
            size='small'
            sort={tableSort.value}
            tableLayout='fixed'
            // @ts-expect-error
            onDisplayColumnsChange={(cols: string[]) => emit('columnsChange', cols)}
            onSortChange={handleSortChange}
          />
        </div>
        <Pagination
          class='host-list-table__pagination'
          align='left'
          count={props.total}
          layout={['total', 'limit', 'list']}
          limit={props.pageSize}
          limitList={HOST_LIST_PAGE_SIZE_LIST}
          modelValue={props.page}
          onChange={(v: number) => emit('pageChange', v)}
          onLimitChange={(v: number) => emit('pageSizeChange', v)}
        />
        <div v-show={false}>
          <div ref='tipsContent'>
            <AbnormalTips
              docLink={tipsData.value.docLink}
              linkText={tipsData.value.linkText}
              linkUrl={tipsData.value.linkUrl}
              tipsText={tipsData.value.tipsText}
            />
          </div>
          <div ref='unresolveContent'>
            <UnresolveList list={unresolveList.value} />
          </div>
          <HostListIpStatusTips
            ref={'ipStatusTips'}
            row={ipStatusTipsRow.value}
          />
        </div>
      </div>
    );
  },
});
