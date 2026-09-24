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
import { type PropType, computed, defineComponent, onMounted, onScopeDispose, shallowRef } from 'vue';

import { dayjs } from '@blueking/date-picker';
import { Button, Radio, Sideslider, Switcher } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import ProfilingServiceSelect from './profiling-service-select';
import RefreshRate from '@/components/refresh-rate/refresh-rate';
import TimeRangePicker from '@/components/time-range/time-range';

import type { Application, CompareMode, ProfilingTab, QueryState, ServiceDetail } from '../types';

export default defineComponent({
  name: 'ProfilingExploreHeader',
  props: {
    state: { type: Object as PropType<QueryState>, required: true },
    tab: { type: String as PropType<ProfilingTab>, required: true },
    serviceOptions: { type: Array as PropType<Application[]>, default: () => [] },
    detail: { type: Object as PropType<ServiceDetail>, default: null },
    favoriteShow: Boolean,
    loading: Boolean,
  },
  emits: {
    tabChange: (_tab: ProfilingTab) => true,
    serviceChange: (_value: string[]) => true,
    modeChange: (_mode: CompareMode) => true,
    patch: (_state: Partial<QueryState>) => true,
    search: () => true,
    favoriteToggle: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const detailsVisible = shallowRef(false);
    const selector = shallowRef<HTMLElement>();
    const serviceSelector = shallowRef<InstanceType<typeof ProfilingServiceSelect>>();
    const serviceValue = computed<string[]>(previous => {
      const { appName, serviceName } = props.state;
      const value = appName && serviceName ? [appName, serviceName] : [];
      return value.length === previous?.length && value.every((id, index) => id === previous[index]) ? previous : value;
    });
    function handleShortcut(event: KeyboardEvent) {
      if (props.tab !== 'application' || event.key.toLowerCase() !== 'o' || !(event.metaKey || event.ctrlKey)) return;
      event.preventDefault();
      const input = selector.value?.querySelector('input');
      input?.focus();
      input?.click();
    }
    function changeTime(value: (number | string)[]) {
      emit('patch', { timeRange: value as QueryState['timeRange'], baselineRange: null, comparisonRange: null });
      emit('search');
    }
    onMounted(() => window.addEventListener('keydown', handleShortcut));
    onScopeDispose(() => window.removeEventListener('keydown', handleShortcut));
    return {
      t,
      detailsVisible,
      selector,
      serviceSelector,
      createApplication: () => serviceSelector.value?.goToApplication(true),
      serviceValue,
      changeTime,
      formatTime: (time: null | number) =>
        time
          ? dayjs(time * 1000)
              .tz(props.state.timezone)
              .format('YYYY-MM-DD HH:mm:ss')
          : '--',
    };
  },
  render() {
    return (
      <header class='profiling-explore-header'>
        <div class='profiling-heading'>
          <Button
            v-tippy={this.t('收藏夹')}
            aria-label={this.t('收藏夹')}
            text
            onClick={() => this.$emit('favoriteToggle')}
          >
            <i class={['icon-monitor icon-mc-search-favorites', { active: this.favoriteShow }]} />
          </Button>
          <h1>{this.t('Profiling 检索')}</h1>
        </div>
        <Radio.Group
          class='profiling-tabs'
          modelValue={this.tab}
          type='capsule'
          onChange={value => this.$emit('tabChange', value)}
        >
          <Radio.Button label='application'>{this.t('应用服务')}</Radio.Button>
          <Radio.Button label='file'>{this.t('文件分析')}</Radio.Button>
          <Radio.Button
            v-tippy={this.t('敬请期待')}
            label='collection'
            disabled
          >
            {this.t('主动采集')}
          </Radio.Button>
        </Radio.Group>
        {this.tab === 'application' && (
          <>
            <span class='profiling-header-divider' />
            <div class='profiling-service-tools'>
              <div
                ref='selector'
                class='profiling-service-select'
              >
                <ProfilingServiceSelect
                  ref='serviceSelector'
                  applications={this.serviceOptions}
                  loading={this.loading}
                  value={this.serviceValue}
                  onChange={value => this.$emit('serviceChange', value)}
                />
              </div>
              <Button
                v-tippy={this.t('服务详情')}
                aria-label={this.t('服务详情')}
                disabled={!this.detail}
                text
                onClick={() => {
                  this.detailsVisible = true;
                }}
              >
                <i class='icon-monitor icon-mc-detail' />
              </Button>
            </div>
            <div class='profiling-compare-switches'>
              <label class='profiling-switch'>
                <Switcher
                  modelValue={this.state.mode !== 'none'}
                  size='small'
                  theme='primary'
                  onChange={value => this.$emit('modeChange', value ? 'condition' : 'none')}
                />
                <span>{this.t('对比模式')}</span>
              </label>
              {this.state.mode !== 'none' && (
                <label class='profiling-switch'>
                  <Switcher
                    modelValue={this.state.mode === 'time'}
                    size='small'
                    theme='primary'
                    onChange={value => this.$emit('modeChange', value ? 'time' : 'condition')}
                  />
                  <span>{this.t('时间对比')}</span>
                </label>
              )}
            </div>
          </>
        )}
        {this.tab === 'file' && (
          <>
            <span class='profiling-header-divider' />
            {this.$slots.fileTools?.()}
          </>
        )}
        {this.tab !== 'collection' && (
          <div class='profiling-time-tools'>
            <TimeRangePicker
              modelValue={this.state.timeRange}
              timezone={this.state.timezone}
              onUpdate:modelValue={this.changeTime}
              onUpdate:timezone={timezone => {
                this.$emit('patch', { timezone });
                this.$emit('search');
              }}
            />
            <RefreshRate
              value={this.state.refreshInterval}
              onImmediate={() => this.$emit('search')}
              onSelect={refreshInterval => this.$emit('patch', { refreshInterval })}
            />
          </div>
        )}
        <Sideslider
          width={560}
          isShow={this.detailsVisible}
          title={this.t('服务详情')}
          quickClose
          onClosed={() => {
            this.detailsVisible = false;
          }}
        >
          {this.detail && (
            <dl class='profiling-service-detail'>
              <dt>{this.t('应用')}</dt>
              <dd>{this.detail.app_name}</dd>
              <dt>{this.t('服务')}</dt>
              <dd>{this.detail.name}</dd>
              <dt>{this.t('创建时间')}</dt>
              <dd>{this.formatTime(this.detail.create_time)}</dd>
              <dt>{this.t('最近上报时间')}</dt>
              <dd>{this.formatTime(this.detail.last_report_time)}</dd>
              <dt>{this.t('数据类型')}</dt>
              <dd>{this.detail.data_types.map(item => item.name).join(', ')}</dd>
            </dl>
          )}
        </Sideslider>
      </header>
    );
  },
});
