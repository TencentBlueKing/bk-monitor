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

import { type PropType, defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import RefreshRate from '../../../components/refresh-rate/refresh-rate';
import SelectMenu, { type ISelectMenuOption } from '../../../components/select-menu/select-menu';
import TimeRange from '../../../components/time-range/time-range';
import { getDefaultTimezone } from '../../../i18n/dayjs';
import FavoritesList from '../favorites-list/favorites-list';

import type { TimeRangeType } from '../../../components/time-range/utils';
import type { IFavoriteItem } from '../../../typings';

import './search-header.scss';

export default defineComponent({
  name: 'SearchHeader',
  props: {
    showLeft: {
      type: Boolean,
      default: true,
    },
    favoritesList: {
      type: Array as PropType<IFavoriteItem[]>,
      default: () => [],
    },
    timeRange: {
      type: Array as PropType<TimeRangeType>,
      default: () => ['now-1h', 'now'],
    },
    timezone: {
      type: String,
      default: getDefaultTimezone(),
    },
    menuList: {
      type: Array as PropType<ISelectMenuOption[]>,
      default: () => [],
    },
    refreshInterval: {
      type: Number,
      default: -1,
    },
    checkedValue: {
      type: Object,
      defalut: () => ({}),
    },
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
    'immediateRefresh',
  ],
  setup(props, { emit }) {
    const { t } = useI18n();
    const router = useRouter();
    const route = useRoute();
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
    function handleGotoOld() {
      router.push({
        name: 'home',
        query: route.query,
      });
    }
    return () => (
      <div class='inquire-header-wrap'>
        <div class='inquire-header-preend'>
          {!props.showLeft && (
            <span
              class='tool-icon right'
              onClick={() => emit('update:showLeft', true)}
            >
              <i class='arrow-right icon-monitor icon-double-up' />
            </span>
          )}
        </div>
        <div class='inquire-header-center'>
          {props.favoritesList.length ? (
            <FavoritesList
              checkedValue={props.checkedValue}
              value={props.favoritesList}
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
              value={props.refreshInterval}
              onImmediate={() => emit('immediateRefresh')}
              onSelect={val => {
                emit('update:refreshInterval', val);
                emit('refreshIntervalChange', val);
              }}
            />
            <SelectMenu
              list={props.menuList}
              onSelect={val => emit('menuSelectChange', val)}
            >
              <i class='icon-monitor icon-mc-more-tool' />
            </SelectMenu>
          </span>
          <div
            style='padding-right: 0px'
            class='goto-old'
          >
            <div
              class='goto-old-wrap'
              v-bk-tooltips={{
                content: t('返回新版'),
                placements: ['bottom-end'],
                zIndex: 9999,
              }}
              onClick={handleGotoOld}
            >
              <div class='icon'>
                <i class='icon-monitor icon-zhuanhuan' />
              </div>
              <span>{t('返回新版')}</span>
            </div>
          </div>
        </div>
      </div>
    );
  },
});
