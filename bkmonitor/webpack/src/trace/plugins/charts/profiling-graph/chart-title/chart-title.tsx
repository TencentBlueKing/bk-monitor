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

import { computed, defineComponent, PropType, ref } from 'vue';
import { Dropdown, Input } from 'bkui-vue';
import { ViewModeItem, ViewModeType } from 'monitor-ui/chart-plugins/typings/profiling-graph';
import { debounce } from 'throttle-debounce';

import { DirectionType } from '../../../../typings';

import './chart-title.scss';

export default defineComponent({
  name: 'ProfilingGraphTitle',
  props: {
    activeMode: {
      type: String as PropType<ViewModeType>,
      required: true
    },
    textDirection: {
      type: String as PropType<DirectionType>,
      default: 'ltr'
    },
    isCompared: {
      type: Boolean,
      default: false
    }
  },
  emits: ['modeChange', 'textDirectionChange', 'keywordChange', 'download'],
  setup(props, { emit }) {
    const downloadTypeMaps = [
      'png',
      //  'json',
      'pprof'
      //  'html'
    ];

    const keyword = ref('');

    const viewModeList = computed<ViewModeItem[]>(() => {
      const list = [
        { id: ViewModeType.Table, icon: 'table' },
        { id: ViewModeType.Combine, icon: 'mc-fenping' },
        { id: ViewModeType.Flame, icon: 'mc-flame' }
      ];

      if (!props.isCompared) {
        list.push({ id: ViewModeType.Topo, icon: 'Component' });
      }

      return list;
    });

    /** 切换视图模式 */
    const handleModeChange = (val: ViewModeType) => {
      emit('modeChange', val);
    };
    const handleEllipsisDirectionChange = (val: DirectionType) => {
      emit('textDirectionChange', val);
    };
    const handleKeywordChange = debounce(300, async () => {
      emit('keywordChange', keyword.value);
    });
    const menuClick = (type: string) => {
      emit('download', type);
    };

    return {
      keyword,
      downloadTypeMaps,
      viewModeList,
      handleModeChange,
      handleEllipsisDirectionChange,
      handleKeywordChange,
      menuClick
    };
  },
  render() {
    return (
      <div class='profiling-chart-title'>
        <div class='view-mode button-group'>
          {this.viewModeList.map(mode => (
            <div
              class={`button-group-item ${this.activeMode === mode.id ? 'active' : ''}`}
              onClick={() => this.handleModeChange(mode.id)}
            >
              <i class={`icon-monitor icon-${mode.icon}`}></i>
            </div>
          ))}
        </div>
        <Input
          type='search'
          v-model={this.keyword}
          onInput={this.handleKeywordChange}
        />
        <div class='ellipsis-direction button-group'>
          <div
            class={`button-group-item ${this.textDirection === 'ltr' ? 'active' : ''}`}
            onClick={() => this.handleEllipsisDirectionChange('ltr')}
          >
            <i class='icon-monitor icon-AB'></i>
          </div>
          <div
            class={`button-group-item ${this.textDirection === 'rtl' ? 'active' : ''}`}
            onClick={() => this.handleEllipsisDirectionChange('rtl')}
          >
            <i class='icon-monitor icon-YZ'></i>
          </div>
        </div>
        {/* <div class='download-button'>
          <i class='icon-monitor icon-xiazai1'></i>
        </div> */}

        <Dropdown
          placement='bottom-end'
          v-slots={{
            content: () => (
              <Dropdown.DropdownMenu>
                {this.downloadTypeMaps.map(item => (
                  <Dropdown.DropdownItem
                    class='profiling-view-download-menu-item'
                    onClick={() => this.menuClick(item)}
                  >
                    {item}
                  </Dropdown.DropdownItem>
                ))}
              </Dropdown.DropdownMenu>
            )
          }}
        >
          <div class='download-button'>
            <i class='icon-monitor icon-xiazai1'></i>
          </div>
        </Dropdown>
      </div>
    );
  }
});
