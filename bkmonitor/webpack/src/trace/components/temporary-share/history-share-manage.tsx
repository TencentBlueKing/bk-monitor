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
import { computed, defineComponent, onMounted, reactive, ref, shallowRef, watch } from 'vue';

import { DateRange } from '@blueking/date-picker/vue3';
import { PrimaryTable } from '@blueking/tdesign-ui';
import { Button, Checkbox, Dialog, InfoBox, Loading } from 'bkui-vue';
import dayjs from 'dayjs';
import { deleteShareToken, getShareTokenList } from 'monitor-api/modules/share';
import tippy, { type SingleTarget } from 'tippy.js';
import { useI18n } from 'vue-i18n';
import { useRoute } from 'vue-router';

import { useAppStore } from '../../store/modules/app';
import { shortcuts } from '../time-range/utils';
import MiddleOmitted from './middle-omitted';
import { EStatus } from './typings';

import type { INavItem, ITableItem } from './typings';
import type { SortInfo, TableSort, TdPaginationProps } from 'tdesign-vue-next';

import './history-share-manage.scss';
import 'tippy.js/dist/tippy.css';

type TableColumn = Record<string, any>;

const formNowStrFormat = (str: string) =>
  str
    .replace(/years?/g, 'y')
    .replace(/months?/g, 'M')
    .replace(/days?/g, 'd')
    .replace(/hours?/g, 'h')
    .replace(/minutes?/g, 'm')
    .replace(/seconds?/g, 's');

const periodStrFormat = (str: string, t: any) =>
  ['zh', 'zhCN', 'zh-cn', 'zh-CN'].includes(navigator.language)
    ? str
        .replace('m', ` ${t('分钟')}`)
        .replace('h', ` ${t('小时')}`)
        .replace('d', ` ${t('天')}`)
        .replace('w', ` ${t('周')}`)
        .replace('M', ` ${t('月')}`)
        .replace('y', ` ${t('年')}`)
    : str;

const getStatusMap = (t: any) => ({
  [EStatus.isEnabled]: { name: t('正常'), color1: '#3FC06D', color2: 'rgba(63,192,109,0.16)' },
  [EStatus.isExpired]: { name: t('已过期'), color1: '#FF9C01', color2: 'rgba(255,156,1,0.16)' },
  [EStatus.isDeleted]: { name: t('已回收'), color1: '#979BA5', color2: 'rgba(151,155,165,0.16)' },
});

const getStatusList = (t: any) => {
  const statusMap = getStatusMap(t);
  return [
    { id: 'all', name: t('全部') },
    { id: EStatus.isEnabled, ...statusMap[EStatus.isEnabled] },
    { id: EStatus.isExpired, ...statusMap[EStatus.isExpired] },
    { id: EStatus.isDeleted, ...statusMap[EStatus.isDeleted] },
  ];
};

export default defineComponent({
  name: 'HistoryShareManage',
  props: {
    navList: {
      type: Array as () => INavItem[],
      default: () => [],
    },
    pageInfo: {
      type: Object,
      default: () => ({}),
    },
    positionText: String,
    shareUrl: String,
    show: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['showChange'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const route = useRoute();
    const store = useAppStore();

    const pathName = ref('');
    const statusActive = ref('all');
    const urlList = ref<ITableItem[]>([]);
    const tableData = ref<ITableItem[]>([]);
    const tableColumns = shallowRef<TableColumn[]>([
      {
        title: () => (
          <div style='display: flex;'>
            <Checkbox
              v-model={isAll.value}
              indeterminate={isIndeterminate.value}
              onChange={handleSelectAll}
            />
            <span class='ml8'>{t('分享历史')}</span>
          </div>
        ),
        field: t('分享历史'),
        colKey: 'url',
        width: 300,
        cell: (_, { row }) => (
          <div class='url-wrap'>
            <Checkbox
              v-model={row.isCheck}
              disabled={row.status !== EStatus.isEnabled}
              onChange={(v: boolean) => handleSelect(v, row)}
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
      },
      {
        title: t('访问次数'),
        align: 'right',
        colKey: 'accessCount',
        sorter: true,
        cell: (_, { row }) => (
          <span class={['access-count-wrap', { active: row.isShowAccess }]}>
            <span>{row.accessCount}</span>
            <span
              class={['icon-monitor icon-mc-detail']}
              onClick={(event: Event) => handleAccessDetail(event, row)}
            />
          </span>
        ),
      },
      {
        title: t('状态'),
        colKey: 'status',
        cell: (_, { row }) => {
          const statusMap = getStatusMap(t);
          return (
            <span class='status-wrap'>
              {statusPoint(statusMap[row.status].color1, statusMap[row.status].color2)}
              <span>{statusMap[row.status].name}</span>
            </span>
          );
        },
      },
      {
        title: t('产生时间'),
        width: 150,
        colKey: 'create_time',
        sorter: true,
        ellipsis: true,
        cell: (_, { row }) => <span>{dayjs.tz(row.create_time).format('YYYY-MM-DD HH:mm:ss')}</span>,
      },
      {
        title: t('分享人'),
        colKey: 'create_user',
        sorter: true,
        cell: (_, { row }) => row.create_user,
      },
      {
        title: t('链接有效期'),
        colKey: 'expire_time',
        cell: (_, { row }) => <span>{row.expireTimeStr}</span>,
      },
      {
        title: t('操作'),
        colKey: 'operation',
        cell: (_, { row }) => (
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
              onClick={(event: Event) => handleDetail(event, row)}
            >
              {t('变量详情')}
            </Button>
          </div>
        ),
      },
    ]);
    const isIndeterminate = ref(false);
    const isAll = ref(false);
    const pagination: TdPaginationProps = reactive({
      current: 1,
      total: null,
      pageSize: 10,
      pageSizeOptions: [10, 20, 50, 100],
    });
    const popInstance = ref(null);
    const accessDetail = ref([]);
    const variableDetail = ref([
      {
        name: t('时间选择'),
        isUpdate: true,
        timeRange: '2022.01.04 18:00:00 - 2023.01.04 18:00:59',
      },
    ]);
    const shortcutsMap = ref(new Map());
    const tableDataSort = reactive({
      id: '',
      descending: false,
    });
    const selected = ref(new Set());
    const loading = ref(false);
    const typeMap = { 'event-center': 'event', 'incident-detail': 'incident' };
    const accessDetailRef = ref<HTMLDivElement>();
    const variableDetailRef = ref<HTMLDivElement>();

    const STATUS_LIST = computed(() => getStatusList(t));

    const handleHideDialog = () => {
      emit('showChange', false);
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

    const init = async () => {
      loading.value = true;
      const pathFn = (str: string) => (str ? `  /  ${str}` : '');

      if (route.path === '/event-center') {
        pathName.value = `${t('事件中心')}${pathFn(t('事件详情'))}${pathFn(props.pageInfo?.alertName || '')}`;
      } else if (/^\/performance\/detail\/.+$/.test(route.path)) {
        pathName.value = `${t('主机监控')}${pathFn(t('主机详情'))}${pathFn(
          route.query?.['filter-bk_target_ip'] || ''
        )}`;
      } else if (route.path === '/k8s') {
        pathName.value = `${t('Kubernetes')}${pathFn(props.positionText || '')}`;
      } else if (
        /^\/uptime-check\/group-detail\/.+$/.test(route.path) ||
        /^\/uptime-check\/task-detail\/.+$/.test(route.path)
      ) {
        pathName.value = `${t('综合拨测')}${pathFn(t('任务详情'))}${pathFn(props.navList?.[0]?.name || '')}`;
      } else if (/^\/custom-scenes\/view\/.+$/.test(route.path)) {
        pathName.value = `${t('自定义场景')}${pathFn(props.navList?.[0]?.name || '')}${pathFn(
          props.navList?.[0]?.subName || ''
        )}`;
      } else if (/^\/collect-config\/view\/.+$/.test(route.path)) {
        pathName.value = `${t('数据采集')}${pathFn(t('可视化'))}${pathFn(
          props.navList?.[0]?.name || ''
        )}${pathFn(props.navList?.[0]?.subName || '')}`;
      } else if (/^\/custom-escalation-view\/.+$/.test(route.path)) {
        pathName.value = `${t('自定义指标')}${pathFn(t('可视化'))}${pathFn(
          props.navList?.[0]?.name || ''
        )}${pathFn(props.navList?.[0]?.subName || '')}`;
      } else if (/^\/custom-escalation-event-view\/.+$/.test(route.path)) {
        pathName.value = `${t('自定义事件')}${pathFn(t('可视化'))}${pathFn(
          props.navList?.[0]?.name || ''
        )}${pathFn(props.navList?.[0]?.subName || '')}`;
      } else if (/^\/application/.test(route.path) || /^\/apm\/application/.test(route.path)) {
        pathName.value = `APM${pathFn(props.navList?.[1]?.name)}${pathFn(props.positionText || '')}`;
      } else if (/^\/service/.test(route.path) || /^\/apm\/service/.test(route.path)) {
        pathName.value = `APM${pathFn(props.navList?.[1]?.name)}${pathFn(props.navList?.[2]?.name)}${pathFn(
          props.positionText || ''
        )}`;
      }

      const filterParams = {};
      for (const key of Object.keys(route.query)) {
        if (/^filter-.+$/.test(key)) {
          filterParams[key.replace('filter-', '')] = route.query[key];
        }
      }

      const data = await getShareTokenList({
        type: typeMap[route.name as string] ?? route.query.sceneId,
        filter_params: filterParams,
        scene_params: route.query?.dashboardId
          ? {
              sceneType: route.query.sceneType,
              sceneId: route.query.sceneId,
              dashboardId: route.query.dashboardId,
            }
          : undefined,
      }).catch(() => []);

      urlList.value = data.map(item => ({
        ...item,
        link: `${location.origin}${location.pathname}?bizId=${store.bizId}/#/share/${item.token || ''}`,
        accessCount: item.access_info?.total || 0,
        isCheck: false,
        expireTimeStr: item.params_info?.[0]?.expire_period
          ? periodStrFormat(item.params_info?.[0]?.expire_period, t)
          : formNowStrFormat(dayjs.tz(item.create_time).from(dayjs.tz(Number(item.expire_time) * 1000), true)),
      }));

      pagination.total = urlList.value.length;
      setTableData();
      loading.value = false;
    };

    const handleStatusChange = (item: any) => {
      if (statusActive.value !== item.id) {
        statusActive.value = item.id;
        pagination.current = 1;
        setTableData();
      }
    };

    const setTableData = () => {
      const sortFn = (data: ITableItem[]) => {
        if (tableDataSort.id) {
          const isAscending = !tableDataSort.descending;
          const target = [...data];
          target.sort((a: ITableItem, b: ITableItem) => {
            switch (tableDataSort.id) {
              case 'accessCount':
                return isAscending ? a.accessCount - b.accessCount : b.accessCount - a.accessCount;
              case 'create_time': {
                const aTime = dayjs.tz(a.create_time).unix();
                const bTime = dayjs.tz(b.create_time).unix();
                return isAscending ? aTime - bTime : bTime - aTime;
              }
              case 'create_user':
                return isAscending
                  ? a.create_user.localeCompare(b.create_user)
                  : b.create_user.localeCompare(a.create_user);
              default:
                return 0;
            }
          });
          return target;
        }
        return data;
      };

      const filterUrlList =
        statusActive.value === 'all' ? urlList.value : urlList.value.filter(item => item.status === statusActive.value);

      pagination.total = filterUrlList.length;
      const sortedData = sortFn(filterUrlList);
      tableData.value = sortedData.slice(
        (pagination.current - 1) * pagination.pageSize,
        pagination.current * pagination.pageSize
      );
      resetCheckStatus();
    };

    const handlePopoverHidden = () => {
      if (popInstance.value) {
        popInstance.value.hide(0);
        popInstance.value.destroy();
        popInstance.value = null;
      }
    };

    const handleAccessDetail = (event: Event, row: ITableItem) => {
      handlePopoverHidden();
      row.isShowAccess = true;
      accessDetail.value = row.access_info.data.map(item => ({
        user: item.visitor,
        time: dayjs.tz(item.last_time).format('YYYY-MM-DD HH:mm:ss'),
      }));
      handleShowPop(event, accessDetailRef.value);
    };

    const handleDetail = (event: Event, row: ITableItem) => {
      handlePopoverHidden();
      const timeRangeItem = row.params_info.find(item => item.name === 'time_range');
      if (timeRangeItem) {
        const range = timeRangeItem?.default_time_range?.length
          ? timeRangeItem.default_time_range
          : [timeRangeItem.start_time * 1000, timeRangeItem.end_time * 1000];
        const timeRangeStr =
          shortcutsMap.value.get(range.join(' -- ')) ||
          new DateRange(range, 'YYYY-MM-DD HH:mm:ss', window.timezone).toDisplayString();
        variableDetail.value = [
          {
            name: t('时间选择'),
            isUpdate: !timeRangeItem.lock_search,
            timeRange: timeRangeStr,
          },
        ];
      }
      handleShowPop(event, variableDetailRef.value, true, true);
    };

    const handleRecycle = (row: ITableItem) => {
      const tempSet = new Set([row.token]);
      commonRecycle(tempSet);
    };

    const handleBatchRecycle = () => {
      const tempSet = new Set(tableData.value.filter(item => item.isCheck).map(item => item.token));
      commonRecycle(tempSet, t('确定回收所选分享链接'));
    };

    const commonRecycle = (tokensSet: Set<string>, title = t('确定回收当前分享链接')) => {
      const type = typeMap[route.name as string] ?? route.query.sceneId;
      InfoBox({
        title,
        confirmText: t('回收'),
        cancelText: t('取消'),
        onConfirm: async () => {
          const res = await deleteShareToken({
            tokens: Array.from(tokensSet),
            type,
          }).catch(() => false);

          if (res || res === 0) {
            for (const item of urlList.value) {
              if (tokensSet.has(item.token)) {
                item.status = EStatus.isDeleted;
                item.isCheck = false;
              }
            }
            for (const item of tableData.value) {
              if (tokensSet.has(item.token)) {
                item.status = EStatus.isDeleted;
                item.isCheck = false;
              }
            }
            isIndeterminate.value = false;
            isAll.value = false;
          }
          return !!res;
        },
      });
    };

    const resetCheckStatus = () => {
      for (const item of urlList.value) {
        item.isCheck = false;
      }
      for (const item of tableData.value) {
        item.isCheck = false;
      }
      isAll.value = false;
      isIndeterminate.value = false;
      selected.value = new Set();
    };

    const handleToLink = (row: ITableItem) => {
      window.open(row.link);
    };

    const handlePageChange = (pageInfo: { current: number; pageSize: number }) => {
      pagination.current = pageInfo.current;
      pagination.pageSize = pageInfo.pageSize;
      setTableData();
    };

    const handleSortChange = (order: TableSort) => {
      const { sortBy, descending } = (order as SortInfo) || {};

      tableDataSort.id = sortBy || '';
      tableDataSort.descending = descending;
      setTableData();
    };

    const handleAccessDataSortChange = (order: TableSort) => {
      const { sortBy, descending } = (order as SortInfo) || {};

      if (sortBy) {
        accessDetail.value.sort((a, b) => {
          switch (sortBy) {
            case 'user':
              return descending ? b.user.localeCompare(a.user) : a.user.localeCompare(b.user);
            case 'time': {
              const aTime = dayjs.tz(a.time).unix();
              const bTime = dayjs.tz(b.time).unix();
              return descending ? bTime - aTime : aTime - bTime;
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
      const tempSet = new Set();
      for (const item of tableData.value) {
        if (v) {
          if (item.status === EStatus.isEnabled) {
            item.isCheck = v;
            tempSet.add(item.token);
          }
        } else {
          item.isCheck = v;
        }
      }
      selected.value = tempSet;
      isIndeterminate.value = false;
    };

    const handleSelect = (v: boolean, row: ITableItem) => {
      row.isCheck = v;
      const tempSet = new Set(tableData.value.filter(item => item.isCheck).map(item => item.token));
      selected.value = tempSet;
      const len = tempSet.size;
      isIndeterminate.value = len > 0 && len < tableData.value.length;
      isAll.value = len === tableData.value.length;
    };

    const handleShowPop = (event: Event, el: HTMLElement, isBottomEnd = false, isVariablePop = false) => {
      popInstance.value = tippy(event.target as SingleTarget, {
        content: el,
        trigger: 'click',
        theme: 'light',
        placement: isBottomEnd ? 'bottom-end' : 'bottom-start',
        appendTo: document.body,
        sticky: 'reference',
        interactive: true,
        arrow: true,
        maxWidth: isVariablePop ? 500 : 318,
        onHidden: () => {
          for (const t of tableData.value) {
            t.isShowAccess = false;
          }
        },
      });
      popInstance.value?.show?.();
    };

    onMounted(() => {
      shortcutsMap.value = shortcuts.reduce((map, cur) => {
        map.set(cur.value.join(' -- '), cur.text);
        return map;
      }, new Map());
    });

    watch(
      () => props.show,
      v => {
        if (v) {
          init();
        }
      },
      { immediate: true }
    );

    return {
      pathName,
      statusActive,
      tableData,
      tableColumns,
      pagination,
      accessDetail,
      accessDetailRef,
      variableDetail,
      variableDetailRef,
      selected,
      loading,
      STATUS_LIST,
      statusPoint,
      handleHideDialog,
      handleStatusChange,
      handleBatchRecycle,
      handlePageChange,
      handleSortChange,
      handleAccessDataSortChange,
      t,
    };
  },
  render() {
    return (
      <Dialog
        width={1280}
        class='history-share-manage'
        isShow={this.show}
        title={this.t('管理历史分享')}
        transfer={true}
        onClosed={this.handleHideDialog}
      >
        <Loading
          class='history-share-manage-wrap'
          loading={this.loading}
        >
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
              disabled={!this.selected.size}
              theme='primary'
              onClick={this.handleBatchRecycle}
            >
              {this.t('批量回收')}
            </Button>
            <div class='status-list'>
              {this.STATUS_LIST.map((item: any, index) => (
                <div
                  key={item.id}
                  class={[
                    'status-list-item',
                    { active: this.statusActive === item.id },
                    {
                      'not-border':
                        this.statusActive === item.id || this.STATUS_LIST[index + 1]?.id === this.statusActive,
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
          <PrimaryTable
            key='main-table'
            class='url-table-wrap'
            bkUiSettings={{
              fields: this.tableColumns.map(item => {
                return {
                  label: typeof item.title === 'string' ? item.title : item.field,
                  field: item.colKey,
                  disabled: item.colKey === 'operation',
                };
              }),
              checked: this.tableColumns.map(item => item.colKey),
            }}
            columns={this.tableColumns}
            data={this.tableData}
            hideSortTips={true}
            hover={true}
            maxHeight={536}
            pagination={this.pagination}
            rowKey='token'
            onPageChange={this.handlePageChange}
            onSortChange={this.handleSortChange}
          />
        </Loading>
        <div style='display: none'>
          <div
            ref='accessDetailRef'
            class='history-share-manage-access-count-detail'
          >
            <PrimaryTable
              columns={[
                {
                  title: this.t('访问人'),
                  colKey: 'user',
                  sorter: true,
                },
                {
                  title: this.t('访问时间'),
                  colKey: 'time',
                  sorter: true,
                },
              ]}
              data={this.accessDetail}
              hideSortTips={true}
              max-height={364}
              stripe
              onSortChange={this.handleAccessDataSortChange}
            />
          </div>
          <div
            ref='variableDetailRef'
            class='history-share-manage-variable-detail'
          >
            <PrimaryTable
              columns={[
                {
                  title: this.t('变量名称'),
                  colKey: 'name',
                },
                {
                  title: this.t('是否可更改'),
                  colKey: 'isUpdate',
                  width: 96,
                  cell: (_, { row }) => <span>{this.t(row.isUpdate ? '是' : '否')}</span>,
                },
                {
                  title: this.t('默认选项'),
                  colKey: 'timeRange',
                  width: 280,
                },
              ]}
              data={this.variableDetail}
            />
          </div>
        </div>
      </Dialog>
    );
  },
});
