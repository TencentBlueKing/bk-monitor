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
import { Component, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { VariablesService } from 'monitor-ui/chart-plugins/utils/variable';

import CompareTime from './compare-time';
import GroupBy from './group-by';
import { type IGroupOption, type IListItem, ETypeSelect } from './utils';

import type { IPanelModel, IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './group-compare-select.scss';

const VALUE_KEY = 'groups';

interface IProps {
  active?: ETypeSelect;
  groupOptions?: IGroupOption[];
  groupOptionsLimitEnabled?: boolean;
  groups?: string[];
  hasGroupOptions?: boolean;
  limit?: number;
  limitSortMethod?: string;
  limitSortMethods?: IListItem[];
  metricCalType?: string;
  metricCalTypes?: IListItem[];
  pageId?: string;
  panel?: IPanelModel;
  sceneId?: string;
  sceneType?: string;
  timeValue?: string[];
  onGroupChange?: (val: string[]) => void;
  onLimitChange?: (val: number) => void;
  onLimitSortMethodChange?: (val: string) => void;
  onMetricCalTypeChange?: (val: string) => void;
  onTimeCompareChange?: (val: string[]) => void;
  onTypeChange?: (val: ETypeSelect) => void;
  onVariablesChange?: (val: object) => void;
}

@Component
export default class GroupCompareSelect extends tsc<IProps> {
  @Prop({ type: Object }) panel: IPanelModel;
  /** 场景id */
  @Prop({ default: 'host', type: String }) sceneId: string;
  /** 场景类型 */
  @Prop({ default: 'detail', type: String }) sceneType: string;
  /** 页签id */
  @Prop({ default: '', type: String }) pageId: string;
  /** 外部传入回来显值 */
  @Prop({ type: Array, default: () => [] }) groups: string[];
  /* 是否包含group可选项（有上层传入，无需调用接口） */
  @Prop({ type: Boolean, default: false }) hasGroupOptions: boolean;
  /* groups可选项 */
  @Prop({ type: Array, default: () => [] }) groupOptions: IGroupOption[];
  @Prop({ type: Array, default: () => [] }) limitSortMethods: IListItem[];
  /* 时间对比数据 */
  @Prop({ type: Array, default: () => [] }) timeValue: string[];
  // 当前激活的tab
  @Prop({ type: String, default: '' }) active: ETypeSelect;
  @Prop({ type: String, default: '' }) limitSortMethod: string;
  @Prop({ type: Number, default: 1 }) limit: number;
  @Prop({ type: String, default: '' }) metricCalType: string;
  @Prop({ type: Array, default: () => [] }) metricCalTypes: IListItem[];
  /* group by 是否默认开启limit */
  @Prop({ type: Boolean, default: false }) groupOptionsLimitEnabled: boolean;

  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;

  typeSelects = {
    [ETypeSelect.compare]: {
      name: window.i18n.tc('对比'),
      width: 96,
    },
    [ETypeSelect.group]: {
      name: 'Group by',
      width: 129,
    },
  };
  typeSelected = ETypeSelect.compare;

  localGroupOptions: IGroupOption[] = [];

  groupByVariables = {
    metric_cal_type: '',
    limit_sort_method: '',
    limit: 1,
    group_by_limit_enabled: false,
  };

  /** 接口数据 */
  get currentPanel() {
    if (this.panel) return this.panel;
    return {
      targets: [
        {
          api: 'scene_view.getSceneViewDimensions',
          data: {
            scene_id: this.sceneId,
            type: this.sceneType,
            id: this.pageId,
            bk_biz_id: this.viewOptions.filters?.bk_biz_id || this.$store.getters.bizId,
          },
          field: {
            id: VALUE_KEY,
          },
        },
      ],
    };
  }

  get getGroupOptions() {
    return this.hasGroupOptions
      ? this.groupOptions.map(item => ({
          id: item?.id || item?.value || '',
          name: item?.name || item?.text || '',
          top_limit_enable: item?.top_limit_enable || this.groupOptionsLimitEnabled,
        }))
      : this.localGroupOptions;
  }

  get getMetricCalTypes() {
    return this.metricCalTypes.map(item => ({
      id: item?.id || item?.value || '',
      name: item?.name || item?.text || '',
    }));
  }

  @Watch('active', { immediate: true })
  handleWatchActive(val: ETypeSelect) {
    if (this.typeSelected !== val) {
      this.typeSelected = val;
    }
  }

  created() {
    this.groupByVariables = {
      ...this.groupByVariables,
      metric_cal_type: this.metricCalType,
      limit_sort_method: this.limitSortMethod,
      limit: this.limit,
    };
    if (!this.hasGroupOptions) {
      this.handleGetOptionsData();
    }
  }

  handleChange() {
    if (this.typeSelected === ETypeSelect.compare) {
      this.typeSelected = ETypeSelect.group;
    } else {
      this.typeSelected = ETypeSelect.compare;
    }
    this.$emit('typeChange', this.typeSelected);
  }

  /** 解析api 格式： commons.getTopoTree (模块.api)的字符串 , 返回对应的api*/
  handleGetApi(expr: string) {
    return expr.split('.').reduce((data, curKey) => data[curKey], this.$api);
  }
  /** 获取可选项数据 */
  handleGetOptionsData() {
    const target = this.currentPanel?.targets[0];
    const api = target?.api;
    const variablesService = new VariablesService({
      ...this.viewOptions.filters,
    });
    const params: Record<string, any> = variablesService.transformVariables(target.data);
    this.handleGetApi(api)?.(params).then(data => {
      this.localGroupOptions = data;
    });
  }

  handleGroupsChange(val) {
    this.$emit('groupChange', val);
  }
  handleLimitTypeChange(val) {
    this.$emit('metricCalTypeChange', val);
    this.groupByVariables.metric_cal_type = val;
    this.handleVariablesChange();
  }
  handleMethodChange(val) {
    this.$emit('limitSortMethodChange', val);
    this.groupByVariables.limit_sort_method = val;
    this.handleVariablesChange();
  }
  handleLimitChange(val) {
    this.$emit('limitChange', val);
    this.groupByVariables.limit = val;
    this.handleVariablesChange();
  }
  handleTimeValueChange(val) {
    this.$emit('timeCompareChange', val);
  }
  handleGroupByLimitEnabledChange(val) {
    this.groupByVariables.group_by_limit_enabled = val;
    this.handleVariablesChange();
  }

  handleVariablesChange() {
    this.$emit('variablesChange', this.groupByVariables);
  }

  render() {
    return (
      <div class='common-page___group-compare-select'>
        <div
          style={{
            width: `${this.typeSelects[this.typeSelected].width}px`,
          }}
          class='select-type-wrap'
          onClick={this.handleChange}
        >
          <span class='select-type-name'>{this.typeSelects[this.typeSelected].name}</span>
          <span class='contrast-switch'>
            <i class='icon-monitor icon-switch' />
          </span>
        </div>
        <div class='group-compare-wrap'>
          {this.typeSelected === ETypeSelect.compare ? (
            <CompareTime
              value={this.timeValue}
              onChange={this.handleTimeValueChange}
            />
          ) : (
            <GroupBy
              groupBy={this.groups}
              groupOptions={this.getGroupOptions}
              limit={this.limit}
              limitType={this.metricCalType}
              limitTypes={this.getMetricCalTypes}
              method={this.limitSortMethod}
              methods={this.limitSortMethods}
              onChange={this.handleGroupsChange}
              onGroupByLimitEnabledChange={this.handleGroupByLimitEnabledChange}
              onLimitChange={this.handleLimitChange}
              onLimitType={this.handleLimitTypeChange}
              onMethodChange={this.handleMethodChange}
            />
          )}
        </div>
      </div>
    );
  }
}
