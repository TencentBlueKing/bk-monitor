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

import { Component, Emit, Inject, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { dimensionData, modifyMetric } from '../../../../monitor-api/modules/apm_meta';
import EditableFormItem from '../../../components/editable-form-item/editable-form-item';
import * as authorityMap from '../../home/authority-map';

import { IDimensionItem, IMetricData, IUnitItme } from './type';

interface IndicatorDetailProps {
  data: IMetricData; // 指标详情
  unitList: IUnitItme[]; // 单位列表
}

interface IndicatorDetailEvents {
  onUpdate: boolean;
}

@Component
export default class IndicatorDetail extends tsc<IndicatorDetailProps, IndicatorDetailEvents> {
  @Prop({ type: Object, required: true }) data: IMetricData;
  @Prop({ type: Array, required: true }) unitList: IUnitItme[];

  @Inject('authority') authority;

  tableLoading = false;
  shouldUpdate = false; // 指标详情被修改过 关闭侧边栏需更新指标列表
  detailInfo: IMetricData = {
    field_name: '', // 指标名
    metric_display_name: '', // 指标别名,
    type: '', // 数据类型
    unit: '', // 单位
    table_id: '',
    data_source_label: '', // 来源
    result_table_label_name: '', // 数据对象
    tag_list: [], // 维度信息
    tags: [] // 标签
  };
  hoverRowIndex = -1; // 当前修改的指标维度索引
  dimensionList: IDimensionItem[] = []; // 指标维度列表

  @Watch('data', { immediate: true })
  handleDataChange(val) {
    this.detailInfo = val;
    this.getDimensionData(val);
  }

  get appId() {
    return Number(this.$route.params?.id || 0);
  }

  @Emit('update')
  handleDetailupdate(v) {
    return v;
  }

  /**
   * @desc 获取维度信息
   * @param { IMetricData } row 指标详情
   */
  async getDimensionData(row: IMetricData) {
    this.tableLoading = true;
    const params = {
      application_id: this.appId,
      table_id: row.table_id,
      metric_id: row.field_name,
      dimension_fields: row.tag_list.map(tag => tag.field_name)
    };
    const data = await dimensionData(this.appId, params).catch(() => {});
    this.dimensionList = row.tag_list.map(item => ({
      ...item,
      count: data?.count[item.field_name] || 0,
      data: data?.data[item.field_name] || '--'
    }));
    this.tableLoading = false;
  }
  /**
   * @desc 修改维度别名
   * @param { string } val 修改值
   * @param { string } field 修改的字段
   * @param { IDimensionItem } row 当前修改的维度
   */
  handleDimensionChange(val: string, field: string, row: IDimensionItem) {
    // 处理更新参数格式
    const dimensions = this.dimensionList.map(item => ({
      field: item.field_name,
      description: item.field_name === row.field_name ? val : item.description
    }));
    return this.handleUpdateValue(dimensions, field);
  }
  /**
   * @desc 更新当前详情
   * @param { string | array } value 更新值
   * @param { string } field 修改的字段
   */
  updateLocalDetail(value, field: string) {
    switch (field) {
      case 'metric_description':
        this.detailInfo.metric_display_name = value;
        break;
      case 'metric_unit':
        this.detailInfo.unit = value;
        break;
      case 'dimensions':
        // eslint-disable-next-line no-case-declarations
        const dimensionObj = {};
        value.map(val => (dimensionObj[val.field] = val.description));
        this.dimensionList = this.dimensionList.map(item => ({
          ...item,
          description: dimensionObj[item.field_name]
        }));
        break;
      default:
        break;
    }
  }
  /**
   * @desc 字段请求接口更新
   * @param { string | array } value 更新值
   * @param { string } field 修改的字段
   */
  async handleUpdateValue(value, field: string) {
    try {
      const { field_name: fieldName, metric_display_name: metricDisplayName, unit } = this.detailInfo;
      const dimensions = this.dimensionList.map(item => ({
        field: item.field_name,
        description: item.description
      }));
      const params = {
        application_id: this.appId,
        metric_id: fieldName,
        metric_description: metricDisplayName,
        metric_unit: unit,
        dimensions
      };
      params[field] = value;
      await modifyMetric(this.appId, params);
      this.handleDetailupdate(true);
      this.updateLocalDetail(value, field);
      return true;
    } catch (error) {
      return false;
    }
  }

  render() {
    const aliasNameSlot = {
      default: props => [
        <EditableFormItem
          value={props.row.description}
          showEditable={props.$index === this.hoverRowIndex}
          showLabel={false}
          authority={this.authority.MANAGE_AUTH}
          authorityName={authorityMap.MANAGE_AUTH}
          // eslint-disable-next-line @typescript-eslint/no-misused-promises
          updateValue={val => this.handleDimensionChange(val, 'dimensions', props.row)}
        />
      ]
    };

    return (
      <div class='indicator-detail-wrap'>
        <EditableFormItem
          label={this.$t('指标名')}
          value={this.detailInfo.field_name}
          showEditable={false}
        />
        <EditableFormItem
          label={this.$t('指标别名')}
          value={this.detailInfo.metric_display_name}
          formType='input'
          authority={this.authority.MANAGE_AUTH}
          authorityName={authorityMap.MANAGE_AUTH}
          // eslint-disable-next-line @typescript-eslint/no-misused-promises
          updateValue={val => this.handleUpdateValue(val, 'metric_description')}
        />
        {/* <EditableFormItem
        label={this.$t('数值类型')}
        value={this.detailInfo.numType}
        showEditable={false} /> */}
        <EditableFormItem
          label={this.$t('指标类型')}
          value={this.detailInfo.type}
          showEditable={false}
        />
        <EditableFormItem
          label={this.$t('单位')}
          value={this.detailInfo.unit}
          formType='unit'
          unitList={this.unitList}
          authority={this.authority.MANAGE_AUTH}
          authorityName={authorityMap.MANAGE_AUTH}
          // eslint-disable-next-line @typescript-eslint/no-misused-promises
          updateValue={val => this.handleUpdateValue(val, 'metric_unit')}
        />
        {/* <EditableFormItem
        label="数据步长"
        value={this.detailInfo.dataLength}
        formType="input"
        updateValue={val => this.handleUpdateValue(val, 'dataLength')} /> */}
        {/* <EditableFormItem
        label="启/停"
        value={this.detailInfo.status}
        showEditable={false} /> */}
        <div class='divider'></div>
        <EditableFormItem
          label={this.$t('来源')}
          value={this.detailInfo.data_source_label}
          showEditable={false}
        />
        <EditableFormItem
          label={this.$t('数据对象')}
          value={this.detailInfo.result_table_label_name}
          showEditable={false}
        />
        <EditableFormItem
          class='tag-form-item'
          label={this.$t('标签')}
          value={this.detailInfo.tags}
          formType='tag'
          showEditable={false}
        />
        <div class='divider'></div>
        <bk-table
          outer-border={false}
          data={this.dimensionList}
          v-bkloading={{ isLoading: this.tableLoading }}
          on-row-mouse-enter={index => (this.hoverRowIndex = index)}
          on-row-mouse-leave={() => (this.hoverRowIndex = -1)}
        >
          <bk-table-column
            label={this.$t('维度名')}
            width='120'
            scopedSlots={{ default: props => props.row.field_name }}
          ></bk-table-column>
          <bk-table-column
            label={this.$t('维度别名')}
            width='240'
            scopedSlots={aliasNameSlot}
          ></bk-table-column>
          <bk-table-column
            label={this.$t('数量')}
            width='60'
            scopedSlots={{ default: props => props.row.count }}
          ></bk-table-column>
          <bk-table-column
            label={this.$t('纬度值')}
            scopedSlots={{ default: props => props.row.data }}
          ></bk-table-column>
        </bk-table>
      </div>
    );
  }
}
