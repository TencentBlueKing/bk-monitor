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

import { Component, Emit, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { CancelToken } from 'monitor-api/cancel';
import { Debounce } from 'monitor-common/utils';

import EmptyStatus from '../../../components/empty-status/empty-status';
import { APIType, getEventTopK } from '../api-utils';
import { type ConditionChangeEvent, type IDimensionField, ExploreSourceTypeEnum } from '../typing';
import FieldTypeIcon from './field-type-icon';
import StatisticsList from './statistics-list';

import type { EmptyStatusOperationType, EmptyStatusType } from '../../../components/empty-status/types';
import type { IWhereItem } from '../../../components/retrieval-filter/utils';

import './dimension-filter-panel.scss';

interface DimensionFilterPanelEvents {
  onClose(): void;
  onConditionChange(val: ConditionChangeEvent): void;
  onShowEventSourcePopover(e: Event): void;
}

interface DimensionFilterPanelProps {
  condition: IWhereItem[];
  eventSourceType?: ExploreSourceTypeEnum[];
  hasSourceSelect?: boolean;
  list: IDimensionField[];
  listLoading: boolean;
  queryString: string;
  source: APIType;
}

@Component
export default class DimensionFilterPanel extends tsc<DimensionFilterPanelProps, DimensionFilterPanelEvents> {
  /** 维度列表 */
  @Prop({ default: () => [] }) list!: IDimensionField[];
  /** 已选择的条件 */
  @Prop({ default: () => [] }) condition!: IWhereItem[];
  @Prop({ default: '' }) queryString!: string;
  @Prop({ default: false }) listLoading!: boolean;
  /** 来源 */
  @Prop({ type: String, default: APIType.MONITOR }) source: APIType;
  /** 事件来源类型 */
  @Prop({ type: Array, default: () => [ExploreSourceTypeEnum.ALL] }) eventSourceType: ExploreSourceTypeEnum[];
  @Prop({ type: Boolean, default: false }) hasSourceSelect: boolean;

  @Ref('statisticsList') statisticsListRef!: StatisticsList;

  @InjectReactive('commonParams') commonParams;
  // 是否立即刷新
  @InjectReactive('refreshImmediate') refreshImmediate: string;

  emptyStatus: EmptyStatusType = 'empty';

  /** 字段列表的count统计 */
  fieldListCount = {};
  /* 搜索关键字 */
  searchVal = '';
  /** 搜索结果列表 */
  searchResultList: IDimensionField[] = [];
  /** 已选择的字段 */
  selectField = '';
  showStatisticsPopover = false;
  slideField: IDimensionField = null;
  /** popover实例 */
  popoverInstance = null;

  topKCancelFn = null;

  @Watch('refreshImmediate')
  async watchRefreshImmediate() {
    await this.getFieldCount();
  }

  /** 条件切换后，维度count需要重新获取 */
  @Watch('condition')
  async watchConditionChange() {
    await this.getFieldCount();
  }

  @Watch('queryString')
  async watchQueryStringChange() {
    await this.getFieldCount();
  }

  @Watch('list')
  async watchListChange(list: IDimensionField[]) {
    this.searchVal = '';
    this.searchResultList = list;
    await this.getFieldCount();
  }

  /** 关键字搜索 */
  @Debounce(100)
  handleSearch(keyword: string) {
    this.searchVal = keyword;
    if (!this.searchVal) {
      this.searchResultList = this.list;
      this.emptyStatus = 'empty';
    } else {
      this.emptyStatus = 'search-empty';
      this.searchResultList = this.list.filter(item => item.pinyinStr.includes(this.searchVal));
    }
  }

  /** 点击维度项后展示统计弹窗 */
  async handleDimensionItemClick(e: Event, item: IDimensionField) {
    this.destroyPopover();
    if (!item.is_option_enabled || !this.fieldListCount[item.name]) return;
    this.selectField = item.name;
    this.slideField = item;
    this.popoverInstance = this.$bkPopover(e.currentTarget, {
      content: this.statisticsListRef.$refs.dimensionPopover,
      placement: 'right',
      width: 405,
      distance: -5,
      boundary: 'viewport',
      trigger: 'manul',
      theme: 'light event-retrieval-dimension-filter',
      arrow: true,
      interactive: true,
      onHidden: () => {
        this.showStatisticsPopover = false;
        this.selectField = '';
      },
    });
    await this.$nextTick();
    this.popoverInstance?.show(100);
    this.showStatisticsPopover = true;
  }

  destroyPopover() {
    this.popoverInstance?.hide(100);
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
  }

  @Emit('conditionChange')
  handleConditionChange(value) {
    return value;
  }

  /** 获取各个维度的count */
  async getFieldCount() {
    const fields = this.list.reduce((pre, cur) => {
      if (cur.is_option_enabled) pre.push(cur.name);
      return pre;
    }, []);
    if (!fields.length) return;
    const list = await this.getFieldTopK({
      limit: 0,
      fields,
    });
    this.fieldListCount = list.reduce((pre, cur) => {
      pre[cur.field] = cur.distinct_count;
      return pre;
    }, {});
  }

  getFieldTopK(params) {
    this.topKCancelFn?.();
    return getEventTopK(
      {
        ...this.commonParams,
        ...params,
      },
      this.source,
      {
        cancelToken: new CancelToken(c => (this.topKCancelFn = c)),
      }
    ).catch(() => []);
  }

  @Emit('showEventSourcePopover')
  handleShowEventSourcePopover(e: Event) {
    return e;
  }

  @Emit('close')
  handleClose() {}

  // 渲染骨架屏
  renderSkeleton() {
    return (
      <div class='dimension-filter-panel-skeleton'>
        <div class='skeleton-element title' />
        <div class='skeleton-element search-input' />
        {new Array(10).fill(null).map((item, index) => (
          <div
            key={index}
            class='skeleton-element list-item'
          />
        ))}
      </div>
    );
  }

  emptyOperation(type: EmptyStatusOperationType) {
    if (type === 'clear-filter') {
      this.searchVal = '';
      this.handleSearch('');
    }
  }

  renderEventSourceIcon() {
    const iconMap = {
      [ExploreSourceTypeEnum.BCS]: 'icon-bcs',
      [ExploreSourceTypeEnum.BKCI]: 'icon-landun',
      [ExploreSourceTypeEnum.HOST]: 'icon-host',
      [ExploreSourceTypeEnum.DEFAULT]: 'icon-default',
    };

    if (this.eventSourceType.includes(ExploreSourceTypeEnum.ALL)) return <i class='icon-monitor icon-all' />;
    if (this.eventSourceType.length === 1) return <i class={['source-icon', iconMap[this.eventSourceType[0]]]} />;
    return <div class='source-count-icon'>{this.eventSourceType.length}</div>;
  }

  render() {
    if (this.listLoading) return this.renderSkeleton();

    return (
      <div class='dimension-filter-panel-comp'>
        <div class='header'>
          <div class='title'>{this.$t('维度过滤')}</div>
          <i
            class='icon-monitor icon-gongneng-shouqi'
            v-bk-tooltips={{ content: this.$t('收起') }}
            onClick={this.handleClose}
          />
        </div>
        <div class='search-input'>
          <bk-input
            class={{ 'has-source-select': this.hasSourceSelect }}
            v-model={this.searchVal}
            native-attributes={{
              spellcheck: false,
            }}
            placeholder={this.$t('搜索 维度字段')}
            right-icon='bk-icon icon-search'
            clearable
            show-clear-only-hover
            on-right-icon-click={this.handleSearch}
            onBlur={this.handleSearch}
            onChange={this.handleSearch}
            onClear={this.handleSearch}
            onEnter={this.handleSearch}
          />
          {this.hasSourceSelect && (
            <div
              class='event-source-select'
              onClick={this.handleShowEventSourcePopover}
            >
              {this.renderEventSourceIcon()}
              <i class='icon-monitor icon-mc-arrow-down' />
            </div>
          )}
        </div>

        {this.searchResultList.length ? (
          <div class='dimension-list'>
            {this.searchResultList.map(item => (
              <div
                key={item.name}
                v-bk-tooltips={{
                  content: this.$t(
                    item.is_option_enabled ? '该维度暂无数据，无法进行统计分析' : '该字段类型，暂时不支持统计分析'
                  ),
                  disabled: item.is_option_enabled && this.fieldListCount[item.name],
                  interactive: false,
                  placement: 'right',
                }}
              >
                <div
                  class={{
                    'dimension-item': true,
                    active: this.selectField === item.name,
                    disabled: !item.is_option_enabled || !this.fieldListCount[item.name],
                  }}
                  onClick={e => this.handleDimensionItemClick(e, item)}
                >
                  <FieldTypeIcon type={item.type} />
                  <span
                    class='dimension-name'
                    v-bk-overflow-tips={{ content: item.alias }}
                  >
                    {item.alias}
                  </span>
                  {item.is_option_enabled && [
                    <span
                      key={`${item.name}__count`}
                      class='dimension-count'
                    >
                      {this.fieldListCount[item.name] || 0}
                    </span>,
                    <i
                      key={`${item.name}__statistics`}
                      class='icon-monitor icon-Chart statistics-icon'
                    />,
                  ]}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <EmptyStatus
            type={this.emptyStatus}
            onOperation={this.emptyOperation}
          />
        )}

        <StatisticsList
          ref='statisticsList'
          fieldType={this.slideField?.type}
          isDimensions={this.slideField?.is_dimensions}
          isShow={this.showStatisticsPopover}
          isShowChart={true}
          popoverInstance={this.popoverInstance}
          selectField={this.slideField?.name}
          source={this.source}
          onConditionChange={this.handleConditionChange}
          onShowMore={this.destroyPopover}
        />
      </div>
    );
  }
}
