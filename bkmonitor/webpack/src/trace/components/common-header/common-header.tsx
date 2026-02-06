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

import { defineComponent, type PropType } from 'vue';
import { useI18n } from 'vue-i18n';

import { Badge } from 'bkui-vue';
import { random } from 'monitor-common/utils';

import RefreshRate from '../refresh-rate/refresh-rate';
import SelectMenu, { type ISelectMenuOption } from '../select-menu/select-menu';
import TimeRange from '../time-range/time-range';

import type { TimeRangeType } from '../time-range/utils';

import './common-header.scss';

export type FeatureType = 'gotoOld' | 'refresh' | 'timeRange';

export default defineComponent({
  name: 'CommonHeader',
  props: {
    timeRange: {
      type: Array as PropType<TimeRangeType>,
      default: () => [],
    },
    timezone: {
      type: String,
      default: '',
    },
    refreshImmediate: {
      type: String,
      default: '',
    },
    refreshInterval: {
      type: Number,
      default: -1,
    },
    hideFeature: {
      type: Array as PropType<FeatureType[]>,
      default: () => [],
    },
    menuList: {
      type: Array as PropType<ISelectMenuOption[]>,
      default: () => [],
    },
  },
  emits: [
    'timeRangeChange',
    'timezoneChange',
    'immediateRefreshChange',
    'refreshIntervalChange',
    'menuSelect',
    'gotoOld',
  ],
  setup(props, { emit }) {
    const { t } = useI18n();

    const handleTimeRangeChange = (value: TimeRangeType) => {
      emit('timeRangeChange', value);
    };

    const handleTimezoneChange = (value: string) => {
      emit('timezoneChange', value);
    };

    const handleImmediateRefresh = () => {
      emit('immediateRefreshChange', random(5));
    };

    const handleRefreshChange = (value: number) => {
      emit('refreshIntervalChange', value);
    };

    const handleMenuSelectChange = (value: ISelectMenuOption) => {
      emit('menuSelect', value);
    };

    const handleGotoOld = () => {
      emit('gotoOld');
    };

    return {
      t,
      handleTimeRangeChange,
      handleTimezoneChange,
      handleImmediateRefresh,
      handleRefreshChange,
      handleMenuSelectChange,
      handleGotoOld,
    };
  },
  render() {
    return (
      <div class='common-header-comp'>
        <div class='header-left'>{this.$slots.left?.()}</div>
        <div class='header-center'>{this.$slots.center?.()}</div>
        <div class='header-tools'>
          {!this.hideFeature.includes('timeRange') && (
            <TimeRange
              modelValue={this.timeRange}
              timezone={this.timezone}
              onUpdate:modelValue={this.handleTimeRangeChange}
              onUpdate:timezone={this.handleTimezoneChange}
            />
          )}

          {!this.hideFeature.includes('refresh') && (
            <RefreshRate
              value={this.refreshInterval}
              onImmediate={this.handleImmediateRefresh}
              onSelect={this.handleRefreshChange}
            />
          )}
          {!!this.menuList.length && (
            <SelectMenu
              list={this.menuList}
              onSelect={this.handleMenuSelectChange}
            >
              <i class='icon-monitor icon-mc-more-tool' />
            </SelectMenu>
          )}
        </div>
        {!this.hideFeature.includes('gotoOld') && (
          <div class='goto-old'>
            <div
              class='goto-old-wrap'
              v-bk-tooltips={{
                content: this.t('回到旧版'),
                placements: ['bottom-end'],
                zIndex: 9999,
              }}
              onClick={() => this.handleGotoOld()}
            >
              <div class='icon'>
                <i class='icon-monitor icon-zhuanhuan' />
              </div>
              {this.$slots.gotoOld?.() || (
                <Badge
                  count='!'
                  theme='warning'
                >
                  <span>{this.t('回到旧版')}</span>
                </Badge>
              )}
            </div>
          </div>
        )}
      </div>
    );
  },
});
