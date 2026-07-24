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
  ref as deepRef,
  shallowRef,
  useTemplateRef,
  watch,
} from 'vue';

import { DateRange } from '@blueking/date-picker';
import { type BkUiSettings, type TableSort, PrimaryTable } from '@blueking/tdesign-ui';
import { bkTooltips, Button, Checkbox, Dialog, InfoBox, Loading, Pagination } from 'bkui-vue';
import dayjs from 'dayjs';
import { deleteShareToken, getShareTokenList } from 'monitor-api/modules/share';
import tippy, { type Instance, type SingleTarget } from 'tippy.js';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import MiddleOmitted from './middle-omitted';
import { shortcuts } from '@/components/time-range/utils';
import { useAppStore } from '@/store/modules/app';

import type { INavItem } from '@/components/nav-bar/type';

import './history-share-manage.scss';

const getNextZIndex = () => (window as any).__bk_zIndex_manager?.nextZIndex?.() || 2000;

const formNowStrFormat = (str: string) =>
  str
    .replace(/years?/g, 'y')
    .replace(/months?/g, 'M')
    .replace(/days?/g, 'd')
    .replace(/hours?/g, 'h')
    .replace(/minutes?/g, 'm')
    .replace(/seconds?/g, 's');

/** 如 1w 代表一周 m 分钟 h 小时 d 天 w 周 M 月 y 年 */
const periodStrFormat = (str: string) =>
  ['zh', 'zhCN', 'zh-cn'].includes(window.i18n.locale)
    ? str
        .replace('m', ` ${window.i18n.t('分钟')}`)
        .replace('h', ` ${window.i18n.t('小时')}`)
        .replace('d', ` ${window.i18n.t('天')}`)
        .replace('w', ` ${window.i18n.t('周')}`)
        .replace('M', ` ${window.i18n.t('月')}`)
        .replace('y', ` ${window.i18n.t('年')}`)
    : str;

enum EStatus {
  isDeleted = 'is_deleted',
  isEnabled = 'is_enabled',
  isExpired = 'is_expired',
}

const statusMap = {
  [EStatus.isEnabled]: { name: window.i18n.t('正常'), color1: '#3FC06D', color2: 'rgba(63,192,109,0.16)' },
  [EStatus.isExpired]: { name: window.i18n.t('已过期'), color1: '#FF9C01', color2: 'rgba(255,156,1,0.16)' },
  [EStatus.isDeleted]: { name: window.i18n.t('已回收'), color1: '#979BA5', color2: 'rgba(151,155,165,0.16)' },
};

interface ITableItem {
  accessCount: number;
  create_time: string;
  create_user: string;
  expire_time: number;
  expireTimeStr: string;
  isCheck?: boolean;
  isShowAccess: boolean;
  link: string;
  status: EStatus;
  token: string;
  access_info: {
    data: { last_time: number; visitor: string }[];
    total: number;
  };
  params_info: {
    default_time_range?: string[];
    end_time: number;
    expire_period?: string;
    lock_search: boolean;
    name: string;
    start_time: number;
  }[];
}

interface IAccessItem {
  time: string;
  user: string;
}

interface IVariableItem {
  isUpdate: boolean;
  name: string;
  timeRange: string;
}

export default defineComponent({
  name: 'HistoryShareManage',
  directives: {
    bkTooltips,
  },
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    shareUrl: {
      type: String,
      default: '',
    },
    pageInfo: {
      type: Object as PropType<Record<string, any>>,
      default: () => ({}),
    },
    positionText: {
      type: String,
      default: '',
    },
    navList: {
      type: Array as PropType<INavItem[]>,
      default: () => [],
    },
    /** 分享类型，优先于路由推导 */
    shareType: {
      type: String,
      default: '',
    },
  },
  emits: {
    showChange: (_v: boolean) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const route = useRoute();
    const store = useAppStore();

    const accessDetailRef = useTemplateRef<HTMLElement>('accessDetail');
    const variableDetailRef = useTemplateRef<HTMLElement>('variableDetail');

    const zIndex = shallowRef(getNextZIndex());
    const pathName = shallowRef('');
    const statusActive = shallowRef('all');
    const loading = shallowRef(false);
    const isIndeterminate = shallowRef(false);
    const isAll = shallowRef(false);
    const selected = deepRef<Set<string>>(new Set());

    const urlList = deepRef<ITableItem[]>([]);
    const tableData = deepRef<ITableItem[]>([]);
    const accessDetail = deepRef<IAccessItem[]>([]);
    const variableDetail = deepRef<IVariableItem[]>([{ name: t('时间选择') as string, isUpdate: true, timeRange: '' }]);

    const pagination = deepRef({
      current: 1,
      count: 0,
      limit: 10,
    });

    const tableDataSort = deepRef<{ id: string; order: string }>({
      id: '',
      order: '',
    });

    const tableColumns = deepRef([
      { id: 'url', name: t('分享历史') as string, checked: true, disabled: true },
      { id: 'accessCount', name: t('访问次数') as string, checked: true, disabled: false },
      { id: 'status', name: t('状态') as string, checked: true, disabled: false },
      { id: 'create_time', name: t('产生时间') as string, checked: true, disabled: false },
      { id: 'create_user', name: t('分享人') as string, checked: true, disabled: false },
      { id: 'sort', name: t('链接有效期') as string, checked: true, disabled: false },
    ]);

    const statusList = [
      { id: 'all', name: t('全部') as string },
      { id: EStatus.isEnabled, ...statusMap[EStatus.isEnabled] },
      { id: EStatus.isExpired, ...statusMap[EStatus.isExpired] },
      { id: EStatus.isDeleted, ...statusMap[EStatus.isDeleted] },
    ];

    const shortcutsMap = shortcuts.reduce((map, cur) => {
      map.set(cur.value.join(' -- '), cur.text);
      return map;
    }, new Map());

    const typeMap: Record<string, string> = {
      'event-center': 'event',
      'incident-detail': 'incident',
    };

    let popInstance: Instance | null = null;

    const tableSettings = computed<BkUiSettings>(() => ({
      fields: tableColumns.value.map(item => ({
        label: item.name,
        field: item.id,
        disabled: item.disabled,
      })),
      checked: tableColumns.value.filter(item => item.checked || item.disabled).map(item => item.id),
    }));

    const tableSort = computed<TableSort>(() => {
      if (!tableDataSort.value.id || !tableDataSort.value.order) return [];
      return [
        {
          sortBy: tableDataSort.value.id,
          descending: tableDataSort.value.order === 'desc',
        },
      ];
    });

    const resolveShareType = () =>
      props.shareType || typeMap[String(route.name)] || (route.query.sceneId as string) || 'host';

    const destroyPopover = () => {
      popInstance?.hide();
      popInstance?.destroy();
      popInstance = null;
    };

    onBeforeUnmount(() => {
      destroyPopover();
    });

    const handleHideDialog = () => {
      emit('showChange', false);
    };

    const init = async () => {
      loading.value = true;
      const { query, path } = route;
      const pathFn = (str: string) => {
        if (str) {
          return `  /  ${str}`;
        }
        return '';
      };

      if (path === '/event-center') {
        pathName.value = `${t('事件中心')}${pathFn(t('事件详情') as string)}${pathFn(props.pageInfo?.alertName || '')}`;
      } else if (/^\/performance\/detail\/.+$/.test(path) || /^\/host/.test(path)) {
        pathName.value = `${t('主机监控')}${pathFn(t('主机详情') as string)}${pathFn(
          (query?.['filter-bk_target_ip'] as string) || props.positionText || ''
        )}`;
      } else if (path === '/k8s') {
        pathName.value = `${t('Kubernetes')}${pathFn(props.positionText || '')}`;
      } else if (/^\/uptime-check\/group-detail\/.+$/.test(path) || /^\/uptime-check\/task-detail\/.+$/.test(path)) {
        pathName.value = `${t('综合拨测')}${pathFn(t('任务详情') as string)}${pathFn(String(props.navList?.[0]?.name || ''))}`;
      } else if (/^\/collect-config\/view\/.+$/.test(path)) {
        pathName.value = `${t('数据采集')}${pathFn(t('可视化') as string)}${pathFn(
          String(props.navList?.[0]?.name || '')
        )}${pathFn(String(props.navList?.[0]?.subName || ''))}`;
      } else if (/^\/custom-escalation-view\/.+$/.test(path)) {
        pathName.value = `${t('自定义指标')}${pathFn(t('可视化') as string)}${pathFn(
          String(props.navList?.[0]?.name || '')
        )}${pathFn(String(props.navList?.[0]?.subName || ''))}`;
      } else if (/^\/custom-escalation-event-view\/.+$/.test(path)) {
        pathName.value = `${t('自定义事件')}${pathFn(t('可视化') as string)}${pathFn(
          String(props.navList?.[0]?.name || '')
        )}${pathFn(String(props.navList?.[0]?.subName || ''))}`;
      } else if (/^\/application/.test(path) || /^\/apm\/application/.test(path)) {
        pathName.value = `APM${pathFn(String(props.navList?.[1]?.name || ''))}${pathFn(props.positionText || '')}`;
      } else if (/^\/service/.test(path) || /^\/apm\/service/.test(path)) {
        pathName.value = `APM${pathFn(String(props.navList?.[1]?.name || ''))}${pathFn(
          String(props.navList?.[2]?.name || '')
        )}${pathFn(props.positionText || '')}`;
      } else {
        pathName.value = props.positionText || path;
      }

      const filterParams: Record<string, any> = {};
      Object.keys(query).forEach(key => {
        if (/^filter-.+$/.test(key)) {
          filterParams[key.replace('filter-', '')] = query[key];
        }
      });

      const data = await getShareTokenList({
        type: resolveShareType(),
        filter_params: filterParams,
        scene_params: query?.dashboardId
          ? { sceneType: query.sceneType, sceneId: query.sceneId, dashboardId: query.dashboardId }
          : undefined,
      }).catch(() => []);

      urlList.value = data.map(item => ({
        ...item,
        link: `${location.origin}${location.pathname}?bizId=${store.bizId}/#/share/${item.token || ''}`,
        accessCount: item.access_info?.total || 0,
        isCheck: false,
        isShowAccess: false,
        expireTimeStr: item.params_info?.[0]?.expire_period
          ? periodStrFormat(item.params_info?.[0]?.expire_period)
          : formNowStrFormat(dayjs.tz(item.create_time).from(dayjs.tz(Number(item.expire_time) * 1000), true)),
      }));
      pagination.value.count = urlList.value.length;
      const { current, limit } = pagination.value;
      tableData.value = urlList.value.slice((current - 1) * limit, current * limit);
      loading.value = false;
    };

    watch(
      () => props.show,
      v => {
        if (v) {
          zIndex.value = getNextZIndex();
          init();
        }
      },
      { immediate: true }
    );

    const resetCheckStatus = () => {
      urlList.value.forEach(item => {
        item.isCheck = false;
      });
      tableData.value.forEach(item => {
        item.isCheck = false;
      });
      isAll.value = false;
      isIndeterminate.value = false;
      selected.value = new Set();
    };

    const setTableData = () => {
      const sortFn = (list: ITableItem[]) => {
        if (tableDataSort.value.id) {
          const isAscending = tableDataSort.value.order === 'asc';
          const target = JSON.parse(JSON.stringify(list)) as ITableItem[];
          target.sort((a, b) => {
            switch (tableDataSort.value.id) {
              case 'accessCount': {
                return isAscending ? a.accessCount - b.accessCount : b.accessCount - a.accessCount;
              }
              case 'create_time': {
                const aTime = dayjs.tz(a.create_time).unix();
                const bTime = dayjs.tz(b.create_time).unix();
                return isAscending ? aTime - bTime : bTime - aTime;
              }
              case 'create_user': {
                return isAscending
                  ? a.create_user.localeCompare(b.create_user)
                  : b.create_user.localeCompare(a.create_user);
              }
              default:
                return 0;
            }
          });
          return target;
        }
        return list;
      };

      const filterUrlList =
        statusActive.value === 'all' ? urlList.value : urlList.value.filter(item => item.status === statusActive.value);
      pagination.value.count = filterUrlList.length;
      const { current, limit } = pagination.value;
      tableData.value = sortFn(filterUrlList).slice((current - 1) * limit, current * limit);
      resetCheckStatus();
    };

    const handleStatusChange = (item: { id: string }) => {
      if (statusActive.value !== item.id) {
        statusActive.value = item.id;
        pagination.value.current = 1;
        setTableData();
      }
    };

    const handleShowPop = async (event: MouseEvent, el: HTMLElement | null, placement: any = 'bottom-start') => {
      if (!el) return;
      destroyPopover();
      await nextTick();
      popInstance = tippy(event.currentTarget as SingleTarget, {
        content: el,
        trigger: 'click',
        theme: 'light',
        placement,
        interactive: true,
        arrow: true,
        appendTo: () => document.body,
        onHidden: () => {
          tableData.value.forEach(row => {
            row.isShowAccess = false;
          });
        },
      });
      popInstance.show();
    };

    const handleAccessDetail = async (event: MouseEvent, row: ITableItem) => {
      destroyPopover();
      row.isShowAccess = true;
      accessDetail.value = (row.access_info?.data || []).map(item => ({
        user: item.visitor,
        time: dayjs.tz(item.last_time).format('YYYY-MM-DD HH:mm:ssZZ'),
      }));
      await nextTick();
      handleShowPop(event, accessDetailRef.value);
    };

    const handleDetail = async (event: MouseEvent, row: ITableItem) => {
      destroyPopover();
      const timeRangeItem = row.params_info?.find(item => item.name === 'time_range');
      if (timeRangeItem) {
        const range = timeRangeItem?.default_time_range?.length
          ? timeRangeItem.default_time_range
          : [timeRangeItem.start_time * 1000, timeRangeItem.end_time * 1000];
        const timeRangeStr =
          shortcutsMap.get(range.join(' -- ')) ||
          new DateRange(range as any, 'YYYY-MM-DD HH:mm:ssZZ', window.timezone).toDisplayString();
        variableDetail.value = [
          { name: t('时间选择') as string, isUpdate: !timeRangeItem.lock_search, timeRange: timeRangeStr },
        ];
      }
      await nextTick();
      handleShowPop(event, variableDetailRef.value, 'bottom-end');
    };

    const commonRecycle = (tokensSet: Set<string>, title = t('确定回收当前分享链接')) => {
      InfoBox({
        title,
        confirmText: t('回收'),
        cancelText: t('取消'),
        onConfirm: async () => {
          const res = await deleteShareToken({ tokens: Array.from(tokensSet), type: resolveShareType() }).catch(
            () => false
          );
          if (res || res === 0) {
            urlList.value.forEach(item => {
              if (tokensSet.has(item.token)) {
                item.status = EStatus.isDeleted;
                item.isCheck = false;
              }
            });
            tableData.value.forEach(item => {
              if (tokensSet.has(item.token)) {
                item.status = EStatus.isDeleted;
                item.isCheck = false;
              }
            });
            isIndeterminate.value = false;
            isAll.value = false;
            selected.value = new Set();
          }
          return !!res;
        },
      });
    };

    const handleRecycle = (row: ITableItem) => {
      const tempSet = new Set<string>();
      tempSet.add(row.token);
      commonRecycle(tempSet);
    };

    const handleBatchRecycle = () => {
      const tempSet = new Set<string>();
      tableData.value.forEach(item => {
        if (item.isCheck) {
          tempSet.add(item.token);
        }
      });
      commonRecycle(tempSet, t('确定回收所选分享链接'));
    };

    const handleToLink = (row: ITableItem) => {
      window.open(row.link);
    };

    const handlePageChange = (newPage: number) => {
      pagination.value.current = newPage;
      setTableData();
    };

    const handlePageLimitChange = (limit: number) => {
      pagination.value.current = 1;
      pagination.value.limit = limit;
      setTableData();
    };

    const handleSortChange = (sortEvent: TableSort) => {
      const target = Array.isArray(sortEvent) ? sortEvent[0] : sortEvent;
      tableDataSort.value = {
        id: target?.sortBy || '',
        order: target?.sortBy ? (target.descending ? 'desc' : 'asc') : '',
      };
      setTableData();
    };

    const handleAccessDataSortChange = (sortEvent: TableSort) => {
      const target = Array.isArray(sortEvent) ? sortEvent[0] : sortEvent;
      if (target?.sortBy) {
        const isAscending = !target.descending;
        accessDetail.value.sort((a, b) => {
          switch (target.sortBy) {
            case 'user': {
              return isAscending ? a.user.localeCompare(b.user) : b.user.localeCompare(a.user);
            }
            case 'time': {
              const aTime = dayjs.tz(a.time).unix();
              const bTime = dayjs.tz(b.time).unix();
              return isAscending ? aTime - bTime : bTime - aTime;
            }
            default:
              return 0;
          }
        });
      } else {
        accessDetail.value.sort((a, b) => {
          const aTime = dayjs.tz(a.time).unix();
          const bTime = dayjs.tz(b.time).unix();
          return bTime - aTime;
        });
      }
    };

    const handleSelectAll = (v: boolean) => {
      const tempSet = new Set<string>();
      tableData.value.forEach(item => {
        if (v) {
          if (item.status === EStatus.isEnabled) {
            item.isCheck = true;
            tempSet.add(item.token);
          }
        } else {
          item.isCheck = false;
        }
      });
      selected.value = tempSet;
      isAll.value = v && tempSet.size > 0;
      isIndeterminate.value = false;
    };

    const handleSelect = (v: boolean, row: ITableItem) => {
      row.isCheck = v;
      const tempSet = new Set<string>();
      tableData.value.forEach(item => {
        if (item.isCheck) {
          tempSet.add(item.token);
        }
      });
      selected.value = tempSet;
      const len = tempSet.size;
      const enabledLen = tableData.value.filter(item => item.status === EStatus.isEnabled).length;
      isIndeterminate.value = len > 0 && len < enabledLen;
      isAll.value = enabledLen > 0 && len === enabledLen;
    };

    const handleSettingChange = (cols: string[]) => {
      tableColumns.value.forEach(item => {
        item.checked = cols.includes(item.id) || item.disabled;
      });
    };

    const statusPoint = (color1: string, color2: string) => (
      <div
        style={{ background: color2 }}
        class='status-point'
      >
        <div
          style={{ background: color1 }}
          class='point'
        />
      </div>
    );

    const primaryColumns = computed(() => {
      const checkedColumns = tableColumns.value.filter(item => item.checked);
      const cols = checkedColumns.map(item => {
        switch (item.id) {
          case 'url':
            return {
              colKey: 'url',
              width: 300,
              title: () => (
                <div style='display: flex; align-items: center;'>
                  <Checkbox
                    indeterminate={isIndeterminate.value}
                    modelValue={isAll.value}
                    onChange={handleSelectAll}
                  />
                  <span class='ml8'>{item.name}</span>
                </div>
              ),
              cell: (_: unknown, { row }: { row: ITableItem }) => (
                <div class='url-wrap'>
                  <Checkbox
                    disabled={row.status !== EStatus.isEnabled}
                    modelValue={row.isCheck}
                    onChange={v => handleSelect(v, row)}
                  />
                  <MiddleOmitted
                    v-bk-tooltips={{
                      content: row.link,
                      placements: ['top'],
                      duration: [300, 20],
                      allowHTML: false,
                    }}
                    click={() => handleToLink(row)}
                    lengthNum={row.token.length + 1}
                    value={row.link}
                  />
                </div>
              ),
            };
          case 'accessCount':
            return {
              colKey: 'accessCount',
              title: item.name,
              align: 'right' as const,
              sorter: true,
              cell: (_: unknown, { row }: { row: ITableItem }) => (
                <span class={['access-count-wrap', { active: row.isShowAccess }]}>
                  <span>{row.accessCount}</span>
                  <span
                    class='icon-monitor icon-mc-detail'
                    onClick={event => handleAccessDetail(event, row)}
                  />
                </span>
              ),
            };
          case 'status':
            return {
              colKey: 'status',
              title: t('状态'),
              cell: (_: unknown, { row }: { row: ITableItem }) => (
                <span class='status-wrap'>
                  {statusPoint(statusMap[row.status].color1, statusMap[row.status].color2)}
                  <span>{statusMap[row.status].name}</span>
                </span>
              ),
            };
          case 'create_time':
            return {
              colKey: 'create_time',
              title: t('产生时间'),
              width: 150,
              sorter: true,
              ellipsis: true,
              cell: (_: unknown, { row }: { row: ITableItem }) => (
                <span>{dayjs.tz(row.create_time).format('YYYY-MM-DD HH:mm:ssZZ')}</span>
              ),
            };
          case 'create_user':
            return {
              colKey: 'create_user',
              title: t('分享人'),
              sorter: true,
            };
          case 'sort':
            return {
              // colKey 需与 tableSettings.checked / fields.field（id: 'sort'）一致，否则受控列设置会隐藏该列
              colKey: 'sort',
              title: t('链接有效期'),
              cell: (_: unknown, { row }: { row: ITableItem }) => <span>{row.expireTimeStr}</span>,
            };
          default:
            return {
              colKey: item.id,
              title: item.name,
            };
        }
      });

      cols.push({
        // 使用内置操作列 key，始终显示且不出现在列设置面板
        colKey: 'row-operation',
        title: t('操作'),
        cell: (_: unknown, { row }: { row: ITableItem }) => (
          <div>
            <Button
              class='mr16'
              disabled={row.status !== EStatus.isEnabled}
              theme='primary'
              text
              onClick={() => handleRecycle(row)}
            >
              {t('回收')}
            </Button>
            <Button
              theme='primary'
              text
              onClick={event => handleDetail(event, row)}
            >
              {t('变量详情')}
            </Button>
          </div>
        ),
      });
      return cols;
    });

    const accessColumns = [
      { colKey: 'user', title: t('访问人'), sorter: true },
      { colKey: 'time', title: t('访问时间'), sorter: true },
    ];

    const variableColumns = [
      { colKey: 'name', title: t('变量名称') },
      {
        colKey: 'isUpdate',
        title: t('是否可更改'),
        cell: (_: unknown, { row }: { row: IVariableItem }) => <span>{t(row.isUpdate ? '是' : '否')}</span>,
      },
      { colKey: 'timeRange', title: t('默认选项'), width: 280 },
    ];

    return {
      t,
      zIndex,
      pathName,
      statusActive,
      loading,
      isIndeterminate,
      isAll,
      selected,
      tableData,
      accessDetail,
      variableDetail,
      pagination,
      statusList,
      tableSettings,
      tableSort,
      primaryColumns,
      accessColumns,
      variableColumns,
      handleHideDialog,
      handleStatusChange,
      handleBatchRecycle,
      handlePageChange,
      handlePageLimitChange,
      handleSortChange,
      handleAccessDataSortChange,
      handleSettingChange,
      statusPoint,
    };
  },
  render() {
    return (
      <Dialog
        width={1280}
        class='history-share-manage'
        dialogType='show'
        isShow={this.show}
        title={this.t('管理历史分享') as string}
        transfer={true}
        zIndex={this.zIndex}
        onClosed={this.handleHideDialog}
      >
        <Loading loading={this.loading}>
          <div class='history-share-manage-wrap'>
            <span class='top-info'>
              <span class='info-item'>
                <span class='title'>{this.t('页面路径')}:</span>
                <span
                  class='content path'
                  title={this.pathName}
                >
                  {this.pathName}
                </span>
              </span>
              <span class='info-item'>
                <span class='title'>{this.t('本次分享URL')}:</span>
                <span class='content link'>
                  <a
                    href={this.shareUrl}
                    rel='noopener noreferrer'
                    target='_blank'
                  >
                    {this.shareUrl}
                  </a>
                </span>
              </span>
            </span>
            <div class='opreate-wrap'>
              <Button
                class='mr18'
                disabled={!Array.from(this.selected).length}
                theme='primary'
                onClick={this.handleBatchRecycle}
              >
                {this.t('批量回收')}
              </Button>
              <div class='status-list'>
                {this.statusList.map((item: any, index: number) => (
                  <div
                    key={item.id}
                    class={[
                      'status-list-item',
                      { active: this.statusActive === item.id },
                      {
                        'not-border':
                          this.statusActive === item.id || this.statusList[index + 1]?.id === this.statusActive,
                      },
                    ]}
                    onClick={() => this.handleStatusChange(item)}
                  >
                    {index !== 0 && this.statusPoint(item.color1, item.color2)}
                    <span>{item.name}</span>
                  </div>
                ))}
              </div>
            </div>
            <div class='url-table-wrap'>
              <PrimaryTable
                bkUiSettings={this.tableSettings}
                columns={this.primaryColumns as any}
                data={this.tableData}
                maxHeight={536}
                rowKey='token'
                size='small'
                sort={this.tableSort}
                onDisplayColumnsChange={this.handleSettingChange}
                onSortChange={this.handleSortChange}
              />
              <Pagination
                class='history-share-pagination'
                align='right'
                count={this.pagination.count}
                layout={['total', 'limit', 'list']}
                limit={this.pagination.limit}
                modelValue={this.pagination.current}
                onChange={this.handlePageChange}
                onLimitChange={this.handlePageLimitChange}
              />
            </div>
          </div>
        </Loading>
        <div v-show={false}>
          <div
            ref='accessDetail'
            class='history-share-manage-access-count-detail'
          >
            <PrimaryTable
              columns={this.accessColumns as any}
              data={this.accessDetail}
              maxHeight={364}
              rowKey='time'
              size='small'
              stripe
              onSortChange={this.handleAccessDataSortChange}
            />
          </div>
          <div
            ref='variableDetail'
            class='history-share-manage-variable-detail'
          >
            <PrimaryTable
              columns={this.variableColumns as any}
              data={this.variableDetail}
              rowKey='name'
              size='small'
            />
          </div>
        </div>
      </Dialog>
    );
  },
});
