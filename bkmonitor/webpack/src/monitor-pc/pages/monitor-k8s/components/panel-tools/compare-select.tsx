import type { VNode } from 'vue';

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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { modifiers, Component as tsc } from 'vue-tsx-support';

import { deepClone } from 'monitor-common/utils/utils';

import { type PanelToolsType, COMPARE_KEY, COMPARE_LIST, COMPARE_TIME_OPTIONS } from '../../typings/panel-tools';
import TargetCompareSelect from './target-compare-select';

import type { IOption } from '../../typings';
import type { IViewOptions, PanelModel } from 'monitor-ui/chart-plugins/typings';

import './compare-select.scss';

interface IEvents {
  onMetricChange: string[];
  onTargetChange: IViewOptions;
  onTimeChange: string[];
  onTypeChange: PanelToolsType.CompareId;
}
interface IProps {
  compareListEnable?: PanelToolsType.CompareId[];
  compareTimeOptions?: PanelToolsType.ICompareListItem[];
  curTarget?: string;
  metricOptions?: IOption[];
  metricValue?: string[];
  needCompare?: boolean;
  needMetricSelect?: boolean;
  needTargetSelect?: boolean;
  panel?: PanelModel;
  targetOptions?: IOption[];
  targetValue?: IViewOptions;
  timeValue: string[];
  type: PanelToolsType.CompareId;
  zIndex?: number;
}
@Component
export default class CompareSelect extends tsc<IProps, IEvents> {
  /** 面板启用的的对比方式 */
  @Prop({
    default: () => COMPARE_KEY,
    type: Array,
    validator: val => val.every(item => COMPARE_KEY.includes(item)),
  })
  compareListEnable: PanelToolsType.CompareId[];
  /** 时间对比可选列表 */
  @Prop({
    default: () => COMPARE_TIME_OPTIONS,
    type: Array,
  })
  compareTimeOptions: PanelToolsType.ICompareListItem[];
  /** 目标可选项 */
  @Prop({ default: () => [], type: Array }) targetOptions: IOption[];
  /** 指标可选项 */
  @Prop({ default: () => [], type: Array }) metricOptions: IOption[];
  /** 启用目标对比下拉 */
  @Prop({ default: false, type: Boolean }) needTargetSelect: boolean;
  /** 启用指标对比下拉 */
  @Prop({ default: false, type: Boolean }) needMetricSelect: boolean;
  /** 对比类型 */
  @Prop({ default: 'none', type: String }) type: PanelToolsType.CompareId;
  /** 时间对比值 */
  @Prop({ default: () => [], type: Array }) timeValue: string[];
  /** 目标对比值 */
  @Prop({ default: () => ({}), type: Object }) targetValue: IViewOptions;
  /** 指标对比值 */
  @Prop({ default: () => [], type: Array }) metricValue: string[];
  /** 接口数据 */
  @Prop({ type: Object }) panel: PanelModel;
  /** 目标对比的参考目标 */
  @Prop({ type: [String, Number], default: '' }) curTarget: string;
  /* 启用对比 */
  @Prop({ type: Boolean, default: true }) needCompare: boolean;
  @Prop({ type: Number, default: undefined }) zIndex: number;

  /** 对比类型 */
  localType: PanelToolsType.CompareId = 'none';
  /** 时间对比值 */
  localTimeValue: string[] = [];
  /** 目标对比值 */
  localTargetValue: string[] = [];
  /** 指标对比值 */
  localMetricValue: string[] = [];

  /** 所有的对比方式 */
  compareList: PanelToolsType.ICompareListItem[] = COMPARE_LIST;

  /** 自定义时间输入框展示 */
  showCustomTime = false;
  /** 自定义时间 */
  customTimeVal = '';

  /** 自定义添加的时间可选列表 */
  compareTimeCustomList = [];

  get compareFieldsSort() {
    const compareFieldsSort = this.panel.targets?.[0]?.compareFieldsSort;
    return compareFieldsSort.length ? compareFieldsSort : null;
  }

  /* 目标对比时如果此属性有值时需要按照当前的数据配置字典 */
  get queryFileds(): { [propName: string]: string } {
    return this.panel?.targets?.[0]?.fields || {};
  }

  /** 启用的对比下拉 */
  get compareEnable() {
    return this.compareList.filter(item => this.compareListEnable.includes(item.id));
  }

  /** 时间可选项的下拉数据 */
  get compareTimeList() {
    const allList = [...this.compareTimeOptions, ...this.compareTimeCustomList];
    const allListMap = new Map();
    allList.forEach(item => {
      allListMap.set(item.id, item.name);
    });
    if (this.localType === 'time') {
      const value = this.localTimeValue;
      value.forEach(item => {
        if (!allListMap.has(item))
          allList.push({
            id: item,
            name: item,
          });
      });
    }
    return allList;
  }

  /** 当前要进行对比的参考对象id 根据映射关系生成 */
  get currentSelectTargetId() {
    return this.panel.targets[0].handleCreateItemId(this.targetValue.filters, true);
  }

  /** 排除选中的主机 */
  get targetOptionsFilter() {
    const filterDict = this.targetValue.filters;
    if (!filterDict) return [];
    if (this.currentSelectTargetId) return this.targetOptions.filter(item => item.id !== this.currentSelectTargetId);
    return Object.keys(this.queryFileds).length
      ? this.targetOptions.filter(item => item.id !== `${filterDict[this.queryFileds.id]}`)
      : this.targetOptions.filter(item => item.id !== filterDict.bk_host_id);
  }

  @Watch('timeValue', { immediate: true })
  timeValueChange() {
    this.localTimeValue = deepClone(this.timeValue);
  }
  @Watch('targetValue', { immediate: true })
  targetValueChange() {
    const viewOptions = deepClone(this.targetValue) as IViewOptions;

    this.localTargetValue = viewOptions.compares?.targets?.map(item =>
      this.panel.targets?.[0]?.handleCreateItemId(item, true)
    );
    // this.localTargetValue = viewOptions.compares?.targets?.filter(item => item).map(item => item.bk_host_id);
  }
  @Watch('metricValue', { immediate: true })
  metricValueChange() {
    this.localMetricValue = deepClone(this.metricValue);
  }
  @Watch('type', { immediate: true })
  typeChange() {
    this.localType = this.type;
  }
  @Watch('needCompare')
  handleNeedCompare(v: boolean) {
    if (!v) {
      /* 禁用对比方式需要重置对比方式 */
      this.localType = 'none';
      this.handleTypeChange();
    }
  }

  /**
   * @description: 对比数据变更
   * @param {PanelToolsType} type 对比类型
   * @return {*}
   */
  @Emit('compareChange')
  handleCompareChange(
    type: PanelToolsType.CompareId,
    val?: PanelToolsType.CompareValue<PanelToolsType.CompareId>
  ): PanelToolsType.Compare {
    const defaultDataMap: PanelToolsType.ICompareValueType = {
      none: true,
      target: (val as PanelToolsType.CompareValue<'target'>) || [],
      time: (val as PanelToolsType.CompareValue<'time'>) || [],
      metric: (val as PanelToolsType.CompareValue<'metric'>) || [],
    };
    const data = {
      type,
      value: defaultDataMap[type],
    };
    return data;
  }

  /**
   * @description: 处理bk-input事件不触发vue-tsx-support的modifiers问题
   * @param {Event} evt 事件
   * @param {*} handler 要执行的执行的方法
   */
  handleModifiers(evt: Event, handler: (evt: Event) => void) {
    modifiers.enter(handler).call(this, evt);
  }
  /**
   * @description: 自定义按下回车
   */
  handleAddCustomTime() {
    const regular = /^([1-9][0-9]+)+(m|h|d|w|M|y)$/;
    const str = this.customTimeVal.trim();
    if (regular.test(str)) {
      this.handleAddCustom(str);
    } else {
      this.$bkMessage({
        theme: 'warning',
        message: this.$t('按照提示输入'),
        offsetY: 40,
      });
    }
  }

  /**
   * @description: 添加自定义时间对比
   * @param {*} str
   */
  handleAddCustom(str) {
    const timeValue = this.localTimeValue;
    if (this.compareTimeList.every(item => item.id !== str)) {
      this.compareTimeCustomList.push({
        id: str,
        name: str,
      });
    }
    !timeValue.includes(str) && timeValue.push(str);
    this.showCustomTime = false;
    this.customTimeVal = '';
    this.handleTimeChange(this.localTimeValue);
  }

  /**
   * @description: 时间下拉收起
   * @param {boolean} val
   */
  handleSelectToggle(val: boolean) {
    if (!val) {
      this.customTimeVal = '';
      this.showCustomTime = false;
    }
  }

  /**
   * @description: 时间变更
   */
  @Emit('timeChange')
  handleTimeChange(list: string[]) {
    return list;
  }

  @Emit('metricChange')
  handleMetricChange(list: string[]) {
    return list;
  }

  @Emit('targetChange')
  handleTargetChange(list: string[]): IViewOptions {
    const targetCheckedList = list.reduce((total, id) => {
      const item = this.targetOptions.find(item => item.id === id);
      const value = this.panel.targets?.[0]?.handleCreateCompares(item);
      total.push({ ...value });
      return total;
    }, []);
    const viewOptions: IViewOptions = {
      ...this.targetValue,
      compares: {
        targets: targetCheckedList,
      },
    };
    return viewOptions;
  }

  /** 切换类型 */
  @Emit('typeChange')
  handleTypeChange() {
    return this.localType;
  }

  /** 通用型下拉选择 */
  commonSelectTpl() {
    const optionsMap = {
      metric: this.metricOptions,
      target: this.targetOptionsFilter,
    };
    const localValueMap = {
      metric: this.localMetricValue,
      target: this.localTargetValue,
    };
    const eventMap = {
      metric: this.handleMetricChange,
      target: this.handleTargetChange,
    };
    const options = optionsMap[this.localType] || [];
    const localValue = localValueMap[this.localType];
    const handler = eventMap[this.localType];
    return (
      <bk-select
        class='bk-select-simplicity compare-select'
        behavior='simplicity'
        value={localValue}
        zIndex={this.zIndex}
        multiple
        searchable
        onClear={() => handler([])}
        onSelected={handler}
      >
        {options.map(item => (
          <bk-option
            id={item.id}
            key={item.id}
            name={item.name}
          />
        ))}
      </bk-select>
    );
  }

  /** 各对比类型的选择器 */
  get handleRenderTpl() {
    const tplMap: { [key in PanelToolsType.CompareId]: VNode } = {
      none: undefined,
      metric: this.needMetricSelect ? this.commonSelectTpl() : undefined,
      target: this.needTargetSelect ? (
        <span class='compare-target-wrap'>
          {this.curTarget && (
            <span
              class='compare-target-ip'
              v-bk-overflow-tips
            >
              {this.curTarget}
            </span>
          )}
          {/* <bk-tag-input
          class="bk-tag-input-simplicity"
          value={this.localTargetValue}
          list={this.targetOptionsFilter}
          trigger="focus"
          allow-create
          has-delete-icon
          allow-auto-match
          placeholder={this.$t('选择目标')}
          onChange={this.handleTargetChange} /> */}
          <span class='target-compare-select'>
            <TargetCompareSelect
              list={this.targetOptionsFilter as any}
              value={this.localTargetValue}
              onChange={this.handleTargetChange}
            />
          </span>
          {/* {this.commonSelectTpl()} */}
        </span>
      ) : undefined,
      time: (
        <bk-select
          class='bk-select-simplicity compare-select time-compare-select'
          v-model={this.localTimeValue}
          behavior='simplicity'
          zIndex={this.zIndex}
          multiple
          onClear={() => this.handleTimeChange([])}
          onSelected={list => this.handleTimeChange(list)}
          onToggle={this.handleSelectToggle}
        >
          {this.compareTimeList.map(item => (
            <bk-option
              id={item.id}
              key={item.id}
              name={item.name}
            />
          ))}
          <div class='compare-time-select-custom'>
            {this.showCustomTime ? (
              <span class='time-input-wrap'>
                <bk-input
                  v-model={this.customTimeVal}
                  size='small'
                  onKeydown={(_, evt) => this.handleModifiers(evt, this.handleAddCustomTime)}
                />
                <span
                  class='help-icon icon-monitor icon-mc-help-fill'
                  v-bk-tooltips={this.$t('自定义输入格式: 如 1w 代表一周 m 分钟 h 小时 d 天 w 周 M 月 y 年')}
                />
              </span>
            ) : (
              <span
                class='custom-text'
                onClick={() => (this.showCustomTime = !this.showCustomTime)}
              >
                {this.$t('自定义')}
              </span>
            )}
          </div>
        </bk-select>
      ),
    };
    return tplMap[this.localType];
  }

  render() {
    return (
      <span class='compare-select-wrap'>
        <span class='compare-select-label'>{this.$t('对比方式')}</span>
        <bk-select
          class='bk-select-simplicity compare-select'
          v-model={this.localType}
          behavior='simplicity'
          clearable={false}
          disabled={!this.needCompare}
          zIndex={this.zIndex}
          onSelected={this.handleTypeChange}
        >
          {this.compareEnable.map(item => (
            <bk-option
              id={item.id}
              key={item.id}
              name={item.name}
            />
          ))}
        </bk-select>
        <span class='compare-select-content'>{this.handleRenderTpl}</span>
      </span>
    );
  }
}
