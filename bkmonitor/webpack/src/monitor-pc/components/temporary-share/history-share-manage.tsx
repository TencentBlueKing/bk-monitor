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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { DateRange } from '@blueking/date-picker/dist/vue2-light.es';
import dayjs from 'dayjs';

import { INavItem } from '@/pages/monitor-k8s/typings';

import { deleteShareToken, getShareTokenList } from '../../../monitor-api/modules/share';
import MonitorDialog from '../../../monitor-ui/monitor-dialog';
import { shortcuts } from '../time-range/utils';

import MiddleOmitted from './middle-omitted';

import './history-share-manage.scss';

const formNowStrFormat = (str: string) =>
  str
    .replace(/years?/g, 'y')
    .replace(/months?/g, 'M')
    .replace(/days?/g, 'd')
    .replace(/hours?/g, 'h')
    .replace(/minutes?/g, 'm')
    .replace(/seconds?/g, 's');

//  如 1w 代表一周 m 分钟 h 小时 d 天 w 周 M 月 y 年
const periodStrFormat = (str: string) =>
  ['zh', 'zhCN', 'zh-cn'].includes(window.i18n.locale)
    ? str
        .replace('m', ` ${window.i18n.tc('分钟')}`)
        .replace('h', ` ${window.i18n.tc('小时')}`)
        .replace('d', ` ${window.i18n.tc('天')}`)
        .replace('w', ` ${window.i18n.tc('周')}`)
        .replace('M', ` ${window.i18n.tc('月')}`)
        .replace('y', ` ${window.i18n.tc('年')}`)
    : str;

enum EStatus {
  isEnabled = 'is_enabled',
  isExpired = 'is_expired',
  isDeleted = 'is_deleted'
}

const statusMap = {
  [EStatus.isEnabled]: { name: window.i18n.tc('正常'), color1: '#3FC06D', color2: 'rgba(63,192,109,0.16)' },
  [EStatus.isExpired]: { name: window.i18n.tc('已过期'), color1: '#FF9C01', color2: 'rgba(255,156,1,0.16)' },
  [EStatus.isDeleted]: { name: window.i18n.tc('已回收'), color1: '#979BA5', color2: 'rgba(151,155,165,0.16)' }
};

export const STATUS_LIST = [
  { id: 'all', name: window.i18n.tc('全部') },
  { id: EStatus.isEnabled, ...statusMap[EStatus.isEnabled] },
  { id: EStatus.isExpired, ...statusMap[EStatus.isExpired] },
  { id: EStatus.isDeleted, ...statusMap[EStatus.isDeleted] }
];

interface ITableItem {
  isCheck?: boolean;
  link: string;
  accessCount: number;
  status: EStatus;
  create_time: string;
  create_user: string;
  expire_time: number;
  isShowAccess: boolean;
  token: string;
  params_info: {
    name: string;
    lock_search: boolean;
    default_time_range?: string[];
    end_time: number;
    start_time: number;
    expire_period?: string;
  }[];
  access_info: {
    total: number;
    data: { visitor: string; last_time: number }[];
  };
  expireTimeStr: string;
}
interface IProps {
  show?: boolean;
  shareUrl?: string;
  pageInfo?: Record<string, any>;
  positionText?: string;
  navList?: INavItem[];
  onShowChange?: (v: boolean) => void;
}

@Component
export default class HistoryShareManage extends tsc<IProps> {
  @Prop({ default: false, type: Boolean }) show: boolean; // 是否显示
  @Prop({ default: '', type: String }) shareUrl: string; // 分享链接
  @Prop({ type: Object, default: () => ({}) }) pageInfo: Record<string, any>; // 页面信息
  @Prop({ type: String }) positionText: string; // 位置信息
  @Prop() navList: INavItem[]; // 导航信息
  @Ref('accessDetail') accessDetailRef: HTMLDivElement;
  @Ref('variableDetail') variableDetailRef: HTMLDivElement;

  // 初始化弹层层级
  zIndex: number = window.__bk_zIndex_manager?.nextZIndex();
  // 页面路径
  pathName = '';
  // 当前筛选状态
  statusActive = 'all';
  // 原始数据
  urlList: ITableItem[] = [];
  // 表格数据
  tableData: ITableItem[] = [];
  // 表格字段
  tableColumns = [
    { id: 'url', name: window.i18n.tc('分享历史'), checked: true, disabled: true },
    { id: 'accessCount', name: window.i18n.tc('访问次数'), checked: true, disabled: false },
    { id: 'status', name: window.i18n.tc('状态'), checked: true, disabled: false },
    { id: 'create_time', name: window.i18n.tc('产生时间'), checked: true, disabled: false },
    { id: 'create_user', name: window.i18n.tc('分享人'), checked: true, disabled: false },
    { id: 'sort', name: window.i18n.tc('链接有效期'), checked: true, disabled: false }
  ];
  // 大小
  tableSize = 'small';
  // 半选
  isIndeterminate = false;
  // 全选
  isAll = false;
  /* 分页 */
  pagination = {
    current: 1,
    count: 0,
    limit: 10
  };
  /* 弹出层 */
  popInstance = null;
  /* 访问详情 */
  accessDetail = [];
  /* 变量详情 */
  variableDetail = [{ name: '时间选择', isUpdate: true, timeRange: '2022.01.04 18:00:00 - 2023.01.04 18:00:59' }];
  /* 快捷选项映射表 */
  shortcutsMap = new Map();
  /* 表格排序 */
  tableDataSort = {
    id: '',
    order: ''
  };
  /* 当前选中的选项 */
  selected = new Set();
  loading = false; // 加载中

  created() {
    this.shortcutsMap = shortcuts.reduce((map, cur) => {
      map.set(cur.value.join(' -- '), cur.text);
      return map;
    }, new Map());
  }

  @Watch('show', { immediate: true })
  handleShow(v: boolean) {
    if (v) {
      this.zIndex = window.__bk_zIndex_manager?.nextZIndex();
      this.init();
    }
  }
  /**
   * 隐藏弹层
   */
  handleHideDialog() {
    //
    this.$emit('showChange', false);
  }

  /* 初始化 */
  async init() {
    this.loading = true;
    const { query, path } = this.$route;
    /* 页面路径 */
    const pathFn = str => {
      if (!!str) {
        return `  /  ${str}`;
      }
      return '';
    };
    /* 页面路径 */
    if (path === '/event-center') {
      this.pathName = `${this.$t('事件中心')}${pathFn(this.$t('事件详情'))}${pathFn(this.pageInfo?.alertName || '')}`;
    } else if (/^\/performance\/detail\/.+$/.test(path)) {
      this.pathName = `${this.$t('主机监控')}${pathFn(this.$t('主机详情'))}${pathFn(
        query?.['filter-bk_target_ip'] || ''
      )}`;
    } else if (path === '/k8s') {
      this.pathName = `${this.$t('Kubernetes')}${pathFn(this.positionText || '')}`;
    } else if (/^\/uptime-check\/group-detail\/.+$/.test(path) || /^\/uptime-check\/task-detail\/.+$/.test(path)) {
      this.pathName = `${this.$t('综合拨测')}${pathFn(this.$t('任务详情'))}${pathFn(this.navList?.[0]?.name || '')}`;
    } else if (/^\/custom-scenes\/view\/.+$/.test(path)) {
      this.pathName = `${this.$t('自定义场景')}${pathFn(this.navList?.[0]?.name || '')}${pathFn(
        this.navList?.[0]?.subName || ''
      )}`;
    } else if (/^\/collect-config\/view\/.+$/.test(path)) {
      this.pathName = `${this.$t('数据采集')}${pathFn(this.$t('可视化'))}${pathFn(
        this.navList?.[0]?.name || ''
      )}${pathFn(this.navList?.[0]?.subName || '')}`;
    } else if (/^\/custom-escalation-view\/.+$/.test(path)) {
      this.pathName = `${this.$t('自定义指标')}${pathFn(this.$t('可视化'))}${pathFn(
        this.navList?.[0]?.name || ''
      )}${pathFn(this.navList?.[0]?.subName || '')}`;
    } else if (/^\/custom-escalation-event-view\/.+$/.test(path)) {
      this.pathName = `${this.$t('自定义事件')}${pathFn(this.$t('可视化'))}${pathFn(
        this.navList?.[0]?.name || ''
      )}${pathFn(this.navList?.[0]?.subName || '')}`;
    } else if (/^\/application/.test(path) || /^\/apm\/application/.test(path)) {
      this.pathName = `APM${pathFn(this.navList?.[1]?.name)}${pathFn(this.positionText || '')}`;
    } else if (/^\/service/.test(path) || /^\/apm\/service/.test(path)) {
      this.pathName = `APM${pathFn(this.navList?.[1]?.name)}${pathFn(this.navList?.[2]?.name)}${pathFn(
        this.positionText || ''
      )}`;
    }
    const filterParams = {};
    Object.keys(query).forEach(key => {
      if (/^filter-.+$/.test(key)) {
        filterParams[key.replace('filter-', '')] = query[key];
      }
    });
    const data = await getShareTokenList({
      type: this.$route.name === 'event-center' ? 'event' : query.sceneId,
      filter_params: filterParams,
      scene_params: !!query?.dashboardId
        ? { sceneType: query.sceneType, sceneId: query.sceneId, dashboardId: query.dashboardId }
        : undefined
    }).catch(() => []);
    this.urlList = data.map(item => ({
      ...item,
      link: `${location.origin}${location.pathname}?bizId=${this.$store.getters.bizId}/#/share/${item.token || ''}`,
      accessCount: item.access_info?.total || 0,
      isCheck: false,
      expireTimeStr: !!item.params_info?.[0]?.expire_period
        ? periodStrFormat(item.params_info?.[0]?.expire_period)
        : formNowStrFormat(dayjs.tz(item.create_time).from(dayjs.tz(Number(item.expire_time) * 1000), true))
    }));
    this.pagination.count = this.urlList.length;
    const { current, limit } = this.pagination;
    this.tableData = this.urlList.slice((current - 1) * limit, current * limit);
    this.loading = false;
  }

  /* 状态筛选 */
  handleStatusChange(item) {
    if (this.statusActive !== item.id) {
      this.statusActive = item.id;
      this.pagination.current = 1;
      this.setTableData();
    }
  }
  /* 获取当前表格数据 */
  setTableData() {
    const sortFn = (tableData: ITableItem[]) => {
      if (this.tableDataSort.id) {
        /* 是否升序 */
        const isAscending = this.tableDataSort.order === 'ascending';
        const target = JSON.parse(JSON.stringify(tableData));
        target.sort((a: ITableItem, b: ITableItem) => {
          switch (this.tableDataSort.id) {
            case 'accessCount': {
              if (isAscending) {
                return a.accessCount - b.accessCount;
              }
              return b.accessCount - a.accessCount;
            }
            case 'create_time': {
              const aTime = dayjs.tz(a.create_time).unix();
              const bTime = dayjs.tz(b.create_time).unix();
              if (isAscending) {
                return aTime - bTime;
              }
              return bTime - aTime;
            }
            case 'create_user': {
              if (isAscending) {
                return a.create_user.localeCompare(b.create_user);
              }
              return b.create_user.localeCompare(a.create_user);
            }
          }
        });
        return target;
      }
      return tableData;
    };
    const filterUrlList =
      this.statusActive === 'all' ? this.urlList : this.urlList.filter(item => item.status === this.statusActive);
    this.pagination.count = filterUrlList.length;
    const { current, limit } = this.pagination;
    const sortTableData = sortFn(filterUrlList);
    this.tableData = sortTableData.slice((current - 1) * limit, current * limit);
    this.resetCheckStatus();
  }

  /* 展开弹层 */
  handleShowPop(event: Event, el, placement = 'bottom-start') {
    this.popInstance = this.$bkPopover(event.target, {
      content: el || this.accessDetailRef,
      trigger: 'click',
      theme: 'light',
      placement,
      boundary: 'window',
      interactive: true,
      arrow: true,
      onHidden: () => {
        this.tableData.forEach(t => {
          t.isShowAccess = false;
        });
      }
    });
    this.popInstance?.show?.();
  }
  /* 清除弹层 */
  handlePopoerHidden() {
    this.popInstance?.hide?.(0);
    this.popInstance?.destroy?.();
    this.popInstance = null;
  }
  /* 访问详情 */
  handleAccessDetail(event, row: ITableItem) {
    this.handlePopoerHidden();
    row.isShowAccess = true;
    this.accessDetail = row.access_info.data.map(item => ({
      user: item.visitor,
      time: dayjs.tz(item.last_time).format('YYYY-MM-DD HH:mm:ss')
    }));
    this.handleShowPop(event, this.accessDetailRef);
  }

  /* 变量详情 */
  handleDetail(event, row: ITableItem) {
    this.handlePopoerHidden();
    const timeRangeItem = row.params_info.find(item => item.name === 'time_range');
    if (timeRangeItem) {
      const range = !!timeRangeItem?.default_time_range?.length
        ? timeRangeItem.default_time_range
        : [timeRangeItem.start_time * 1000, timeRangeItem.end_time * 1000];
      const timeRangeStr =
        this.shortcutsMap.get(range.join(' -- ')) ||
        new DateRange(range, 'YYYY-MM-DD HH:mm:ss', window.timezone).toDisplayString();
      this.variableDetail = [
        { name: this.$tc('时间选择'), isUpdate: !timeRangeItem.lock_search, timeRange: timeRangeStr }
      ];
    }
    this.handleShowPop(event, this.variableDetailRef, 'bottom-end');
  }

  /* 单个回收 */
  handleRecycle(row: ITableItem) {
    const tempSet = new Set();
    tempSet.add(row.token);
    this.commonRecycle(tempSet as Set<string>);
  }
  /* 批量回收 */
  handleBatchRecycle() {
    const tempSet = new Set();
    this.tableData.forEach(item => {
      if (item.isCheck) {
        tempSet.add(item.token);
      }
    });
    this.commonRecycle(tempSet as Set<string>, this.$t('确定回收所选分享链接'));
  }
  /* 回收 */
  commonRecycle(tokensSet: Set<string>, title = this.$t('确定回收当前分享链接')) {
    const { query } = this.$route;
    const type = this.$route.name === 'event-center' ? 'event' : query.sceneId;
    this.$bkInfo({
      title,
      okText: this.$tc('回收'),
      cancelText: this.$tc('取消'),
      confirmLoading: true,
      confirmFn: async () => {
        const res = await deleteShareToken({ tokens: Array.from(tokensSet), type }).catch(() => false);
        if (res || res === 0) {
          this.urlList.forEach(item => {
            if (tokensSet.has(item.token)) {
              item.status = EStatus.isDeleted;
              item.isCheck = false;
            }
          });
          this.tableData.forEach(item => {
            if (tokensSet.has(item.token)) {
              item.status = EStatus.isDeleted;
              item.isCheck = false;
            }
          });
          this.isIndeterminate = false;
          this.isAll = false;
        }
        return !!res;
      }
    });
  }

  /* 重置选中态 */
  resetCheckStatus() {
    this.urlList.forEach(item => {
      item.isCheck = false;
    });
    this.tableData.forEach(item => {
      item.isCheck = false;
    });
    this.isAll = false;
    this.isIndeterminate = false;
    this.selected = new Set();
  }

  /* 跳转 */
  handleToLink(row: ITableItem) {
    window.open(row.link);
  }
  /*  分页 */
  handlePageChange(newPage: number) {
    this.pagination.current = newPage;
    this.setTableData();
  }
  /* 分页 */
  handlePageLimitChange(limit: number) {
    this.pagination.current = 1;
    this.pagination.limit = limit;
    this.setTableData();
  }

  /* 列表排序 */
  handleSortChange({ _column, prop, order }) {
    this.tableDataSort = {
      id: prop || '',
      order: order || ''
    };
    this.setTableData();
  }

  /* 访问列表排序 */
  handleAccessDataSortChange({ _column, prop, order }) {
    if (prop) {
      const isAscending = order === 'ascending';
      this.accessDetail.sort((a, b) => {
        switch (prop) {
          case 'user': {
            if (isAscending) {
              return a[prop].localeCompare(b[prop]);
            }
            return a[prop].localeCompare(b[prop]);
          }
          case 'time': {
            const aTime = dayjs.tz(a[prop]).unix();
            const bTime = dayjs.tz(b[prop]).unix();
            if (isAscending) {
              return aTime - bTime;
            }
            return bTime - aTime;
          }
        }
      });
    } else {
      this.accessDetail.sort((a, b) => {
        const aTime = dayjs.tz(a.time).unix();
        const bTime = dayjs.tz(b.time).unix();
        return bTime - aTime;
      });
    }
  }
  /* 多选 */
  handleSelectAll(v: boolean) {
    const tempSet = new Set();
    this.tableData.forEach(item => {
      if (v) {
        if (item.status === EStatus.isEnabled) {
          item.isCheck = v;
          tempSet.add(item.token);
        }
      } else {
        item.isCheck = v;
      }
    });
    this.selected = tempSet;
    this.isIndeterminate = false;
  }
  /* 单选 */
  handleSelect(v: boolean, row: ITableItem) {
    row.isCheck = v;
    const tempSet = new Set();
    this.tableData.forEach(item => {
      if (item.isCheck) {
        tempSet.add(item.token);
      }
    });
    this.selected = tempSet;
    const len = Array.from(tempSet).length;
    this.isIndeterminate = len > 0 && len < this.tableData.length;
    this.isAll = len === this.tableData.length;
  }
  /* 表格设置 */
  handleSettingChange({ size, fields }) {
    this.tableSize = size;
    this.tableColumns.forEach(item => (item.checked = fields.some(field => field.id === item.id)));
  }

  render() {
    const statusPoint = (color1: string, color2: string) => (
      <div
        class='status-point'
        style={{ background: color2 }}
      >
        <div
          class='point'
          style={{ background: color1 }}
        ></div>
      </div>
    );
    return (
      <MonitorDialog
        value={this.show}
        zIndex={this.zIndex}
        appendToBody={true}
        needFooter={false}
        width={1280}
        title={this.$tc('管理历史分享')}
        class='history-share-manage'
        onChange={this.handleHideDialog}
      >
        <div
          class='history-share-manage-wrap'
          v-bkloading={{ isLoading: this.loading }}
        >
          <span class='top-info'>
            <span class='info-item'>
              <span class='title'>{this.$t('页面路径')}:</span>
              <span
                class='content path'
                title={this.pathName}
              >
                {this.pathName}
              </span>
            </span>
            <span class='info-item'>
              <span class='title'>{this.$t('本次分享URL')}:</span>
              <span class='content link'>
                <a
                  href={this.shareUrl}
                  target='_blank'
                >
                  {this.shareUrl}
                </a>
              </span>
            </span>
          </span>
          <div class='opreate-wrap'>
            <bk-button
              disabled={!Array.from(this.selected).length}
              theme={'primary'}
              class='mr18'
              onClick={this.handleBatchRecycle}
            >
              {this.$t('批量回收')}
            </bk-button>
            <div class='status-list'>
              {STATUS_LIST.map((item: any, index) => (
                <div
                  class={[
                    'status-list-item',
                    { active: this.statusActive === item.id },
                    { 'not-border': this.statusActive === item.id || STATUS_LIST[index + 1]?.id === this.statusActive }
                  ]}
                  key={item.id}
                  onClick={() => this.handleStatusChange(item)}
                >
                  {index !== 0 && statusPoint(item.color1, item.color2)}
                  <span>{item.name}</span>
                </div>
              ))}
            </div>
          </div>
          <div class='url-table-wrap'>
            <bk-table
              size={this.tableSize}
              pagination={this.pagination}
              {...{
                props: {
                  data: this.tableData
                }
              }}
              max-height={536}
              on-page-change={this.handlePageChange}
              on-page-limit-change={this.handlePageLimitChange}
              on-sort-change={this.handleSortChange}
            >
              {this.tableColumns
                .filter(item => item.checked)
                .map(item => {
                  switch (item.id) {
                    case 'url': {
                      return (
                        <bk-table-column
                          key={item.id}
                          width={300}
                          renderHeader={() => (
                            <div>
                              <bk-checkbox
                                indeterminate={this.isIndeterminate}
                                v-model={this.isAll}
                                onChange={this.handleSelectAll}
                              ></bk-checkbox>
                              <span class='ml8'>{item.name}</span>
                            </div>
                          )}
                          scopedSlots={{
                            default: ({ row }: { row: ITableItem }) => (
                              <div class='url-wrap'>
                                <bk-checkbox
                                  v-model={row.isCheck}
                                  disabled={row.status !== EStatus.isEnabled}
                                  onChange={v => this.handleSelect(v, row)}
                                ></bk-checkbox>
                                <MiddleOmitted
                                  v-bk-tooltips={{
                                    content: row.link,
                                    placements: ['top'],
                                    duration: [300, 20],
                                    allowHTML: false
                                  }}
                                  value={row.link}
                                  lengthNum={row.token.length + 1}
                                  click={() => this.handleToLink(row)}
                                ></MiddleOmitted>
                              </div>
                            )
                          }}
                        ></bk-table-column>
                      );
                    }
                    case 'accessCount': {
                      return (
                        <bk-table-column
                          key={item.id}
                          label={item.name}
                          sortable={'custom'}
                          prop={'accessCount'}
                          align={'right'}
                          scopedSlots={{
                            default: ({ row }: { row: ITableItem }) => (
                              <span class={['access-count-wrap', { active: row.isShowAccess }]}>
                                <span>{row.accessCount}</span>
                                <span
                                  class={['icon-monitor icon-mc-detail']}
                                  onClick={event => this.handleAccessDetail(event, row)}
                                ></span>
                              </span>
                            )
                          }}
                        ></bk-table-column>
                      );
                    }
                    case 'status': {
                      return (
                        <bk-table-column
                          key={item.id}
                          label={this.$t('状态')}
                          scopedSlots={{
                            default: ({ row }: { row: ITableItem }) => (
                              <span class='status-wrap'>
                                {statusPoint(statusMap[row.status].color1, statusMap[row.status].color2)}
                                <span>{statusMap[row.status].name}</span>
                              </span>
                            )
                          }}
                        ></bk-table-column>
                      );
                    }
                    case 'create_time': {
                      return (
                        <bk-table-column
                          key={item.id}
                          label={this.$t('产生时间')}
                          sortable={'custom'}
                          width={150}
                          prop={'create_time'}
                          show-overflow-tooltip
                          scopedSlots={{
                            default: ({ row }: { row: ITableItem }) => (
                              <span>{dayjs.tz(row.create_time).format('YYYY-MM-DD HH:mm:ss')}</span>
                            )
                          }}
                        ></bk-table-column>
                      );
                    }
                    case 'create_user': {
                      return (
                        <bk-table-column
                          key={item.id}
                          label={this.$t('分享人')}
                          sortable={'custom'}
                          prop={'create_user'}
                        ></bk-table-column>
                      );
                    }
                    case 'sort': {
                      return (
                        <bk-table-column
                          key={item.id}
                          label={this.$t('链接有效期')}
                          prop={'expire_time'}
                          scopedSlots={{
                            default: ({ row }: { row: ITableItem }) => <span>{row.expireTimeStr}</span>
                          }}
                        ></bk-table-column>
                      );
                    }
                  }
                })}
              <bk-table-column
                label={this.$t('操作')}
                scopedSlots={{
                  default: ({ row }: { row: ITableItem }) => (
                    <div>
                      <bk-button
                        disabled={row.status !== EStatus.isEnabled}
                        text
                        class='mr16'
                        onClick={() => this.handleRecycle(row)}
                      >
                        {this.$t('回收')}
                      </bk-button>
                      <bk-button
                        text
                        onClick={event => this.handleDetail(event, row)}
                      >
                        {this.$t('变量详情')}
                      </bk-button>
                    </div>
                  )
                }}
              ></bk-table-column>
              <bk-table-column type='setting'>
                <bk-table-setting-content
                  fields={this.tableColumns}
                  value-key='id'
                  label-key='name'
                  size={this.tableSize}
                  selected={this.tableColumns.filter(item => item.checked || item.disabled)}
                  on-setting-change={this.handleSettingChange}
                ></bk-table-setting-content>
              </bk-table-column>
            </bk-table>
          </div>
        </div>
        <div style={{ display: 'none' }}>
          {/* 访问详情 */}
          <div
            class='history-share-manage-access-count-detail'
            ref='accessDetail'
          >
            <bk-table
              {...{
                props: {
                  data: this.accessDetail
                }
              }}
              max-height={364}
              stripe
              on-sort-change={this.handleAccessDataSortChange}
            >
              <bk-table-column
                label={this.$t('访问人')}
                prop={'user'}
                sortable={'custom'}
              ></bk-table-column>
              <bk-table-column
                label={this.$t('访问时间')}
                prop={'time'}
                sortable={'custom'}
              ></bk-table-column>
            </bk-table>
          </div>
          {/* 变量详情 */}
          <div
            class='history-share-manage-variable-detail'
            ref='variableDetail'
          >
            <bk-table
              {...{
                props: {
                  data: this.variableDetail
                }
              }}
            >
              <bk-table-column
                label={this.$t('变量名称')}
                prop={'name'}
              ></bk-table-column>
              <bk-table-column
                label={this.$t('是否可更改')}
                prop={'isUpdate'}
                scopedSlots={{
                  default: ({ row }) => <span>{this.$t(row.isUpdate ? '是' : '否')}</span>
                }}
              ></bk-table-column>
              <bk-table-column
                label={this.$t('默认选项')}
                prop={'timeRange'}
                width={280}
              ></bk-table-column>
            </bk-table>
          </div>
        </div>
      </MonitorDialog>
    );
  }
}
