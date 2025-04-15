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

import { defineComponent, reactive, shallowRef, watch } from 'vue';
import { useI18n } from 'vue-i18n';

import { $bkPopover, Progress, Sideslider } from 'bkui-vue';
import { downloadFile } from 'monitor-common/utils';
import loadingIcon from 'monitor-ui/chart-plugins/icons/spinner.svg';

import EmptyStatus from '../../../components/empty-status/empty-status';
import { handleTransformToTimestamp } from '../../../components/time-range/utils';
import { useTraceExploreStore } from '../../../store/modules/explore';

import type { DimensionType, ICommonParams, ITopKField } from '../typing';
import type { PropType } from 'vue';

import './statistics-list.scss';

const colorList = ['#F59789', '#F5C78E', '#5AB8A8', '#92D4F1', '#A3B1CC'];

export default defineComponent({
  name: 'StatisticsList',
  props: {
    commonParams: {
      type: Object as PropType<ICommonParams>,
      default: () => ({}),
    },
    selectField: {
      type: String,
      default: '',
    },
    fieldType: {
      type: String as PropType<DimensionType>,
      default: 'text',
    },
    isDimensions: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['conditionChange', 'showMore', 'sliderShowChange'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const store = useTraceExploreStore();
    const popoverLoading = shallowRef(true);
    const statisticsList = reactive<ITopKField>({
      distinct_count: 0,
      field: '',
      list: [],
    });
    const downloadLoading = shallowRef(false);

    watch(
      () => props.selectField,
      val => {
        if (!val) {
          statisticsList.distinct_count = 0;
          statisticsList.field = '';
          statisticsList.list = [];
          return;
        }
        getStatisticsList();
      }
    );

    async function getStatisticsList() {
      popoverLoading.value = true;
      const [start_time, end_time] = handleTransformToTimestamp(store.timeRange);
      const data = await getFieldTopK({
        ...props.commonParams,
        start_time,
        end_time,
        limit: 5,
        fields: [props.selectField],
      });
      statisticsList.distinct_count = data.distinct_count;
      statisticsList.field = data.field;
      statisticsList.list = data.list;
      popoverLoading.value = false;
    }

    const sliderShow = shallowRef(false);
    const sliderLoading = shallowRef(false);
    const sliderLoadMoreLoading = shallowRef(false);
    const sliderDimensionList = reactive<ITopKField>({
      distinct_count: 0,
      field: '',
      list: [],
    });
    const slideOverflowPopoverInstance = shallowRef(null);

    /** 展示侧栏 */
    async function showMore() {
      sliderShow.value = true;
      sliderLoading.value = true;
      sliderShowChange();
      emit('showMore');
      await loadMore();
      sliderLoading.value = false;
    }

    /** 加载更多 */
    async function loadMore() {
      sliderLoadMoreLoading.value = true;
      const [start_time, end_time] = handleTransformToTimestamp(store.timeRange);
      const data = await getFieldTopK({
        ...props.commonParams,
        start_time,
        end_time,
        limit: (Math.floor(sliderDimensionList.list.length / 100) + 1) * 100,
        fields: [props.selectField],
      });
      sliderDimensionList.distinct_count = data.distinct_count;
      sliderDimensionList.field = data.field;
      sliderDimensionList.list = data.list;
      sliderLoadMoreLoading.value = false;
    }

    function handleSliderShowChange(show: boolean) {
      sliderShow.value = show;
      sliderShowChange();
      if (!show) {
        sliderDimensionList.distinct_count = 0;
        sliderDimensionList.field = '';
        sliderDimensionList.list = [];
      }
    }

    async function handleDownload() {
      downloadLoading.value = true;
      const [start_time, end_time] = handleTransformToTimestamp(store.timeRange);
      const data = await getDownloadTopK({
        ...props.commonParams,
        start_time,
        end_time,
        limit: statisticsList?.distinct_count,
        fields: [props.selectField],
      }).finally(() => {
        downloadLoading.value = false;
      });
      try {
        downloadFile(data.data, 'txt', data.filename);
      } catch {}
    }

    function getFieldTopK(params) {
      return new Promise(resolve => {
        setTimeout(() => {
          console.log(params);
          const data =
            Math.random() < 0.5
              ? {
                  field: 'apiVersion',
                  total: 2143,
                  distinct_count: 8,
                  list: [
                    {
                      value: 'v1',
                      alias: 'v1',
                      count: 1730,
                      proportions: 80.73,
                    },
                    {
                      value: 'apps/v1',
                      alias: 'apps/v1',
                      count: 331,
                      proportions: 15.45,
                    },
                    {
                      value: 'batch/v1',
                      alias: 'batch/v1',
                      count: 49,
                      proportions: 2.29,
                    },
                    {
                      value: 'batch/v1beta1',
                      alias: 'batch/v1beta1',
                      count: 21,
                      proportions: 0.98,
                    },
                    {
                      value: 'kyverno.io/v1',
                      alias: 'kyverno.io/v1',
                      count: 7,
                      proportions: 0.33,
                    },
                  ],
                }
              : {
                  field: 'type',
                  total: 2143,
                  distinct_count: 2,
                  list: [
                    {
                      value: 'Normal',
                      alias: 'Normal',
                      count: 2119,
                      proportions: 98.88,
                    },
                    {
                      value: 'Warning',
                      alias: 'Warning',
                      count: 24,
                      proportions: 1.12,
                    },
                  ],
                };
          resolve(data);
        }, 1000);
      });
    }

    function getDownloadTopK(params) {
      return new Promise(resolve => {
        setTimeout(() => {
          console.log(params);
          resolve({ data: 'data', filename: 'filename' });
        }, 1000);
      });
    }

    function topKItemMouseenter(e: MouseEvent, content: string) {
      const target = e.target as HTMLElement;
      if (target.offsetWidth < target.scrollWidth) {
        slideOverflowPopoverInstance.value = $bkPopover({
          target,
          content,
          arrow: true,
          interactive: true,
          theme: 'slide-dimension-filter-overflow-tips',
        });
        slideOverflowPopoverInstance.value.install();
        setTimeout(() => {
          slideOverflowPopoverInstance.value?.show(50);
        }, 100);
      }
    }

    function hiddenSliderPopover() {
      slideOverflowPopoverInstance.value?.hide(0);
      slideOverflowPopoverInstance.value?.uninstall();
      slideOverflowPopoverInstance.value = null;
    }

    /** 渲染TopK字段行 */
    function renderTopKField(list: ITopKField['list'], scene: 'popover' | 'slider') {
      if (!list.length) return <EmptyStatus type='empty' />;

      return (
        <div class='top-k-list'>
          {list.map((item, index) => (
            <div
              key={item.value}
              class='top-k-list-item'
            >
              <div class='filter-tools'>
                <i
                  class='icon-monitor icon-a-sousuo'
                  v-bk-tooltips={{
                    content: `${props.isDimensions ? 'dimensions.' : ''}${props.selectField} = ${item.value || '""'}`,
                  }}
                  onClick={() => handleConditionChange('eq', item)}
                />
                <i
                  class='icon-monitor icon-sousuo-'
                  v-bk-tooltips={{
                    content: `${props.isDimensions ? 'dimensions.' : ''}${props.selectField} != ${item.value || '""'}`,
                  }}
                  onClick={() => handleConditionChange('ne', item)}
                />
              </div>
              <div class='progress-content'>
                <div class='info-text'>
                  <span
                    class='field-name'
                    onMouseenter={e => topKItemMouseenter(e, item.alias)}
                    onMouseleave={hiddenSliderPopover}
                  >
                    {item.alias}
                  </span>
                  <span class='counts'>
                    <span class='total'>{t('{0}条', [item.count])}</span>
                    <span class='progress-count'>{item.proportions}%</span>
                  </span>
                </div>
                <Progress
                  color={props.fieldType !== 'interger' && scene === 'popover' ? colorList[index] : '#5AB8A8'}
                  percent={item.proportions}
                  show-text={false}
                  stroke-width={6}
                />
              </div>
            </div>
          ))}
        </div>
      );
    }

    function handleConditionChange(type: 'eq' | 'ne', item: ITopKField['list'][0]) {
      emit('conditionChange', {
        key: props.selectField,
        method: type,
        value: item.value,
      });
    }

    function sliderShowChange() {
      emit('sliderShowChange', sliderShow.value);
    }

    function renderSkeleton() {
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

    return {
      popoverLoading,
      statisticsList,
      downloadLoading,
      sliderShow,
      sliderLoading,
      sliderLoadMoreLoading,
      sliderDimensionList,
      renderTopKField,
      sliderShowChange,
      showMore,
      handleSliderShowChange,
      topKItemMouseenter,
      hiddenSliderPopover,
      handleDownload,
      loadMore,
      renderSkeleton,
    };
  },

  render() {
    return (
      <div style={{ display: 'none' }}>
        <div
          ref='dimensionPopover'
          class='dimension-statistics-popover'
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
                {this.$t('去重后的字段统计')} ({this.statisticsList?.distinct_count || 0})
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
                this.renderTopKField(this.statisticsList?.list, 'popover'),
                this.statisticsList?.distinct_count > 5 && (
                  <div
                    class='load-more'
                    onClick={this.showMore}
                  >
                    {this.$t('更多')}
                  </div>
                ),
              ]}
        </div>

        <Sideslider
          width='480'
          ext-cls='dimension-top-k-slider'
          is-show={this.sliderShow}
          // show-mask={false}
          transfer={true}
          quick-close
          onUpdate:isShow={this.handleSliderShowChange}
        >
          {{
            header: () => (
              <div class='dimension-slider-header'>
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
            ),
            default: () => (
              <div class='dimension-slider-content'>
                {this.sliderLoading
                  ? this.renderSkeleton()
                  : this.renderTopKField(this.sliderDimensionList.list, 'slider')}
                {this.sliderDimensionList.distinct_count > this.sliderDimensionList.list.length && (
                  <div
                    class={['slider-load-more', { 'is-loading': this.sliderLoadMoreLoading }]}
                    onClick={this.loadMore}
                  >
                    {this.$t(this.sliderLoadMoreLoading ? '正在加载...' : '加载更多')}
                  </div>
                )}
              </div>
            ),
          }}
        </Sideslider>
      </div>
    );
  },
});
