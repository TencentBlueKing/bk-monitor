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

import { type PropType, computed, defineComponent } from 'vue';

import { Dropdown, Input } from 'bkui-vue';
import { type ViewModeItem, ViewModeType } from 'monitor-ui/chart-plugins/typings/profiling-graph';
import { debounce } from 'throttle-debounce';
import { useI18n } from 'vue-i18n';

import type { DirectionType } from '../../../../typings';

import './chart-title.scss';

export default defineComponent({
  name: 'ProfilingGraphTitle',
  props: {
    activeMode: {
      type: String as PropType<ViewModeType>,
      required: true,
    },
    textDirection: {
      type: String as PropType<DirectionType>,
      default: 'ltr',
    },
    isCompared: {
      type: Boolean,
      default: false,
    },
    keyword: {
      type: String,
      default: '',
    },
  },
  emits: ['modeChange', 'textDirectionChange', 'update:keyword', 'download'],
  setup(props, { emit }) {
    const { t } = useI18n();

    const viewModeList = computed<ViewModeItem[]>(() => {
      const list = [
        { id: ViewModeType.Table, icon: 'table', label: t('表格') },
        { id: ViewModeType.Combine, icon: 'mc-fenping', label: t('表格和火焰图') },
        { id: ViewModeType.Flame, icon: 'mc-flame', label: t('火焰图') },
      ];

      if (!props.isCompared) {
        list.push({ id: ViewModeType.Topo, icon: 'Component', label: t('功能调用图') });
      }

      return list;
    });

    // 表格火焰图 && 火焰图 展示png下载
    const downloadTypeMaps = computed(() => {
      const baseTypes = ['pprof'];
      if ([ViewModeType.Flame, ViewModeType.Combine].includes(props.activeMode)) {
        baseTypes.unshift('png');
      }
      return baseTypes;
    });

    /** 切换视图模式 */
    const handleModeChange = (val: ViewModeType) => {
      emit('modeChange', val);
    };
    const handleEllipsisDirectionChange = (val: DirectionType) => {
      emit('textDirectionChange', val);
    };
    const handleKeywordChange = debounce(300, async v => {
      emit('update:keyword', v);
    });
    const menuClick = (type: string) => {
      emit('download', type);
    };

    return {
      downloadTypeMaps,
      viewModeList,
      handleModeChange,
      handleEllipsisDirectionChange,
      handleKeywordChange,
      menuClick,
    };
  },
  render() {
    return (
      <div class='profiling-chart-title'>
        <div class='view-mode button-group'>
          {this.viewModeList.map(mode => (
            <div
              key={mode.id}
              class={`button-group-item ${this.activeMode === mode.id ? 'active' : ''}`}
              v-bk-tooltips={{
                content: mode.label,
                placement: 'top',
                delay: 300,
              }}
              onClick={() => this.handleModeChange(mode.id)}
            >
              <i class={`icon-monitor icon-${mode.icon}`} />
            </div>
          ))}
        </div>
        <Input
          clearable={true}
          modelValue={this.keyword}
          type='search'
          onClear={() => this.handleKeywordChange('')}
          onInput={this.handleKeywordChange}
        />
        <div class='ellipsis-direction button-group'>
          <div
            class={`button-group-item ${this.textDirection === 'ltr' ? 'active' : ''}`}
            onClick={() => this.handleEllipsisDirectionChange('ltr')}
          >
            <i class='icon-monitor icon-AB' />
          </div>
          <div
            class={`button-group-item ${this.textDirection === 'rtl' ? 'active' : ''}`}
            onClick={() => this.handleEllipsisDirectionChange('rtl')}
          >
            <i class='icon-monitor icon-YZ' />
          </div>
        </div>
        {/* <div class='download-button'>
          <i class='icon-monitor icon-xiazai1'></i>
        </div> */}

        <Dropdown
          v-slots={{
            content: () => (
              <Dropdown.DropdownMenu>
                {this.downloadTypeMaps.map((item, index) => (
                  <Dropdown.DropdownItem
                    key={index}
                    class='profiling-view-download-menu-item'
                    onClick={() => this.menuClick(item)}
                  >
                    {item}
                  </Dropdown.DropdownItem>
                ))}
              </Dropdown.DropdownMenu>
            ),
          }}
          placement='bottom-end'
        >
          <div class='download-button'>
            <i class='icon-monitor icon-xiazai1' />
          </div>
        </Dropdown>
      </div>
    );
  },
});
