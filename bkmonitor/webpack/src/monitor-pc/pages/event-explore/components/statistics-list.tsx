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

import { Component, Emit, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { downloadFile } from 'monitor-common/utils';
import loadingIcon from 'monitor-ui/chart-plugins/icons/spinner.svg';

import EmptyStatus from '../../../components/empty-status/empty-status';
import { APIType, getDownloadTopK, getEventTopK } from '../api-utils';

import type { ITopKField } from '../typing';

import './statistics-list.scss';
interface StatisticsListProps {
  selectField: string;
  popoverInstance?: any;
}

interface StatisticsListEvents {
  onConditionChange(val): void;
  onShowMore(): void;
  onSliderShowChange(sliderShow: boolean): void;
}

@Component
export default class StatisticsList extends tsc<StatisticsListProps, StatisticsListEvents> {
  @Prop({ type: String, default: '' }) selectField: string;
  @Prop({ type: Object, default: null }) popoverInstance: any;

  @InjectReactive('commonParams') commonParams;
  @InjectReactive({
    from: 'source',
    default: APIType.MONITOR,
  })
  source!: APIType;

  sliderShow = false;
  sliderLoading = false;
  sliderLoadMoreLoading = false;

  /** 维度统计列表 */
  statisticsList: ITopKField = { distinct_count: 0, field: '', list: [] };
  /** 侧栏维度列表 */
  sliderDimensionList: ITopKField = { distinct_count: 0, field: '', list: [] };

  popoverLoading = true;
  downloadLoading = false;

  /** 渲染TopK字段行 */
  renderTopKField(list: ITopKField['list'] = []) {
    if (!list.length) return <EmptyStatus type='empty' />;

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
                <span
                  class='field-name'
                  v-bk-overflow-tips
                >
                  {item.alias}
                </span>
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

  @Emit('conditionChange')
  handleConditionChange(type, item: ITopKField['list'][0]) {
    if (type === 'eq') {
      return [{ condition: 'and', key: this.selectField, method: 'eq', value: [item.value] }];
    }
    return [{ condition: 'and', key: this.selectField, method: 'ne', value: [item.value] }];
  }

  @Emit('sliderShowChange')
  sliderShowChange() {
    return this.sliderShow;
  }

  @Watch('selectField')
  watchSelectFieldChange(val) {
    if (!val) {
      return;
    }
    this.getStatisticsList();
  }

  async getStatisticsList() {
    this.popoverLoading = true;
    this.statisticsList = await this.getFieldTopK({
      limit: 5,
      fields: [this.selectField],
    });
    this.popoverLoading = false;
    this.popoverInstance?.popperInstance?.update();
  }

  /** 展示侧栏 */
  async showMore() {
    this.sliderShow = true;
    this.sliderLoading = true;
    this.$emit('showMore');
    await this.loadMore();
    this.sliderLoading = false;
  }

  /** 加载更多 */
  async loadMore() {
    this.sliderLoadMoreLoading = true;
    this.sliderDimensionList = await this.getFieldTopK({
      limit: (Math.floor(this.sliderDimensionList.list.length / 100) + 1) * 100,
      fields: [this.selectField],
    });
    this.sliderLoadMoreLoading = false;
  }

  handleSliderShowChange(show: boolean) {
    this.sliderShow = show;
    this.sliderShowChange();
    if (!show) {
      this.sliderDimensionList = { distinct_count: 0, field: '', list: [] };
    }
  }

  async handleDownload() {
    this.downloadLoading = true;
    const data = await getDownloadTopK(
      {
        limit: this.statisticsList.distinct_count,
        fields: [this.selectField],
        ...this.commonParams,
      },
      this.source
    ).finally(() => {
      this.downloadLoading = false;
    });
    try {
      downloadFile(data, 'txt', `${this.selectField}.txt`);
    } catch {}
  }

  async getFieldTopK(params) {
    const data = await getEventTopK({
      ...this.commonParams,
      ...params,
    }).catch(() => [{ distinct_count: 0, field: '', list: [] }]);
    return data[0];
  }

  renderSkeleton() {
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

  render() {
    return (
      <div style={{ display: 'none' }}>
        <div
          ref='dimensionPopover'
          class='event-retrieval-dimension-filter-content'
        >
          <div class='popover-header'>
            <div class='dimension-top-k-title'>
              <span
                class='field-name'
                v-bk-overflow-tips
              >
                {this.selectField}
              </span>
              <span class='divider' />
              <span class='desc'>
                {this.$t('去重后的字段统计')} ({this.statisticsList.distinct_count || 0})
              </span>
            </div>
            {this.downloadLoading ? (
              <img
                class='loading-icon'
                alt=''
                src={loadingIcon}
              />
            ) : (
              <div
                class='download-tool'
                onClick={this.handleDownload}
              >
                <i class='icon-monitor icon-xiazai2' />
                <span class='text'>{this.$t('下载')}</span>
              </div>
            )}
          </div>
          {this.popoverLoading
            ? this.renderSkeleton()
            : [
                this.renderTopKField(this.statisticsList.list),
                this.statisticsList.distinct_count > 5 && (
                  <div
                    class='load-more'
                    onClick={this.showMore}
                  >
                    {this.$t('更多')}
                  </div>
                ),
              ]}
        </div>

        <bk-sideslider
          width='480'
          ext-cls='dimension-top-k-slider'
          is-show={this.sliderShow}
          show-mask={false}
          transfer={true}
          quick-close
          {...{ on: { 'update:isShow': this.handleSliderShowChange } }}
        >
          <div
            class='dimension-slider-header'
            slot='header'
          >
            <div class='dimension-top-k-title'>
              <span
                class='field-name'
                v-bk-overflow-tips
              >
                {this.selectField}
              </span>
              <span class='divider' />
              <span class='desc'>
                {this.$t('去重后的字段统计')} ({this.sliderDimensionList.distinct_count || 0})
              </span>
            </div>
            {this.downloadLoading ? (
              <img
                class='loading-icon'
                alt=''
                src={loadingIcon}
              />
            ) : (
              <div
                class='download-tool'
                onClick={this.handleDownload}
              >
                <i class='icon-monitor icon-xiazai2' />
                <span class='text'>{this.$t('下载')}</span>
              </div>
            )}
          </div>
          <div
            class='dimension-slider-content'
            slot='content'
          >
            {this.sliderLoading ? this.renderSkeleton() : this.renderTopKField(this.sliderDimensionList.list)}
            {this.sliderDimensionList.distinct_count > this.sliderDimensionList.list.length && (
              <div
                class={['slider-load-more', { 'is-loading': this.sliderLoadMoreLoading }]}
                onClick={this.loadMore}
              >
                {this.$t(this.sliderLoadMoreLoading ? '正在加载...' : '加载更多')}
              </div>
            )}
          </div>
        </bk-sideslider>
      </div>
    );
  }
}
