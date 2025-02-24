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

import { eventTopK } from 'monitor-api/modules/data_explorer';

import EmptyStatus from '../../../components/empty-status/empty-status';

import type { EmptyStatusType } from '../../../components/empty-status/types';
import type { IDimensionField, IFormData, ITopKField } from '../typing';

import './dimension-filter-panel.scss';

interface DimensionFilterPanelProps {
  formData: IFormData;
  list: IDimensionField[];
  listLoading: boolean;
}

interface DimensionFilterPanelEvents {
  onClose(): void;
  onConditionChange(val): void;
}

@Component
export default class DimensionFilterPanel extends tsc<DimensionFilterPanelProps, DimensionFilterPanelEvents> {
  @Prop() formData!: IFormData;
  @Prop({ default: () => [] }) list!: IDimensionField[];
  @Prop({ default: false }) listLoading!: boolean;

  @Ref('dimensionPopover') dimensionPopoverRef!: HTMLDivElement;

  @InjectReactive('formatTimeRange') formatTimeRange;
  typeIconMap = {
    keyword: 'icon-string',
    text: 'icon-text',
    interger: 'icon-number',
    date: 'icon-mc-time',
  };

  emptyStatus: EmptyStatusType = 'empty';

  /** 字段列表的count统计 */
  fieldListCount = {};

  searchVal = '';
  /** 搜索结果列表 */
  searchResultList: IDimensionField[] = [];
  /** 已选择的字段 */
  activeField = '';
  popoverLoading = true;
  /** popover实例 */
  popoverInstance = null;
  /** 统计列表 */
  statisticsList: ITopKField[] = [];

  @Watch('list')
  async handleListChange() {
    this.searchVal = '';
    this.emptyStatus = 'search-empty';
    this.searchResultList = this.list;

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

  handleSearchValChange(val: string) {
    this.searchVal = val;
    this.emptyStatus = val ? 'search-empty' : 'empty';
  }

  /** 关键字搜索 */
  handleSearch() {
    if (!this.searchVal) {
      this.searchResultList = this.list;
    } else {
      this.searchResultList = this.list.filter(item => item.name.includes(this.searchVal));
    }
  }

  /** 维度项点击 */
  async handleDimensionItemClick(e: Event, item) {
    this.popoverLoading = true;
    this.popoverInstance?.hide(100);
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
    this.activeField = item.name;
    if (!item.is_option_enabled) return;
    this.popoverInstance = this.$bkPopover(e.currentTarget, {
      content: this.dimensionPopoverRef,
      placement: 'right',
      width: 400,
      distance: -5,
      boundary: 'window',
      trigger: 'manul',
      theme: 'light event-retrieval-dimension-filter',
      arrow: true,
      interactive: true,
      onHide: () => {
        this.activeField = '';
      },
    });
    this.popoverInstance?.show(100);
    const list = await this.getFieldTopK({
      limit: 5,
      fields: [item.name],
    });
    this.statisticsList = list;
    this.popoverLoading = false;
  }

  @Emit('conditionChange')
  handleConditionChange(type, item: ITopKField['list'][0]) {
    if (type === 'eq') {
      return { condition: 'and', key: this.activeField, method: 'eq', value: [item.value] };
    }
    return { condition: 'and', key: this.activeField, method: 'ne', value: [item.value] };
  }

  getFieldTopK(params) {
    const { result_table_id, ...formData } = this.formData; //
    return eventTopK({
      query_configs: [
        {
          ...formData,
          table: this.formData.result_table_id,
        },
      ],
      start_time: this.formatTimeRange[0],
      end_time: this.formatTimeRange[1],
      ...params,
    }).catch(() => []);
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

  render() {
    if (this.listLoading) return this.renderSkeleton();

    return (
      <div class='dimension-filter-panel-comp'>
        <div class='header'>
          <div class='title'>{this.$t('维度过滤')}</div>
          <i
            class='icon-monitor icon-back-left'
            onClick={this.handleClose}
          />
        </div>
        <div class='search-input'>
          <bk-input
            v-model={this.searchVal}
            placeholder={this.$t('搜索 维度字段')}
            right-icon='bk-icon icon-search'
            on-right-icon-click={this.handleSearch}
            onBlur={this.handleSearch}
            onChange={this.handleSearchValChange}
            onEnter={this.handleSearch}
          />
        </div>

        {this.searchResultList.length ? (
          <div class='dimension-list'>
            {this.searchResultList.map(item => (
              <div
                key={item.name}
                class={{ 'dimension-item': true, active: this.activeField === item.name }}
                onClick={e => this.handleDimensionItemClick(e, item)}
              >
                <span class={['icon-monitor', this.typeIconMap[item.type], 'type-icon']} />
                <span
                  class='dimension-name'
                  v-bk-overflow-tips
                >
                  {item.alias}
                </span>
                {item.is_option_enabled && <span class='dimension-count'>{this.fieldListCount[item.name] || 0}</span>}
              </div>
            ))}
          </div>
        ) : (
          <EmptyStatus
            showOperation={false}
            type={this.emptyStatus}
          />
        )}

        <div style={{ display: 'none' }}>
          <div
            ref='dimensionPopover'
            class='event-retrieval-dimension-filter-content'
          >
            <div class='popover-header'>
              <div class='title'>
                {this.activeField}
                {this.$t('去重后的字段统计')}
              </div>
              <div class='count'>{this.fieldListCount[this.activeField]}</div>
            </div>
            {this.popoverLoading ? (
              <div class='skeleton-wrap'>
                {new Array(5).fill(null).map((_, index) => (
                  <div
                    key={index}
                    class='skeleton-element'
                  />
                ))}
              </div>
            ) : (
              <div class='field-list'>
                {this.statisticsList[0].list.map(item => (
                  <div
                    key={item.value}
                    class='field-item'
                  >
                    <div class='filter-tools'>
                      <i
                        class='icon-monitor icon-a-sousuo'
                        onClick={() => this.handleConditionChange('eq', item)}
                      />
                      <i
                        class='icon-monitor icon-sousuo-'
                        onClick={() => this.handleConditionChange('ne', item)}
                      />
                    </div>
                    <div class='progress-content'>
                      <div class='info-text'>
                        <span class='field-name'>{item.alias}</span>
                        <span class='counts'>
                          <span class='total'>{this.$t('{0}条', [item.count])}</span>
                          <span class='progress-count'>{item.proportions}%</span>
                        </span>
                      </div>
                      <bk-progress
                        color='#5AB8A8'
                        percent={item.proportions / 100}
                        show-text={false}
                        stroke-width={6}
                      />
                    </div>
                  </div>
                ))}
                {this.fieldListCount[this.activeField] > 5 && <div class='load-more'>{this.$t('更多')}</div>}
              </div>
            )}
          </div>
        </div>
      </div>
    );
  }
}
