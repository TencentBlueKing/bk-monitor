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

import EmptyStatus from '../../../components/empty-status/empty-status';
import { getDownloadTopK, getEventTopK } from '../api-utils';
import FieldTypeIcon from './field-type-icon';

import type { EmptyStatusType } from '../../../components/empty-status/types';
import type { IWhereItem } from '../../../components/retrieval-filter/utils';
import type { IDimensionField, ITopKField } from '../typing';

import './dimension-filter-panel.scss';

interface DimensionFilterPanelProps {
  list: IDimensionField[];
  listLoading: boolean;
  condition: IWhereItem[];
}

interface DimensionFilterPanelEvents {
  onClose(): void;
  onConditionChange(val): void;
}

@Component
export default class DimensionFilterPanel extends tsc<DimensionFilterPanelProps, DimensionFilterPanelEvents> {
  @Prop({ default: () => [] }) list!: IDimensionField[];
  @Prop({ default: () => [] }) condition!: IWhereItem[];
  @Prop({ default: false }) listLoading!: boolean;

  @Ref('dimensionPopover') dimensionPopoverRef!: HTMLDivElement;

  @InjectReactive('formatTimeRange') formatTimeRange;
  @InjectReactive('commonParams') commonParams;

  emptyStatus: EmptyStatusType = 'empty';

  /** 字段列表的count统计 */
  fieldListCount = {};

  searchVal = '';
  /** 搜索结果列表 */
  searchResultList: IDimensionField[] = [];
  /** 已选择的字段 */
  selectField = '';
  popoverLoading = true;
  /** popover实例 */
  popoverInstance = null;
  /** 统计列表 */
  statisticsList: ITopKField[] = [];

  sliderShow = false;
  sliderLoading = false;
  sliderDimensionList: ITopKField[] = [];

  downloadLoading = false;

  @Watch('condition')
  async watchConditionChange() {
    console.log(123);
    await this.getFieldCount();
  }

  @Watch('list')
  async watchListChange() {
    this.searchVal = '';
    this.emptyStatus = 'search-empty';
    this.searchResultList = this.list;
    await this.getFieldCount();
  }

  /** 关键字搜索 */
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

  /** 维度项点击 */
  async handleDimensionItemClick(e: Event, item) {
    this.popoverLoading = true;
    this.destroyPopover();
    this.selectField = item.name;
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
    });
    this.popoverInstance?.show(100);
    const list = await this.getFieldTopK({
      limit: 5,
      fields: [item.name],
    });
    this.statisticsList = list;
    this.popoverLoading = false;
  }

  destroyPopover() {
    this.popoverInstance?.hide(100);
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
  }

  @Emit('conditionChange')
  handleConditionChange(type, item: ITopKField['list'][0]) {
    if (type === 'eq') {
      return [{ condition: 'and', key: this.selectField, method: 'eq', value: [item.value] }];
    }
    return [{ condition: 'and', key: this.selectField, method: 'ne', value: [item.value] }];
  }

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
    return getEventTopK({
      ...this.commonParams,
      ...params,
    }).catch(() => []);
  }

  @Emit('close')
  handleClose() {}

  // 渲染骨架屏
  renderSkeleton(type: 'page' | 'topKList') {
    if (type === 'page')
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
    return (
      <div class='skeleton-wrap'>
        {new Array(5).fill(null).map((_, index) => (
          <div
            key={index}
            class='skeleton-element'
          />
        ))}
      </div>
    );
  }

  /** 渲染TopK字段行 */
  renderTopKField(list: ITopKField['list'] = []) {
    return (
      <div class='top-k-list'>
        {list.map(item => (
          <div
            key={item.value}
            class='top-k-list-item'
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
      </div>
    );
  }

  async showMore() {
    this.sliderShow = true;
    this.sliderLoading = true;
    this.destroyPopover();
    this.sliderDimensionList = await this.getFieldTopK({
      limit: this.statisticsList[0].distinct_count,
      fields: [this.selectField],
    }).catch(() => []);
    this.sliderLoading = false;
  }

  handleSliderShowChange(show: boolean) {
    this.sliderShow = show;
  }

  async handleDownload() {
    this.downloadLoading = true;
    await getDownloadTopK({
      limit: this.statisticsList[0].distinct_count,
      fields: [this.selectField],
      ...this.commonParams,
    }).finally(() => {
      this.downloadLoading = false;
    });
  }

  render() {
    if (this.listLoading) return this.renderSkeleton('page');

    return (
      <div class='dimension-filter-panel-comp'>
        <div class='header'>
          <div class='title'>{this.$t('维度过滤')}</div>
          <i
            class='icon-monitor icon-gongneng-shouqi'
            onClick={this.handleClose}
          />
        </div>
        <div class='search-input'>
          <bk-input
            v-model={this.searchVal}
            placeholder={this.$t('搜索 维度字段')}
            right-icon='bk-icon icon-search'
            clearable
            show-clear-only-hover
            on-right-icon-click={this.handleSearch}
            onBlur={this.handleSearch}
            onClear={this.handleSearch}
            onEnter={this.handleSearch}
          />
        </div>

        {this.searchResultList.length ? (
          <div class='dimension-list'>
            {this.searchResultList.map(item => (
              <div
                key={item.name}
                class={{ 'dimension-item': true, active: this.selectField === item.name }}
                onClick={e => this.handleDimensionItemClick(e, item)}
              >
                <FieldTypeIcon type={item.type} />
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
                {this.selectField}
                {this.$t('去重后的字段统计')}
              </div>
              <div class='count'>{this.statisticsList[0]?.distinct_count || 0}</div>
            </div>
            {this.popoverLoading
              ? this.renderSkeleton('topKList')
              : [
                  this.renderTopKField(this.statisticsList[0]?.list),
                  this.statisticsList[0].distinct_count > 2 && (
                    <div
                      class='load-more'
                      onClick={this.showMore}
                    >
                      {this.$t('更多')}
                    </div>
                  ),
                ]}
          </div>
        </div>

        <bk-sideslider
          width='480'
          ext-cls='dimension-top-k-slider'
          is-show={this.sliderShow}
          show-mask={false}
          quick-close
          {...{ on: { 'update:isShow': this.handleSliderShowChange } }}
        >
          <div
            class='dimension-slider-header'
            slot='header'
          >
            <div class='title'>
              <span class='field-name'>{this.selectField}</span>
              <span class='divider' />
              <span class='desc'>
                {this.$t('去重后的字段统计')} ({this.sliderDimensionList[0]?.distinct_count || 0})
              </span>
            </div>
            {this.downloadLoading ? (
              <bk-spin size='mini' />
            ) : (
              <div
                class='download-tool'
                onClick={this.handleDownload}
              >
                <i class='icon-monitor icon-xiazai1' />
                <span class='text'>{this.$t('下载')}</span>
              </div>
            )}
          </div>
          <div
            class='dimension-slider-content'
            slot='content'
          >
            {this.sliderLoading
              ? this.renderSkeleton('topKList')
              : this.renderTopKField(this.sliderDimensionList[0]?.list)}
          </div>
        </bk-sideslider>
      </div>
    );
  }
}
