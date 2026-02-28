/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, Emit, Prop, Ref, InjectReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import { Debounce, deepClone } from 'monitor-common/utils';
import CycleInput from 'monitor-pc/components/cycle-input/cycle-input';

import { METHOD_LIST } from '../../../../../../../../../constant/constant';
import FunctionSelect from '../../../../../../../../strategy-config/strategy-config-set-new/monitor-data/function-select';
import { matchRuleFn } from '../../../../../../utils';
import type { ICustomTsFields, IUnitItem } from '../../../../../../../service';
import { DEFAULT_HEIGHT_OFFSET, type IGroupListItem, NULL_LABEL, type RequestHandlerMap } from '../../../../../../type';

import './index.scss';

/** 组件 Props 接口定义 */
interface IProps {
  /** 指标数据 */
  metricData: IMetricItem;
  /** 单位列表 */
  unitList: IUnitItem[];
  /** 分组选择列表 */
  groupSelectList: { id: number; name: string }[];
  /** 维度表 */
  dimensionTable: ICustomTsFields['dimensions'];
  /** 所有数据预览 */
  // allDataPreview: Record<string, any>;
  /** 分组映射表 */
  groupsMap: Map<string, IGroupListItem>;
  /** 默认分组信息 */
  defaultGroupInfo: { id: number; name: string };
}

/** 指标项类型定义 */
type IMetricItem = ICustomTsFields['metrics'][number] & { selection: boolean; isNew?: boolean; error?: string };

@Component
export default class MetricDetail extends tsc<IProps, any> {
  @Prop({ default: () => {} }) metricData: IProps['metricData'];
  @Prop({ default: () => [] }) unitList: IProps['unitList'];
  @Prop({ default: () => [], type: Array }) groupSelectList: IProps['groupSelectList'];
  @Prop({ default: () => [], type: Array }) dimensionTable: IProps['dimensionTable'];
  // @Prop({ default: () => {} }) allDataPreview: IProps['allDataPreview'];
  @Prop({ default: () => new Map(), type: Map }) groupsMap: IProps['groupsMap'];
  @Prop({ default: () => {} }) defaultGroupInfo: IProps['defaultGroupInfo'];

  @InjectReactive('timeSeriesGroupId') readonly timeSeriesGroupId: number;
  @InjectReactive('requestHandlerMap') readonly requestHandlerMap: RequestHandlerMap;
  @InjectReactive('isAPM') readonly isAPM: boolean;
  @InjectReactive('appName') readonly appName: string;
  @InjectReactive('serviceName') readonly serviceName: string;

  /** 别名输入框引用 */
  @Ref() readonly descriptionInput!: HTMLInputElement;
  /** 汇聚方法选择器引用 */
  @Ref() readonly aggConditionInput!: HTMLInputElement;
  /** 指标表格头部引用 */
  @Ref() readonly metricTableHeader!: HTMLInputElement;
  /** 单位选择器引用 */
  @Ref() readonly unitSelectInput!: HTMLInputElement;

  /** 是否正在编辑别名 */
  canEditName = false;
  /** 别名备份值，用于编辑时临时存储 */
  copyAlias = '';
  /** 是否正在编辑汇聚方法 */
  canEditAgg = false;
  /** 是否正在编辑单位 */
  canEditUnit = false;
  /** 汇聚方法备份值，用于编辑时临时存储 */
  copyAggregation = '';
  /** 单位备份值，用于编辑时临时存储 */
  copyUnit = '';
  /** ResizeObserver 实例，用于监听元素尺寸变化 */
  resizeObserver = null;
  /** 表格头部高度 */
  rectHeight = 32;

  /** 获取去重后的维度选择列表 */
  get dimensionSelectList() {
    return [...new Set(this.dimensionTable.map(item => item.name))];
  }

  /** 计算后的高度（包含偏移量） */
  get computedHeight() {
    return this.rectHeight + DEFAULT_HEIGHT_OFFSET;
  }

  /**
   * 获取展示时间
   * @param timeStr 时间戳（秒）
   * @returns 格式化后的时间字符串
   */
  getShowTime(timeStr: number) {
    if (!timeStr) return '-';
    const timestamp = new Date(timeStr * 1000);
    return dayjs.tz(timestamp).format('YYYY-MM-DD HH:mm:ss');
  }

  /**
   * 处理分组选择切换
   * @param id 分组ID
   * @param row 指标项数据
   */
  handleGroupSelectToggle(id: number, row: IMetricItem) {
    if (!id) {
      this.updateCustomFields('scope', this.defaultGroupInfo, row);
      return;
    }
    const name = this.groupSelectList.find(item => item.id === id)?.name;
    this.updateCustomFields('scope', { id, name }, row);
  }

  /**
   * 判断选项是否被禁用（由匹配规则匹配的选项）
   * @param metricName 指标名称
   * @param key 分组ID
   * @returns 是否禁用
   */
  getIsDisable(metricName, key) {
    if (!metricName) {
      return false;
    }
    return this.groupsMap.get(key)?.matchRulesOfMetrics?.includes?.(metricName) || false;
  }
  /**
   * 获取由匹配规则生成的提示信息
   * @param metricName 指标名称
   * @param groupName 分组名称
   * @returns 匹配规则字符串
   */
  getDisableTip(metricName, groupName) {
    const targetGroup = this.groupsMap.get(groupName);
    let targetRule = '';
    targetGroup?.matchRules?.forEach(rule => {
      if (!targetRule) {
        if (matchRuleFn(metricName, rule)) {
          targetRule = rule;
        }
      }
    });
    return targetRule;
  }

  /**
   * 显示分组管理弹窗
   * @returns 触发 showAddGroup 事件
   */
  @Emit('showAddGroup')
  handleShowGroupManage(): boolean {
    return true;
  }

  /**
   * 更新自定义字段
   * @param k 字段名
   * @param v 字段值
   * @param metricInfo 指标信息
   * @param showMsg 是否显示成功消息
   */
  async updateCustomFields(k: string, v: any, metricInfo: IMetricItem) {
    const updateField = {
      type: 'metric',
      name: metricInfo.name,
      id: metricInfo.id,
      scope: metricInfo.scope,
      config: metricInfo.config,
      dimensions: metricInfo.dimensions,
    };
    if (k === 'scope') {
      updateField.scope = v;
    }
    try {
      const params = {
        time_series_group_id: this.timeSeriesGroupId,
        update_fields: [updateField],
      };
      if (this.isAPM) {
        delete params.time_series_group_id;
        Object.assign(params, {
          app_name: this.appName,
          service_name: this.serviceName,
        });
      }
      await this.requestHandlerMap.modifyCustomTsFields(params);
      this.$bkMessage({ theme: 'success', message: this.$t('变更成功') });
      if (k === 'scope') {
        this.$emit('refresh');
        this.$emit('close');
      }
    } catch (error) {
      console.error('Update metric failed:', error);
    }
  }

  /**
   * 编辑别名
   * @param metricInfo 指标信息
   */
  async handleEditAlias(metricInfo: IMetricItem) {
    this.canEditName = false;
    if (this.copyAlias === metricInfo.config.alias) {
      this.copyAlias = '';
      return;
    }
    const currentDescription = this.copyAlias;
    metricInfo.config.alias = currentDescription;
    await this.updateCustomFields('alias', currentDescription, metricInfo);
  }

  handleEnterEditAlias() {
    this.descriptionInput.blur();
  }

  /**
   * 显示编辑别名输入框
   * @param name 当前别名
   */
  handleShowEditDescription(name) {
    this.canEditName = true;
    this.copyAlias = name;
    this.$nextTick(() => {
      this.descriptionInput.focus();
    });
  }
  /**
   * 编辑单位
   * @param isShow 下拉框是否展开
   * @param metricInfo 指标信息
   */
  async handleEditUnit(isShow: boolean, metricInfo: IMetricItem) {
    if (isShow) return;
    this.canEditUnit = false;
    if (this.copyUnit === metricInfo.config.unit) return;
    metricInfo.config.unit = this.copyUnit;
    await this.updateCustomFields('unit', metricInfo.config.unit, metricInfo);
  }

  /**
   * 编辑函数
   * @param func 函数配置
   * @param metricInfo 指标信息
   */
  async editFunction(func, metricInfo) {
    metricInfo.config.function = func;
    await this.updateCustomFields('function', func, metricInfo);
  }

  /**
   * 编辑汇聚方法
   * @param metricInfo 指标信息
   * @param isShow 下拉框是否展开
   */
  async editAggregation(metricInfo, isShow) {
    if (isShow) return;
    this.canEditAgg = false;
    if (this.copyAggregation === metricInfo.config.aggregate_method) return;
    metricInfo.config.aggregate_method = this.copyAggregation;
    await this.updateCustomFields('aggregate_method', this.copyAggregation, metricInfo);
  }

  handleShowEditUnit(unit: string) {
    this.copyUnit = unit;
    this.canEditUnit = true;
    this.$nextTick(() => {
      this.unitSelectInput?.getPopoverInstance?.()?.show?.();
    });
  }
  /**
   * 显示编辑汇聚方法选择器
   * @param aggCondition 当前汇聚方法
   */
  handleShowEditAgg(aggCondition) {
    this.canEditAgg = true;
    this.copyAggregation = deepClone(aggCondition);
    this.$nextTick(() => {
      this.aggConditionInput?.getPopoverInstance?.()?.show?.();
    });
  }

  /**
   * 编辑上报周期
   * @param v 周期值（秒）
   * @param metricInfo 指标信息
   */
  editInterval(v: number, metricInfo: IMetricItem) {
    metricInfo.config.interval = v;
    this.updateCustomFields('interval', v, metricInfo);
  }
  /**
   * 编辑关联维度
   * @param metricInfo 指标信息
   * @param v 维度值数组
   */
  editDimension(metricInfo: IMetricItem, v: string[]) {
    if (metricInfo.dimensions.join(',') === v.join(',')) {
      return;
    }

    metricInfo.dimensions = v;
    this.updateCustomFields('dimensions', v, metricInfo);
  }
  /**
   * 切换显示/隐藏状态
   * @param v 当前显示状态
   * @param metricInfo 指标信息
   */
  handleEditHidden(v: boolean, metricInfo: IMetricItem) {
    metricInfo.config.hidden = !metricInfo.config.hidden;
    this.updateCustomFields('hidden', !v, metricInfo);
  }
  /** 切换状态 */
  // handleClickDisabled(metricInfo) {
  //   metricInfo.disabled = !metricInfo.disabled;
  //   this.updateCustomFields('disabled', metricInfo.disabled, metricInfo, true);
  // }
  /**
   * 获取分组选择组件
   * @param row 指标项数据
   * @param showFoot 是否显示底部"新建分组"选项
   * @returns 分组选择组件
   */
  getGroupCpm(row: IMetricItem, showFoot = true) {
    return (
      <bk-select
        key={row.name}
        clearable={false}
        value={row.scope.id}
        disabled={!row.movable}
        displayTag
        searchable
        onChange={(v: number) => this.handleGroupSelectToggle(v, row)}
      >
        {this.groupSelectList.map(item => (
          <bk-option
            id={item.id}
            key={item.id}
            v-bk-tooltips={
              !this.getIsDisable(row.name, item.id)
                ? { disabled: true }
                : {
                    content: this.$t('由匹配规则{0}生成', [this.getDisableTip(row.name, item.id)]),
                    placements: ['right'],
                    boundary: 'window',
                    allowHTML: false,
                  }
            }
            disabled={this.getIsDisable(row.name, item.id)}
            name={item.name === NULL_LABEL ? this.$t('默认分组') : item.name}
          />
        ))}
        {showFoot && (
          <div
            class='edit-group-manage'
            slot='extension'
            onClick={this.handleShowGroupManage}
          >
            <i class='icon-monitor icon-jia' />
            <span>{this.$t('新建分组')}</span>
          </div>
        )}
      </bk-select>
    );
  }

  /**
   * 渲染信息项
   * @param props 包含 label 和 value 的对象
   * @param readonly 是否为只读模式
   * @returns 信息项组件
   */
  renderInfoItem(props: { label: string; value?: any }, readonly = false) {
    return (
      <div class='info-item'>
        <span class='info-label'>{props.label}：</span>
        <div
          class={['info-content', readonly ? 'readonly' : '']}
          v-bk-overflow-tips
        >
          {props.value ?? '-'}
        </div>
      </div>
    );
  }

  /**
   * 生成唯一键值（用于函数选择器的 key）
   * @param obj 函数配置对象
   * @returns 唯一键值字符串
   */
  getKey(obj) {
    return `${obj?.id || ''}_${obj?.params?.[0]?.value || ''}`;
  }

  /** 组件挂载后初始化 */
  mounted() {
    this.handleSetDefault(); // 初始化高度
    this.resizeObserver = new ResizeObserver(this.handleResize);
    if (this.metricTableHeader) {
      this.resizeObserver.observe(this.metricTableHeader);
    }
  }
  /** 组件销毁前清理 */
  destroyed() {
    if (this.resizeObserver) {
      this.resizeObserver.disconnect(); // 清除监听
    }
  }
  /**
   * 处理元素尺寸变化（带防抖）
   * @param entries ResizeObserver 回调的 entries 数组
   */
  @Debounce(100)
  handleResize(entries) {
    const entry = entries[0];
    if (entry) {
      this.rectHeight = entry.contentRect.height;
    }
  }
  /** 初始化或窗口调整时设置默认高度值 */
  handleSetDefault() {
    if (this.metricTableHeader) {
      const rect = this.metricTableHeader.getBoundingClientRect();
      this.rectHeight = rect.height;
    }
  }

  render() {
    if (!Object.keys(this.metricData).length) {
      return null;
    }

    return (
      <div class='metric-card-main'>
        <div class='card-header'>
          <h2 class='card-title'>{this.$t('指标详情')}</h2>
          <i
            class=' icon-monitor icon-mc-close'
            onClick={() => {
              this.$emit('close');
            }}
          />
        </div>
        <div class='card-body'>
          <div class='info-column'>
            {this.renderInfoItem({ label: '名称', value: this.metricData.name }, true)}
            <div class='info-item'>
              <span class='info-label'>{this.$t('别名')}：</span>
              {!this.canEditName ? (
                <div
                  class='info-content info-text'
                  v-bk-overflow-tips
                  onClick={() => this.handleShowEditDescription(this.metricData.config.alias)}
                >
                  {this.metricData.config.alias || '--'}
                </div>
              ) : (
                <bk-input
                  ref='descriptionInput'
                  v-model={this.copyAlias}
                  onBlur={() => this.handleEditAlias(this.metricData)}
                  onEnter={this.handleEnterEditAlias}
                />
              )}
            </div>
            <div class='info-item is-group-item'>
              <span class='info-label'>{this.$t('分组')}：</span>
              <div class='info-content'>
                <div class='group-list'>{this.getGroupCpm(this.metricData, false)}</div>
              </div>
            </div>

            {/* TODO: 暂不支持配置 */}
            {/* <div class='info-item'>
              <span class='info-label'>{this.$t('状态')}：</span>
              <div class='info-content'>
                <span
                  class='status-wrap'
                  onClick={() => this.handleClickDisabled(metricData)}
                >
                  {this.statusPoint(
                    statusMap.get(Boolean(metricData?.disabled)).color1,
                    statusMap.get(Boolean(metricData?.disabled)).color2
                  )}
                  <span>{statusMap.get(Boolean(metricData?.disabled)).name}</span>
                </span>
              </div>
            </div> */}

            <div class='info-item'>
              <span class='info-label'>{this.$t('单位')}：</span>
              {!this.canEditUnit ? (
                <div
                  class='info-content'
                  onClick={() => this.handleShowEditUnit(this.metricData.config.unit)}
                >
                  {this.metricData.config.unit || '--'}
                </div>
              ) : (
                <bk-select
                  ref='unitSelectInput'
                  ext-cls='unit-content unit-ext'
                  v-model={this.copyUnit}
                  clearable={false}
                  allow-create
                  searchable
                  onToggle={(v: boolean) => this.handleEditUnit(v, this.metricData)}
                >
                  {this.unitList.map((group, index) => (
                    <bk-option-group
                      key={index}
                      name={group.name}
                    >
                      {group.formats.map(option => (
                        <bk-option
                          id={option.id}
                          key={option.id}
                          name={option.name}
                        />
                      ))}
                    </bk-option-group>
                  ))}
                </bk-select>
              )}
            </div>
            {/* 汇聚方法 */}
            <div class='info-item'>
              <span class='info-label'>{this.$t('汇聚方法')}：</span>
              {!this.canEditAgg ? (
                <div
                  class='info-content'
                  onClick={() => this.handleShowEditAgg(this.metricData.config.aggregate_method)}
                >
                  {this.metricData.config.aggregate_method || '--'}
                </div>
              ) : (
                <bk-select
                  ref='aggConditionInput'
                  ext-cls='unit-content'
                  v-model={this.copyAggregation}
                  clearable={false}
                  onToggle={v => this.editAggregation(this.metricData, v)}
                >
                  {METHOD_LIST.map(option => (
                    <bk-option
                      id={option.id}
                      key={option.id}
                      name={option.name}
                    />
                  ))}
                </bk-select>
              )}
            </div>

            <div class='info-item'>
              <span class='info-label'>{this.$t('函数')}：</span>
              <div class='info-content'>
                <FunctionSelect
                  key={`${this.metricData.name}_${this.getKey(this.metricData.config.function?.length ? this.metricData.config.function[0] : {})}`}
                  class='metric-func-selector-add'
                  isMultiple={false}
                  placeholder='--'
                  value={this.metricData.config.function}
                  onValueChange={params => this.editFunction(params, this.metricData)}
                />
              </div>
            </div>
            <div class='info-item'>
              <span class='info-label'>{this.$t('关联维度')}：</span>
              {
                <div class='dimension-content'>
                  <bk-select
                    clearable={false}
                    value={this.metricData.dimensions}
                    displayTag
                    multiple
                    searchable
                    onChange={v => this.editDimension(this.metricData, v)}
                  >
                    {this.dimensionSelectList.map(dim => (
                      <bk-option
                        id={dim}
                        key={dim}
                        value={dim}
                        name={dim}
                      />
                    ))}
                  </bk-select>
                </div>
              }
            </div>

            {/* 上报周期 */}
            <div class='info-item is-interval-item'>
              <span class='info-label'>{this.$t('上报周期')}：</span>
              <CycleInput
                class='unit-content'
                isNeedDefaultVal={true}
                minSec={10}
                needAuto={false}
                value={this.metricData.config.interval}
                onChange={(v: number) => this.editInterval(v, this.metricData)}
              />
            </div>
            {this.renderInfoItem({ label: '创建时间', value: this.getShowTime(this.metricData.create_time) }, true)}
            {this.renderInfoItem({ label: '更新时间', value: this.getShowTime(this.metricData.update_time) }, true)}
            {/* {this.renderInfoItem(
              {
                label: '最近数据',
                value: this.allDataPreview[this.metricData.name]
                  ? `${this.allDataPreview[this.metricData.name]}(数据时间: ${this.getShowTime(this.metricData?.last_time)})`
                  : `(${this.$t('近5分钟无数据上报')})`,
              },
              true
            )} */}
            <div class='info-item'>
              <span class='info-label'>{this.$t('显示')}：</span>
              <bk-switcher
                class='switcher-btn'
                size='small'
                theme='primary'
                value={!this.metricData.config.hidden}
                onChange={v => this.handleEditHidden(v, this.metricData)}
              />
            </div>
          </div>
        </div>
      </div>
    );
  }
}
