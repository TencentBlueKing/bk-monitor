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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import { type PropType, defineComponent } from 'vue';

import { Sideslider } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import TopKFieldList from './topk-field-list';
import TopKListHeader from './topk-list-header';

import type { ConditionChangeEvent, ITopKField } from '../../typing';
import type { StatisticsMode } from './utils';

import './statistics-slider.scss';

/** TopK 全量数据侧栏：列表 + 加载更多 + 下载入口（耗时模式下隐藏下载） */
export default defineComponent({
  name: 'StatisticsSlider',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    loading: {
      type: Boolean,
      default: false,
    },
    loadMoreLoading: {
      type: Boolean,
      default: false,
    },
    downloadLoading: {
      type: Boolean,
      default: false,
    },
    list: {
      type: Object as PropType<ITopKField>,
      required: true,
    },
    mode: {
      type: String as PropType<StatisticsMode>,
      default: 'text',
    },
    fieldName: {
      type: String,
      default: '',
    },
  },
  emits: {
    conditionChange: (_condition: ConditionChangeEvent) => true,
    download: () => true,
    loadMore: () => true,
    showChange: (_show: boolean) => true,
  },
  setup(_props, { emit }) {
    const { t } = useI18n();

    function handleShowChange(show: boolean) {
      emit('showChange', show);
    }

    function handleConditionChange(condition: ConditionChangeEvent) {
      emit('conditionChange', condition);
    }

    function handleLoadMore() {
      emit('loadMore');
    }

    function handleDownload() {
      emit('download');
    }

    return { t, handleShowChange, handleConditionChange, handleLoadMore, handleDownload };
  },
  render() {
    return (
      <Sideslider
        width='480'
        ext-cls='trace-dimension-top-k-slider'
        is-show={this.show}
        transfer={true}
        quick-close
        onUpdate:isShow={this.handleShowChange}
      >
        {{
          header: () => (
            <div class='dimension-slider-header'>
              <TopKListHeader
                distinctCount={this.list.distinct_count}
                downloadLoading={this.downloadLoading}
                fieldName={this.fieldName}
                showDownload={this.mode !== 'duration'}
                showText={true}
                showTooltips={false}
                onDownload={this.handleDownload}
              />
            </div>
          ),
          default: () => (
            <div class='dimension-slider-content'>
              <TopKFieldList
                fieldName={this.fieldName}
                list={this.list.list}
                loading={this.loading}
                mode={this.mode}
                scene='slider'
                onConditionChange={this.handleConditionChange}
              />
              {this.list.distinct_count > this.list.list.length && (
                <div
                  class={['slider-load-more', { 'is-loading': this.loadMoreLoading }]}
                  onClick={this.handleLoadMore}
                >
                  {this.t(this.loadMoreLoading ? '正在加载...' : '加载更多')}
                </div>
              )}
            </div>
          ),
        }}
      </Sideslider>
    );
  },
});
