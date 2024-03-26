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

import RefreshRate from '../../../components/refresh-rate/refresh-rate';
import SelectMenu, { ISelectMenuOption } from '../../../components/select-menu/select-menu';
import TimeRange from '../../../components/time-range/time-range';
import { TimeRangeType } from '../../../components/time-range/utils';
import { getDefautTimezone } from '../../../i18n/dayjs';
import { IFavoriteItem } from '../../../typings';
import FavoritesList from '../favorites-list/favorites-list';

import './search-header.scss';

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
    refleshInterval: {
      type: Number,
      default: -1
    },
    checkedValue: {
      type: Object,
      defalut: () => ({})
    }
  },
  emits: [
    'update:showLeft',
    'update:refleshInterval',
    'deleteCollect',
    'selectCollect',
    'timeRangeChange',
    'timezoneChange',
    'refleshIntervalChange',
    'menuSelectChange',
    'immediateReflesh'
  ],
  setup(props, { emit }) {
    function handleDeleteCollect(id: number | string) {
      emit('deleteCollect', id);
    }
    function handleSelectCollectItem(id: number | string) {
      emit('selectCollect', id);
    }
    function handleTimeRangeChange(time: TimeRangeType) {
      emit('timeRangeChange', time);
    }
    function handleTimezoneChange(timezone: string) {
      emit('timezoneChange', timezone);
    }
    return () => (
      <div class='inquire-header-wrap'>
        <div class='inquire-header-preend'>
          {!props.showLeft && (
            <span
              class='tool-icon right'
              onClick={() => emit('update:showLeft', true)}
            >
              <i class='arrow-right icon-monitor icon-double-up'></i>
            </span>
          )}
        </div>
        <div class='inquire-header-center'>
          {props.favoritesList.length ? (
            <FavoritesList
              value={props.favoritesList}
              checkedValue={props.checkedValue}
              onDelete={handleDeleteCollect}
              onSelect={handleSelectCollectItem}
            />
          ) : (
            ''
          )}
        </div>
        <div class='inquire-header-append'>
          <span class='inquire-header-append-item'>
            <TimeRange
              modelValue={props.timeRange}
              timezone={props.timezone}
              onUpdate:modelValue={handleTimeRangeChange}
              onUpdate:timezone={handleTimezoneChange}
            />
          </span>
          <span class='inquire-header-append-item'>
            <RefreshRate
              value={props.refleshInterval}
              onSelect={val => {
                emit('update:refleshInterval', val);
                emit('refleshIntervalChange', val);
              }}
              onImmediate={() => emit('immediateReflesh')}
            />
            <SelectMenu
              list={props.menuList}
              onSelect={val => emit('menuSelectChange', val)}
            >
              <i class='icon-monitor icon-mc-more-tool'></i>
            </SelectMenu>
          </span>
        </div>
      </div>
    );
  }
});
