/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { defineComponent, PropType } from 'vue';
import { getDefautTimezone } from 'monitor-pc/i18n/dayjs';

import { IFavoriteItem } from '../../typings';
import RefreshRate from '../refresh-rate/refresh-rate';
import SelectMenu, { ISelectMenuOption } from '../select-menu/select-menu';
import TimeRange from '../time-range/time-range';
import { TimeRangeType } from '../time-range/utils';

import './page-tool-header.scss';

export default defineComponent({
  name: 'SearchHeader',
  props: {
    showLeft: {
      type: Boolean,
      default: true
    },
    favoritesList: {
      type: Array as PropType<IFavoriteItem[]>,
      default: () => []
    },
    timeRange: {
      type: Array as PropType<TimeRangeType>,
      default: () => ['now-1h', 'now']
    },
    timezone: {
      type: String,
      default: getDefautTimezone()
    },
    menuList: {
      type: Array as PropType<ISelectMenuOption[]>,
      default: () => []
    },
    refreshInterval: {
      type: Number,
      default: -1
    }
  },
  emits: [
    'update:showLeft',
    'update:refreshInterval',
    'deleteCollect',
    'selectCollect',
    'timeRangeChange',
    'timezoneChange',
    'refreshIntervalChange',
    'menuSelectChange',
    'immediateRefresh'
  ],
  setup(props, { emit, slots }) {
    function handleTimeRangeChange(time: TimeRangeType) {
      emit('timeRangeChange', time);
    }
    function handleTimezoneChange(timezone: string) {
      emit('timezoneChange', timezone);
    }
    return () => (
      <div class='page-tool-header-component'>
        {slots.prepend ? slots.prepend() : <div class='inquire-header-prepend'></div>}
        {slots.append ? (
          slots.append()
        ) : (
          <div class='append-tools'>
            <span class='append-tools-item'>
              <TimeRange
                modelValue={props.timeRange}
                timezone={props.timezone}
                onUpdate:modelValue={handleTimeRangeChange}
                onUpdate:timezone={handleTimezoneChange}
              />
            </span>
            <span class='append-tools-item'>
              <RefreshRate
                value={props.refreshInterval}
                onSelect={val => {
                  emit('update:refreshInterval', val);
                  emit('refreshIntervalChange', val);
                }}
                onImmediate={() => emit('immediateRefresh')}
              />
              <SelectMenu
                list={props.menuList}
                onSelect={val => emit('menuSelectChange', val)}
              >
                <i class='icon-monitor icon-mc-more-tool'></i>
              </SelectMenu>
            </span>
          </div>
        )}
      </div>
    );
  }
});
