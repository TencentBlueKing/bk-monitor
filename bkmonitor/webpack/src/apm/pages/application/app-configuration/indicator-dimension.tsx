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

import { Component } from 'vue-property-decorator';
import { Component as tsc, modifiers } from 'vue-tsx-support';

import { metricInfo } from '../../../../monitor-api/modules/apm_meta';
import { getUnitList } from '../../../../monitor-api/modules/strategies';
import PanelItem from '../../../components/panel-item/panel-item';

import IndicatorDetail from './indicator-detail';

interface IPagination {
  current: number;
  count: number;
  limit: number;
}

@Component
export default class IndicatorDimension extends tsc<{}> {
  localTimeValue = '1h'; // 时间对比值
  showCustomTime = false; // 自定义时间输入框展示
  loading = false;
  shouldUpdate = false; // 指标详情被修改过 关闭侧边栏需更新指标列表
  customTimeVal = ''; // 自定义时间
  keyword = ''; // 搜索关键字
  /** 表格分页信息 */
  pagination: IPagination = {
    current: 1,
    count: 0,
    limit: 10
  };
  metricList = []; // 全量指标数据
  tableData = []; // 当前页表格数据
  unitList = []; // 策略单位列表
  /** 查询时间列表 */
  compareTimeOptions = [
    { id: '1h', name: this.$t('1 小时前') },
    { id: '1d', name: this.$t('昨天') },
    { id: '1w', name: this.$t('上周') },
    { id: '1M', name: this.$t('一月前') }
  ];
  compareTimeCustomList = []; // 自定义添加的时间可选列表
  sideslider = {
    id: 0, // 指标id
    title: '', // 指标名
    data: {}, // 指标详情
    isShow: false
  };
  /** 启停筛选 */
  statusFilter = [
    { text: '启', value: 'active' },
    { text: '停', value: 'stop' }
  ];

  /** 时间可选项的下拉数据 */
  get compareTimeList() {
    const allList = [...this.compareTimeOptions, ...this.compareTimeCustomList];
    const allListMap = new Map();
    allList.forEach(item => {
      allListMap.set(item.id, item.name);
    });
    const value = this.localTimeValue;
    if (!allListMap.has(value))
      allList.push({
        id: value,
        name: value
      });
    return allList;
  }
  /** 应用ID */
  get appId() {
    return Number(this.$route.params.id);
  }

  created() {
    this.getmetricLst();
    this.getStragegyUnit();
  }

  /**
   * @desc 获取指标列表
   */
  async getmetricLst() {
    this.loading = true;
    const params = {
      keyword: this.keyword,
      before_time: this.localTimeValue
    };
    const list = await metricInfo(this.appId, params).catch(() => []);
    this.metricList = list;
    this.pagination.count = list.length;
    this.changelistPage(1);
    this.loading = false;
  }
  /**
   * @desc 获取策略单位列表
   */
  async getStragegyUnit() {
    const list = await getUnitList().catch(() => []);
    this.unitList = list;
  }
  /**
   * @desc 单位转换显示
   * @param { string } unit
   */
  getUnitText(unit) {
    let txt = '';
    const target = this.unitList.find(group =>
      group.formats.find(option => {
        txt = option.id === unit ? option.name : '';
        return option.id === unit;
      })
    );
    return target ? txt : '';
  }
  /**
   * @desc 前端分页
   * @param { number } page 当前页
   */
  changelistPage(page: number) {
    this.pagination.current = page;
    const { current, limit } = this.pagination;
    const start = (current - 1) * limit;
    const end = current * limit;
    this.tableData = this.metricList.slice(start, end);
  }
  /**
   * @desc 分页操作
   * @param { number } page 当前页
   */
  handlePageChange(page: number) {
    this.pagination.current = page;
    this.changelistPage(page);
  }
  /**
   * @desc 切换limit
   * @param { number } limit 每页条数
   */
  handleLimitChange(limit: number) {
    this.pagination.limit = limit;
    this.changelistPage(1);
  }
  /**
   * @desc 查看指标详情
   * @param { IMetricData } row
   */
  showIndicatirDeatil(row) {
    this.shouldUpdate = false;
    this.sideslider = {
      isShow: true,
      title: row.field_name,
      data: row,
      id: row.table_id
    };
  }
  /**
   * @description: 时间下拉收起
   * @param { boolean } val
   */
  handleSelectToggle(val: boolean) {
    if (!val) {
      this.customTimeVal = '';
      this.showCustomTime = false;
    }
  }
  /**
   * @description: 时间变更
   * @param { string } val
   */
  handleTimeChange(val: string) {
    this.localTimeValue = val;
    this.getmetricLst();
  }
  /**
   * @description: 处理bk-input事件不触发vue-tsx-support的modifiers问题
   * @param { Event } evt 事件
   * @param { * } handler 要执行的执行的方法
   */
  handleModifiers(evt: Event, handler: (evt: Event) => void) {
    modifiers.enter(handler).call(this, evt);
  }
  /**
   * @description: 自定义按下回车
   */
  handleAddCustomTime() {
    const regular = /^([1-9][0-9]*)+(m|h|d|w|M|y)$/;
    const str = this.customTimeVal.trim();
    if (regular.test(str)) {
      this.handleAddCustom(str);
    } else {
      this.$bkMessage({
        theme: 'warning',
        message: this.$t('按照提示输入'),
        offsetY: 40
      });
    }
  }
  /**
   * @description: 添加自定义时间对比
   * @param { * } str
   */
  handleAddCustom(str) {
    if (this.compareTimeList.every(item => item.id !== str)) {
      this.compareTimeCustomList.push({
        id: str,
        name: str
      });
    }
    this.showCustomTime = false;
    this.customTimeVal = '';
    this.handleTimeChange(str);
  }
  /**
   * @desc 指标检索
   * @param { IMetricData } row
   */
  handleRetrieve() {
    const url = location.href.replace(location.hash, '#/data-retrieval');
    window.open(url, '_blank');
  }
  /**
   * @desc 指标详情侧栏关闭
   */
  handleSliderHidden() {
    if (this.shouldUpdate) this.getmetricLst();
  }

  render() {
    const indicatorSlot = {
      default: props => [
        <span
          class='indicator-name'
          onClick={() => this.showIndicatirDeatil(props.row)}
        >
          {props.row.field_name}
        </span>
      ]
    };
    const operatorSlot = {
      default: props => [
        <bk-button
          class='mr10'
          theme='primary'
          text
          onClick={() => this.handleRetrieve(props.row)}
        >
          {this.$t('检索')}
        </bk-button>
      ]
    };

    return (
      <div class='conf-content indicator-dimension-wrap'>
        <PanelItem title={this.$t('指标列表')}>
          <div
            slot='headerTool'
            class='indicator-filter'
          >
            <bk-select
              class='filter-select'
              clearable={false}
              v-model={this.localTimeValue}
              onToggle={this.handleSelectToggle}
              onSelected={list => this.handleTimeChange(list)}
              onClear={() => this.handleTimeChange('')}
            >
              {this.compareTimeList.map(item => (
                <bk-option
                  key={item.id}
                  id={item.id}
                  name={item.name}
                />
              ))}
              <div class='compare-time-select-custom'>
                {this.showCustomTime ? (
                  <span class='time-input-wrap'>
                    <bk-input
                      size='small'
                      v-model={this.customTimeVal}
                      onKeydown={(_, evt) => this.handleModifiers(evt, this.handleAddCustomTime)}
                    />
                    <span
                      v-bk-tooltips={this.$t('自定义输入格式: 如 1w 代表一周 m 分钟 h 小时 d 天 w 周 M 月 y 年')}
                      class='help-icon icon-monitor icon-mc-help-fill'
                    />
                  </span>
                ) : (
                  <span
                    class='custom-text'
                    onClick={() => (this.showCustomTime = !this.showCustomTime)}
                  >
                    {this.$t('自定义')}
                  </span>
                )}
              </div>
            </bk-select>
            <bk-input
              class='filter-input'
              v-model={this.keyword}
              clearable
              right-icon={'bk-icon icon-search'}
              onEnter={this.getmetricLst}
              onClear={this.getmetricLst}
            />
          </div>
          <bk-table
            outer-border={false}
            data={this.metricList}
            pagination={this.pagination}
            on-page-change={this.handlePageChange}
            on-page-limit-change={this.handleLimitChange}
            v-bkloading={{ isLoading: this.loading }}
          >
            <bk-table-column
              label={this.$t('指标名')}
              scopedSlots={indicatorSlot}
            ></bk-table-column>
            <bk-table-column
              label={this.$t('指标别名')}
              scopedSlots={{ default: props => props.row.metric_display_name || '--' }}
            ></bk-table-column>
            <bk-table-column
              label={this.$t('指标类型')}
              width='100'
              scopedSlots={{ default: props => props.row.type }}
            ></bk-table-column>
            <bk-table-column
              label={this.$t('单位')}
              width='160'
              scopedSlots={{ default: props => this.getUnitText(props.row.unit) }}
            ></bk-table-column>
            {/* <bk-table-column
            label="启/停"
            width="80"
            filters={this.statusFilter}
            scopedSlots={{ default: props => props.row.status }}>
          </bk-table-column> */}
            <bk-table-column
              label={this.$t('操作')}
              width='120'
              scopedSlots={operatorSlot}
              key='operator'
            ></bk-table-column>
          </bk-table>
        </PanelItem>

        <bk-sideslider
          ext-cls='indicator-detail-sideslider'
          transfer={true}
          isShow={this.sideslider.isShow}
          {...{ on: { 'update:isShow': v => (this.sideslider.isShow = v) } }}
          quick-close={true}
          width={640}
          on-hidden={this.handleSliderHidden}
        >
          <div
            slot='header'
            class='title-wrap'
          >
            <span>{`${this.sideslider.title}${this.$t('指标详情')}`}</span>
            <span
              class='retrieve-btn'
              onClick={() => this.handleRetrieve()}
            >
              {this.$t('检索')}
              <span class='icon-monitor icon-fenxiang'></span>
            </span>
          </div>
          <IndicatorDetail
            slot='content'
            data={this.sideslider.data}
            unitList={this.unitList}
            on-update={val => (this.shouldUpdate = val)}
          />
        </bk-sideslider>
      </div>
    );
  }
}
