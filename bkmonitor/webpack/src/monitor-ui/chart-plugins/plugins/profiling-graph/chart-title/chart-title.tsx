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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from 'monitor-common/utils/utils';

import { TextDirectionType, ViewModeType } from '../../../typings/profiling-graph';

import './chart-title.scss';

interface IChartTitleEvent {
  onDownload: string;
  onKeywordChange: string;
  onModeChange: ViewModeType;
  onTextDirectionChange: TextDirectionType;
}
interface IChartTitleProps {
  activeMode: ViewModeType;
  isCompared: boolean;
  keyword: string;
  textDirection: TextDirectionType;
}

@Component
export default class ChartTitle extends tsc<IChartTitleProps, IChartTitleEvent> {
  @Prop({ required: true, type: String }) activeMode: string;
  @Prop({ required: true, type: String }) textDirection: string;
  @Prop({ required: true, default: '' }) keyword: string;
  @Prop({ default: false, type: Boolean }) isCompared: boolean;

  get viewModeList() {
    const list = [
      { id: ViewModeType.Table, icon: 'table' },
      { id: ViewModeType.Combine, icon: 'mc-fenping' },
      { id: ViewModeType.Flame, icon: 'mc-flame' },
    ];

    if (!this.isCompared) {
      list.push({ id: ViewModeType.Topo, icon: 'Component' });
    }

    return list;
  }

  // 表格火焰图 && 火焰图 展示png下载
  get downloadTypeMaps() {
    const baseTypes = ['pprof'];
    if ([ViewModeType.Flame, ViewModeType.Combine].includes(this.activeMode as ViewModeType)) {
      baseTypes.unshift('png');
    }
    return baseTypes;
  }

  @Emit('modeChange')
  handleModeChange(val: ViewModeType) {
    return val;
  }

  @Emit('textDirectionChange')
  handleTextDirectionChange(val: TextDirectionType) {
    return val;
  }

  @Debounce(300)
  @Emit('keywordChange')
  handleKeywordChange() {
    return this.keyword;
  }

  @Emit('download')
  handleDownload(type: string) {
    return type;
  }

  render() {
    return (
      <div class='profiling-chart-title'>
        <div class='view-mode button-group'>
          {this.viewModeList.map(mode => (
            <div
              key={mode.id}
              class={`button-group-item ${this.activeMode === mode.id ? 'active' : ''}`}
              onClick={() => this.handleModeChange(mode.id)}
            >
              <i class={`icon-monitor icon-${mode.icon}`} />
            </div>
          ))}
        </div>
        <bk-input
          v-model={this.keyword}
          right-icon='bk-icon icon-search'
          clearable
          onInput={this.handleKeywordChange}
        />
        <div class='ellipsis-direction button-group'>
          {Object.values(TextDirectionType).map(item => (
            <div
              key={item}
              class={`button-group-item ${item === this.textDirection ? 'active' : ''}`}
              onClick={() => this.handleTextDirectionChange(item)}
            >
              <i class={`icon-monitor icon-${item === TextDirectionType.Ltr ? 'AB' : 'YZ'}`} />
            </div>
          ))}
        </div>

        <bk-dropdown-menu
          class='option-dropdown-menu'
          align='right'
        >
          <div slot='dropdown-trigger'>
            <div class='download-button'>
              <i class='icon-monitor icon-xiazai1' />
            </div>
          </div>
          <ul
            class='bk-dropdown-list'
            slot='dropdown-content'
          >
            {this.downloadTypeMaps.map(item => (
              <li
                key={item}
                class='profiling-view-download-menu-item'
                onClick={() => this.handleDownload(item)}
              >
                <a class='profiling-view-download-menu-item'>{item}</a>
              </li>
            ))}
          </ul>
        </bk-dropdown-menu>
      </div>
    );
  }
}
