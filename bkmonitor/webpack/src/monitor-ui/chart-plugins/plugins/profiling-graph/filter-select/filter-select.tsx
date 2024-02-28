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
import { Component, Emit, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { queryLabels, queryLabelValues } from '../../../../../monitor-api/modules/apm_profile';
import { TimeRangeType } from '../../../../../monitor-pc/components/time-range/time-range';
import { handleTransformToTimestamp } from '../../../../../monitor-pc/components/time-range/utils';
import { getPopoverWidth } from '../../../../../monitor-pc/utils';

import './filter-select.scss';

interface IListItem {
  id: string;
  name: string;
}

interface IFilterPanel {
  title: string; // 变量的标题
  options: IListItem[]; // 变量的配置
  value?: string[]; // 值
}

interface IFilterSelectProps {
  appName: string;
  serviceName: string;
}

interface IFilterSelectEvents {
  onFilterChange: Record<string, string>;
  onDiffChange: Record<string, string>;
  onDiffModeChange: boolean;
}

@Component
export default class FilterSelect extends tsc<IFilterSelectProps, IFilterSelectEvents> {
  @Prop({ default: '', type: String }) appName: string;
  @Prop({ default: '', type: String }) serviceName: string;

  @Ref() filterKeySelectRef: Select;
  @Ref() diffKeySelectRef: Select;

  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;

  // 是否开启对比模式
  enableDiffMode = false;
  // 过滤key
  labelList: IListItem[] = [];
  // 新增 key 状态
  isShowAddFilter = false;
  isShowAddDiff = false;
  localFilterPanel: IFilterPanel[] = [];
  localDiffPanel: IFilterPanel[] = [];

  get listenChange() {
    const { appName, serviceName } = this;
    return { appName, serviceName };
  }

  get addKeyprops() {
    return Object.assign(
      {
        value: [],
        'popover-min-width': 240,
        'popover-width': getPopoverWidth(this.labelList) || void 0,
        'popover-options': {
          boundary: 'window',
          onHide: () => {
            this.isShowAddFilter = false;
            this.isShowAddDiff = false;
            return true;
          }
        },
        searchable: true
      },
      this.$attrs
    );
  }

  @Watch('listenChange', { deep: true })
  async handleQueryParamsChange() {
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const params = {
      app_name: this.appName,
      service_name: this.serviceName,
      start: startTime * Math.pow(10, 6),
      end: endTime * Math.pow(10, 6)
    };
    const labels = await queryLabels(params).catch(() => ({ label_keys: [] }));
    this.labelList = (labels.label_keys || []).map(item => ({ id: item, name: item }));
  }

  @Watch('timeRange', { deep: true })
  handleTimeRangeChange() {
    this.handleQueryParamsChange();
  }

  @Emit('filterChange')
  handleFilterChange(val) {
    return val;
  }

  @Emit('diffChange')
  handleDiffChange(val) {
    return val;
  }

  @Emit('diffModeChange')
  handleDiffModeChange(val) {
    return val;
  }

  // 更新过滤条件
  handleSelectValueChange(mode: string) {
    const labelValues = {};
    const panel = mode === 'filter' ? this.localFilterPanel : this.localDiffPanel;
    panel.forEach(item => {
      if (item.value.length) {
        labelValues[item.title] = item.value.join(',');
      }
    });
    mode === 'filter' ? this.handleFilterChange(labelValues) : this.handleDiffChange(labelValues);
  }

  handleShowDropDown(mode) {
    this[`${mode}KeySelectRef`].show();
    mode === 'filter' ? (this.isShowAddFilter = true) : (this.isShowAddDiff = true);
  }

  // 获取过滤条件候选值
  async handleAddFilterChange(val: string, mode: string) {
    const panel = mode === 'filter' ? this.localFilterPanel : this.localDiffPanel;
    if (panel.some(item => item.title === val) || !val.length) return false;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const params = {
      app_name: this.appName,
      service_name: this.serviceName,
      start: startTime * Math.pow(10, 6),
      end: endTime * Math.pow(10, 6),
      label_key: val
    };
    const data = await queryLabelValues(params).catch(() => ({ label_values: [] }));
    const options = (data.label_values || []).map(val => ({ id: val, name: val }));
    (mode === 'filter' ? this.localFilterPanel : this.localDiffPanel).push({
      title: val,
      options,
      value: []
    });
  }

  render() {
    const getSelectorTpl = mode => {
      const panel = mode === 'filter' ? this.localFilterPanel : this.localDiffPanel;

      return [
        panel.map(item => (
          <span class='filter-var-select-wrap'>
            <span class='filter-var-label'>{item.title}</span>
            <span class='filter-var-tag-input'>
              <bk-tag-input
                v-model={item.value}
                list={item.options}
                trigger='focus'
                has-delete-icon
                clearable
                allow-create
                allow-auto-match
                placeholder={this.$t('输入')}
                on-change={() => this.handleSelectValueChange(mode)}
              ></bk-tag-input>
            </span>
          </span>
        )),
        <span class={['filter-add-btn', { active: mode === 'filter' ? this.isShowAddFilter : this.isShowAddDiff }]}>
          <i
            key={mode}
            class='icon-monitor icon-mc-add'
            onClick={() => this.handleShowDropDown(mode)}
          ></i>
          <bk-select
            class='bk-select-wrap'
            ref={`${mode}KeySelectRef`}
            onChange={val => this.handleAddFilterChange(val, mode)}
            {...{
              props: this.addKeyprops
            }}
          >
            {this.labelList.map(opt => (
              <bk-option
                id={opt.id}
                name={opt.name}
              >
                <span
                  v-bk-tooltips={{
                    content: opt.id,
                    placement: 'right',
                    zIndex: 9999,
                    boundary: document.body,
                    allowHTML: false
                  }}
                >
                  {opt.name}
                </span>
              </bk-option>
            ))}
          </bk-select>
        </span>
      ];
    };

    return (
      <div class='profiling-filter-select-wrap'>
        <div class='filter-var-select-group'>
          <span class='filter-var-select-group-label'>Filters：</span>
          <div class='filter-var-select-main'>{getSelectorTpl('filter')}</div>
          <div class='diff-mode-btn'>
            <span>{this.$t('对比模式')}</span>
            <bk-switcher
              theme='primary'
              size='small'
              v-model={this.enableDiffMode}
              onChange={this.handleDiffModeChange}
            />
          </div>
        </div>
        {this.enableDiffMode ? (
          <div class='filter-var-select-group diff-select-group'>
            <span class='filter-var-select-group-label'>Comparison：</span>
            <div
              class='filter-var-select-main'
              style='margin-left: -24px'
            >
              {getSelectorTpl('diff')}
            </div>
          </div>
        ) : (
          ''
        )}
      </div>
    );
  }
}
