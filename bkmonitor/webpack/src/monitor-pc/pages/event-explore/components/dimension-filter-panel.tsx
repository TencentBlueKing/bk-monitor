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

import { Component, Emit, Ref, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from 'monitor-common/utils';

import EmptyStatus from '../../../components/empty-status/empty-status';
import { APIType, getEventTopK } from '../api-utils';
import FieldTypeIcon from './field-type-icon';
import StatisticsList from './statistics-list';

import type { EmptyStatusOperationType, EmptyStatusType } from '../../../components/empty-status/types';
import type { IWhereItem } from '../../../components/retrieval-filter/utils';
import type { ConditionChangeEvent, IDimensionField } from '../typing';

import './dimension-filter-panel.scss';

interface DimensionFilterPanelProps {
  list: IDimensionField[];
  listLoading: boolean;
  condition: IWhereItem[];
  queryString: string;
  source: APIType;
}

interface DimensionFilterPanelEvents {
  onClose(): void;
  onConditionChange(val: ConditionChangeEvent): void;
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
  @Ref('statisticsList') statisticsListRef!: StatisticsList;

  @InjectReactive('commonParams') commonParams;

  emptyStatus: EmptyStatusType = 'empty';

  /** 字段列表的count统计 */
  fieldListCount = {};
  /* 搜索关键字 */
  searchVal = '';
  /** 搜索结果列表 */
  searchResultList: IDimensionField[] = [];
  /** 已选择的字段 */
  selectField: IDimensionField = null;
  /** popover实例 */
  popoverInstance = null;

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
    this.emptyStatus = 'search-empty';
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
      this.searchResultList = this.list.filter(item => item.name.includes(this.searchVal));
    }
  }

  /** 点击维度项后展示统计弹窗 */
  async handleDimensionItemClick(e: Event, item: IDimensionField) {
    this.destroyPopover();
    this.selectField = item;
    if (!item.is_option_enabled) return;
    this.popoverInstance = this.$bkPopover(e.currentTarget, {
      content: this.statisticsListRef.$refs.dimensionPopover,
      placement: 'right',
      width: 400,
      distance: -5,
      boundary: 'viewport',
      trigger: 'manul',
      theme: 'light event-retrieval-dimension-filter',
      arrow: true,
      interactive: true,
    });
    this.popoverInstance?.show(100);
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
    return getEventTopK(
      {
        ...this.commonParams,
        ...params,
      },
      this.source
    ).catch(() => []);
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
        </div>

        {this.searchResultList.length ? (
          <div class='dimension-list'>
            {this.searchResultList.map(item => (
              <div
                key={item.name}
                class={{ 'dimension-item': true, active: this.selectField?.name === item.name }}
                onClick={e => this.handleDimensionItemClick(e, item)}
              >
                <FieldTypeIcon type={item.type} />
                <span
                  class='dimension-name'
                  v-bk-overflow-tips
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
          isDimensions={this.selectField?.is_dimensions}
          popoverInstance={this.popoverInstance}
          selectField={this.selectField?.name}
          source={this.source}
          onConditionChange={this.handleConditionChange}
          onShowMore={this.destroyPopover}
        />
      </div>
    );
  }
}
