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
import { defineComponent, PropType, reactive, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { getDefautTimezone } from 'monitor-pc/i18n/dayjs';

import PageToolHeader from '../../../components/page-tool-header/page-tool-header';
import { ISelectMenuOption } from '../../../components/select-menu/select-menu';
import { DEFAULT_TIME_RANGE, TimeRangeType } from '../../../components/time-range/utils';
import { MenuEnum, PanelType, ToolsFormData } from '../typings';

import './page-header.scss';

export default defineComponent({
  name: 'PageHeader',
  props: {
    isShowFavorite: {
      type: Boolean,
      default: false
    },
    isShowSearch: {
      type: Boolean,
      default: true
    },
    data: {
      type: Object as PropType<ToolsFormData>,
      default: null
    }
  },
  emits: ['change', 'showTypeChange', 'refreshIntervalChange', 'menuSelect', 'immediateRefresh'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const menuList = [{ name: t('查看大图'), id: MenuEnum.FullScreen }];
    const toolsFormData = reactive<ToolsFormData>({
      timeRange: DEFAULT_TIME_RANGE,
      timezone: getDefautTimezone(),
      refreshInterval: -1
    });
    watch(
      () => props.data,
      val => {
        if (val) {
          Object.assign(toolsFormData, val);
        }
      }
    );

    function handleTimeRangeChange(timeRange: TimeRangeType) {
      toolsFormData.timeRange = timeRange;
      handleEmitData();
    }
    function handleTimezoneChange(timezone: string) {
      toolsFormData.timezone = timezone;
      handleEmitData();
    }
    function handleRefreshIntervalChange(refreshInterval: number) {
      toolsFormData.refreshInterval = refreshInterval;
      emit('refreshIntervalChange', refreshInterval);
      handleEmitData();
    }
    function handleImmediateRefresh() {
      emit('immediateRefresh');
    }

    function handleShowTypeChange(showType: PanelType, status: boolean) {
      emit('showTypeChange', showType, status);
    }

    function handleMenuSelect(menu: ISelectMenuOption) {
      emit('menuSelect', menu);
    }

    function handleEmitData() {
      emit('change', toolsFormData);
    }

    return {
      t,
      menuList,
      toolsFormData,
      handleTimeRangeChange,
      handleTimezoneChange,
      handleRefreshIntervalChange,
      handleImmediateRefresh,
      handleShowTypeChange,
      handleMenuSelect
    };
  },
  render() {
    return (
      <PageToolHeader
        class='page-header-component'
        timeRange={this.toolsFormData.timeRange}
        timezone={this.toolsFormData.timezone}
        menuList={this.menuList}
        refreshInterval={this.toolsFormData.refreshInterval}
        onTimeRangeChange={this.handleTimeRangeChange}
        onTimezoneChange={this.handleTimezoneChange}
        onRefreshIntervalChange={this.handleRefreshIntervalChange}
        onImmediateRefresh={this.handleImmediateRefresh}
        onMenuSelectChange={this.handleMenuSelect}
      >
        {{
          prepend: () => (
            <div class='page-header-left'>
              <div class='icon-container'>
                {/* <div
                  v-bk-tooltips={{
                    content: this.isShowFavorite ? this.t('点击收起收藏') : this.t('点击展开收藏'),
                    placements: ['bottom'],
                    delay: 200
                  }}
                  class={[
                    'result-icon-box',
                    {
                      'light-icon': !this.isShowFavorite
                    }
                  ]}
                  onClick={() => this.handleShowTypeChange(PanelType.Favorite, !this.isShowFavorite)}
                >
                  <span class='icon-monitor icon-mc-uncollect'></span>
                </div> */}
                <div
                  v-bk-tooltips={{
                    content: this.isShowSearch ? this.t('点击收起检索') : this.t('点击展开检索'),
                    placements: ['bottom'],
                    delay: 200
                  }}
                  class={['result-icon-box', { 'light-icon': !this.isShowSearch }]}
                  onClick={() => this.handleShowTypeChange(PanelType.Search, !this.isShowSearch)}
                >
                  <span class='bk-icon icon-monitor icon-mc-search-favorites'></span>
                </div>
              </div>
            </div>
          )
        }}
      </PageToolHeader>
    );
  }
});
