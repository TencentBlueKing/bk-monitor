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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import { deleteItem, itemList } from '../../../monitor-api/modules/calendar';
import { Debounce } from '../../../monitor-common/utils/utils';
import StatusTab from '../../../monitor-ui/chart-plugins/plugins/table-chart/status-tab';
import EmptyStatus from '../../components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../components/empty-status/types';
import { Storage } from '../../utils';
import CommonStatus from '../monitor-k8s/components/common-status/common-status';
import { ITableFilterItem } from '../monitor-k8s/typings';

import CalendarInfo, { IProps as CalendarInfoPrps } from './components/calendar-info/calendar-info';
import CalendarAddForm from './calendar-add-form';
import { EDelAndEditType, ERepeatTypeId, ICalendarTableItem, IOptionsItem, WORKING_DATE_LIST, Z_INDEX } from './types';

import './calendar-list.scss';
/** 表格选中的列数据 */
const CALENDAR_TABLE_COLUMNS_CHECKED = 'CALENDAR_TABLE_COLUMNS_CHECKED';
/** 表格size */
const CALENDAR_TABLE_SIZE = 'CALENDAR_TABLE_SIZE';

/** 表格数据达到15条是开启虚拟滚动 */
const TABLE_ROW_COUNT = 15;
interface IProps {
  calendarList: IOptionsItem[];
  checkedCalendarIds: number[];
  defaultCalendarIds: number[];
  timeZoneList: IOptionsItem[];
}
interface IEvents {
  onUpdateCalendarList: void;
}
/**
 * 日历服务事项列表
 */
@Component
export default class CalendarList extends tsc<IProps, IEvents> {
  /** 日历列表 */
  @Prop({ type: Array, default: () => [] }) calendarList: IOptionsItem[];
  /** 时区列表 */
  @Prop({ type: Array, default: () => [] }) timeZoneList: IOptionsItem[];
  /** 表格数据 */
  @Prop({ type: Array, default: () => [] }) checkedCalendarIds: number[];
  /** 内置日历id */
  @Prop({ type: Array, default: () => [] }) defaultCalendarIds: number[];
  @Ref() bkTalbeRef: any;
  /** 新增弹窗 */
  showAddForm = false;

  infoLoading = false;
  /** 删除提示弹窗 */
  infoConfig: CalendarInfoPrps = {
    value: false,
    infoTitle: window.i18n.tc('确定删除日程？'),
    infoDesc: window.i18n.tc('当前日程包含重复内容，仅删除该日程还是全部删除？'),
    okText: window.i18n.tc('仅删除该日程'),
    cancelText: window.i18n.tc('全部删除'),
    zIndex: Z_INDEX
  };

  emptyStatusType: EmptyStatusType = 'empty';

  loading = false;

  /** 列表数据的时区 默认当前时区 */
  timeZone = dayjs.tz.guess();
  /** 搜索关键字 */
  searchKeyword = '';

  /** 时间范围 */
  timeRangeId: ERepeatTypeId = ERepeatTypeId.days;

  /** 时间范围可选列表 */
  timeRangeList: ITableFilterItem[] = [
    {
      id: 'day',
      name: window.i18n.tc('日')
    },
    {
      id: 'week',
      name: window.i18n.tc('周')
    },
    {
      id: 'month',
      name: window.i18n.tc('月')
    },
    {
      id: 'year',
      name: window.i18n.tc('年')
    }
  ];

  /** 事项编辑数据 */
  currentEditData: ICalendarTableItem = null;

  /** 事项列表 */
  tableData: ICalendarTableItem[] = [];
  virtualRender = false;
  selectedFields = [];
  tableSize = 'small';

  /** 重复名称映射 */
  repeatNameMap: Record<ERepeatTypeId, Function> = {
    [ERepeatTypeId.days]: () => window.i18n.tc('每天'),
    [ERepeatTypeId.weeks]: row => {
      if (WORKING_DATE_LIST.every(item => row.repeat.every.includes(item))) return this.$t('每个工作日');
      return window.i18n.tc('每周');
    },
    [ERepeatTypeId.months]: () => window.i18n.tc('每月'),
    [ERepeatTypeId.years]: () => window.i18n.tc('每年')
  };

  /** 缓存管理实例 */
  storage: Storage = new Storage();

  /** 时间范围 */
  get timeRange(): { startTime: number; endTime: number } {
    return {
      startTime: dayjs.tz().startOf(this.timeRangeId).unix(),
      endTime: dayjs.tz().endOf(this.timeRangeId).unix()
    };
  }

  /** 表格列数据 */
  get tableColumns() {
    return [
      {
        label: window.i18n.tc('不工作事项'),
        id: 'name',
        width: 130
      },
      {
        label: window.i18n.tc('日历'),
        id: 'calendar_name',
        with: 50
      },
      {
        label: window.i18n.tc('状态'),
        id: 'status',
        formatter: row => {
          const status = {
            type: 'success',
            text: this.$tc('有效')
          };
          if (!row.status) {
            status.text = this.$tc('已失效');
            status.type = 'disabled';
          }
          return (
            <CommonStatus
              type={status.type}
              text={status.text}
            ></CommonStatus>
          );
        }
      },
      {
        label: window.i18n.tc('开始时间'),
        id: 'start_time',
        width: 90,
        formatter: row => dayjs.tz(row.start_time * 1000, this.timeZone).format('MM-DD HH:mm')
      },
      {
        label: window.i18n.tc('结束时间'),
        id: 'end_time',
        width: 80,
        formatter: row => dayjs.tz(row.end_time * 1000, this.timeZone).format('MM-DD HH:mm')
      },
      {
        label: window.i18n.tc('重复'),
        id: 'repeat',
        formatter: row => this.repeatNameMap[row.repeat.freq]?.(row) || this.$t('不重复')
      },
      {
        label: window.i18n.tc('结束日期'),
        id: 'end_date',
        // eslint-disable-next-line no-nested-ternary
        formatter: row =>
          row.repeat.freq
            ? // eslint-disable-next-line newline-per-chained-call
              row.repeat.until
              ? dayjs.tz(row.repeat.until * 1000, this.timeZone).format('YYYY-MM-DD')
              : this.$t('永不结束')
            : '--'
      },
      {
        label: window.i18n.tc('操作'),
        id: 'handle',
        formatter: row =>
          !this.defaultCalendarIds.includes(row.calendar_id) && [
            <bk-button
              text
              onClick={() => this.handleEditItem(row)}
            >
              {this.$t('button-编辑')}
            </bk-button>,
            <bk-button
              text
              class='del-btn'
              onClick={() => this.handleDelItem(row)}
            >
              {this.$t('删除')}
            </bk-button>
          ]
      }
    ];
  }

  created() {
    this.tableSize = (this.storage.get(CALENDAR_TABLE_SIZE) ?? 'small') as string;
    const checkedList = this.storage.get(CALENDAR_TABLE_COLUMNS_CHECKED) as string[];
    // eslint-disable-next-line max-len
    this.selectedFields = !!checkedList
      ? this.tableColumns.filter(item => checkedList.includes(item.id))
      : this.tableColumns;
  }

  @Watch('tableData.length')
  tableDateLengthChange(val: number) {
    if (val >= TABLE_ROW_COUNT) {
      this.$nextTick(() => (this.virtualRender = true));
    } else {
      this.virtualRender = false;
    }
  }

  /**
   * 获取列表数据
   */
  async getTableList(needLoading = false) {
    if (needLoading) this.loading = true;
    const params = {
      calendar_ids: this.checkedCalendarIds,
      start_time: this.timeRange.startTime,
      end_time: this.timeRange.endTime,
      time_zone: this.timeZone,
      search_key: this.searchKeyword ? this.searchKeyword : undefined
    };
    this.emptyStatusType = params.search_key ? 'search-empty' : 'empty';
    const data = await itemList(params)
      .catch(() => {
        this.emptyStatusType = '500';
        return false;
      })
      .finally(() => (this.loading = false));
    if (data) {
      this.tableData = data.reduce((total, item) => {
        total.push(...item.list);
        return total;
      }, []);
    }
    return data;
  }

  /** 显示新增弹窗 */
  handleShowAddForm() {
    this.currentEditData = null;
    this.showAddForm = true;
  }

  /** 表格设置 */
  handleSettingChange({ fields, size }) {
    this.selectedFields = fields;
    this.tableSize = size;
    this.storage.set(
      CALENDAR_TABLE_COLUMNS_CHECKED,
      this.selectedFields.map(item => item.id)
    );
    this.storage.set(CALENDAR_TABLE_SIZE, this.tableSize);
  }

  /**
   * 删除一条事项
   * @param row 事项数据
   * @param index 索引
   */
  async handleDelItem(row: ICalendarTableItem) {
    this.infoConfig.value = true;
    this.currentEditData = row;
    if (!row.is_first) {
      this.infoConfig.cancelText = this.$tc('删除所有将来日程');
      this.infoConfig.infoDesc = this.$tc('当前日程包含重复内容，仅删除该日程还是删除所有将来日程？');
    } else {
      this.infoConfig.cancelText = this.$tc('全部删除');
      this.infoConfig.infoDesc = this.$tc('当前日程包含重复内容，仅删除该日程还是全部删除？');
    }
    /** 不重复 */
    if (!row.repeat.freq) {
      this.infoConfig.infoDesc = '';
      this.infoConfig.cancelText = '';
      this.infoConfig.okText = this.$tc('删除该日程');
    }
  }

  /** 删除接口 */
  async handleDelItemApi(delType: EDelAndEditType = EDelAndEditType.current) {
    this.infoLoading = true;
    const params = {
      ...this.currentEditData,
      delete_type: delType
    };
    const res = await deleteItem(params)
      .then(() => true)
      .catch(() => false)
      .finally(() => (this.infoLoading = false));
    if (res) {
      this.getTableList(true);
      this.infoConfig.value = false;
    }
    return res;
  }

  /** 删除未来时间所有事项 */
  handleInfoConfirm() {
    this.handleDelItemApi(EDelAndEditType.current);
  }

  /** 删除的全部事项 */
  handleInfoCancel() {
    this.handleDelItemApi(this.currentEditData.is_first ? EDelAndEditType.all : EDelAndEditType.currentAndFuture);
  }

  /**
   * 获取该事项的编辑数据
   * @param row
   * @param index
   */
  handleEditItem(row: ICalendarTableItem) {
    this.currentEditData = row;
    this.showAddForm = true;
  }

  /**
   * 清空编辑数据
   */
  handleAddFormChange(show: boolean) {
    if (!show) {
      this.currentEditData = null;
    }
  }

  /**
   * 切换时间范围
   */
  handleTimeRangeChange() {
    // eslint-disable-next-line @typescript-eslint/no-misused-promises
    this.$nextTick(() => this.getTableList(true));
  }

  /**
   * 搜索日历事项
   */
  @Debounce(300)
  handleSearch() {
    this.getTableList(true);
  }

  /** 更新日历列表数据 */
  @Emit('updateCalendarList')
  handleUpdateCalendarList() {}

  handleOperation(val: EmptyStatusOperationType) {
    if (val === 'clear-filter') this.searchKeyword = '';
    this.getTableList(true);
  }

  render() {
    return (
      <div
        class='calendar-list-wrapper'
        v-bkloading={{ isLoading: this.loading, zIndex: 10 }}
      >
        <div class='calendar-list-header'>
          <StatusTab
            class='time-range-tab'
            v-model={this.timeRangeId}
            needAll={false}
            statusList={this.timeRangeList}
            onChange={this.handleTimeRangeChange}
          ></StatusTab>
          <bk-input
            class='search-input'
            right-icon='bk-icon icon-search'
            v-model={this.searchKeyword}
            clearable
            onChange={this.handleSearch}
          />
          <bk-button
            class='add-btn'
            theme='primary'
            icon='plus'
            onClick={this.handleShowAddForm}
          >
            {this.$t('新增事项')}
          </bk-button>
        </div>
        <div class='time-zone-row'>
          <bk-select
            class='time-zone-select simplicity-select'
            v-model={this.timeZone}
            clearable={false}
            searchable
            z-index={Z_INDEX + 10}
            behavior='simplicity'
            onSelected={() => this.getTableList(true)}
          >
            {this.timeZoneList.map(opt => (
              <bk-option
                id={opt.id}
                name={opt.name}
              ></bk-option>
            ))}
          </bk-select>
        </div>
        <bk-table
          key={this.tableData.length}
          class='calendar-table'
          ref='bkTalbeRef'
          style='margin-top: 15px'
          data={this.tableData}
          outer-border={true}
          header-border={false}
          size={this.tableSize}
          virtual-render={this.virtualRender}
          height={this.tableData.length >= TABLE_ROW_COUNT ? 600 : undefined}
        >
          <EmptyStatus
            type={this.emptyStatusType}
            slot='empty'
            onOperation={this.handleOperation}
          />
          {this.selectedFields.map((item, index) => (
            <bk-table-column
              key={index}
              label={item.label}
              prop={item.id}
              width={item.width}
              show-overflow-tooltip={true}
              formatter={item.formatter}
            ></bk-table-column>
          ))}
          <bk-table-column
            type='setting'
            tippy-options={{ zIndex: Z_INDEX }}
          >
            <bk-table-setting-content
              fields={this.tableColumns}
              selected={this.selectedFields}
              size={this.tableSize}
              on-setting-change={this.handleSettingChange}
            ></bk-table-setting-content>
          </bk-table-column>
        </bk-table>
        {/* 新增弹层 */}
        <CalendarAddForm
          v-model={this.showAddForm}
          editData={this.currentEditData}
          calendarList={this.calendarList}
          onUpdateList={() => this.getTableList(true)}
          onShowChange={this.handleAddFormChange}
          onUpdateCalendarList={this.handleUpdateCalendarList}
        />
        <CalendarInfo
          v-model={this.infoConfig.value}
          infoDesc={this.infoConfig.infoDesc}
          infoTitle={this.infoConfig.infoTitle}
          okText={this.infoConfig.okText}
          cancelText={this.infoConfig.cancelText}
          zIndex={this.infoConfig.zIndex}
          onConfirm={this.handleInfoConfirm}
          onCancel={this.handleInfoCancel}
        ></CalendarInfo>
      </div>
    );
  }
}
