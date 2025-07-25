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
import { Component, Emit, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { VariablesService } from 'monitor-ui/chart-plugins/utils/variable';

import CustomSelect from '../../../../components/custom-select/custom-select';
import { handleTransformToTimestamp } from '../../../../components/time-range/utils';

import type { TimeRangeType } from '../../../../components/time-range/time-range';
import type { IOption } from '../../typings';
import type { IPanelModel, IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './group-select.scss';

const VALUE_KEY = 'groups';
export interface IEvents {
  onChange: string[];
}

export interface IProps {
  pageId: string;
  panel?: IPanelModel;
  scencId?: string;
  sceneType?: string;
  value?: string[];
}
@Component
export default class GroupSelect extends tsc<IProps, IEvents> {
  @Prop({ type: Object }) panel: IPanelModel;
  /** 场景id */
  @Prop({ default: 'host', type: String }) scencId: string;
  /** 场景类型 */
  @Prop({ default: 'detail', type: String }) sceneType: string;
  /** 页签id */
  @Prop({ default: '', type: String }) pageId: string;
  /** 外部传入回来显值 */
  @Prop({ type: Array }) value: string[];

  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  /** 选中的groups */
  localValue: string[] = [];

  /** 可选项数据 */
  options: IOption[] = [];

  /** 接口数据 */
  get currentPanel() {
    if (this.panel) return this.panel;
    return {
      targets: [
        {
          api: 'scene_view.getSceneViewDimensions',
          data: {
            scene_id: this.scencId,
            type: this.sceneType,
            id: this.pageId,
            bk_biz_id: this.viewOptions.filters?.bk_biz_id || this.$store.getters.bizId,
            start_time: '$start_time',
            end_time: '$end_time',
          },
          field: {
            id: VALUE_KEY,
          },
        },
      ],
    };
  }

  created() {
    this.handleGetOptionsData();
  }

  @Watch('value', { immediate: true })
  valueUpdate() {
    if (this.value) {
      this.localValue = [...(this.value || [])];
    }
  }
  /** 解析api 格式： commons.getTopoTree (模块.api)的字符串 , 返回对应的api*/
  handleGetApi(expr: string) {
    return expr.split('.').reduce((data, curKey) => data[curKey], this.$api);
  }
  /** 获取可选项数据 */
  handleGetOptionsData() {
    const target = this.currentPanel?.targets[0];
    const api = target?.api;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const variablesService = new VariablesService({
      ...this.viewOptions.filters,
      start_time: startTime,
      end_time: endTime,
    });
    const params: Record<string, any> = variablesService.transformVariables(target.data);
    this.handleGetApi(api)?.(params).then(data => {
      this.options = data;
    });
  }

  /** 添加、删除 */
  @Emit('change')
  handleAddGroups(data?) {
    data && (this.localValue = data);
    return [...this.localValue];
  }

  /** 处理选中的名称展示 */
  handleDisplayName(id) {
    return this.options.find(item => item.id === id)?.name;
  }

  /** 删除操作 */
  handleDeleteItem(index: number) {
    this.localValue.splice(index, 1);
    this.handleAddGroups();
  }

  render() {
    return (
      <div class='group-select-wrap'>
        <span class='group-select-label'>Groups :</span>
        <span class='group-select-main'>
          {this.localValue.map((item, index) => (
            <span
              key={index}
              class='group-item'
              v-bk-tooltips={{
                content: item,
                zIndex: 9999,
                boundary: document.body,
                allowHTML: false,
              }}
            >
              {this.handleDisplayName(item)}
              <i
                class='icon-monitor icon-mc-close'
                onClick={() => this.handleDeleteItem(index)}
              />
            </span>
          ))}
          <CustomSelect
            class='group-add-btn'
            options={this.options}
            value={this.localValue}
            multiple
            onSelected={this.handleAddGroups}
          >
            {this.options.map(opt => (
              <bk-option
                id={opt.id}
                key={opt.id}
                name={opt.name}
              >
                <span
                  v-bk-tooltips={{
                    content: opt.id,
                    placement: 'right',
                    zIndex: 9999,
                    boundary: document.body,
                    allowHTML: false,
                  }}
                >
                  {opt.name}
                </span>
              </bk-option>
            ))}
          </CustomSelect>
        </span>
      </div>
    );
  }
}
