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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import IndicatorDimension from 'monitor-pc/pages/custom-escalation/metric-manage/components/indicator-dimension';

import { getUnitList } from 'monitor-api/modules/strategies';
import { getFunctions } from 'monitor-api/modules/grafana';
import {
  getCustomTsFields,
  deleteGroupingRule,
  previewGroupingRule,
  modifyCustomTsFields,
  customTsGroupingRuleList,
  importCustomTimeSeriesFields,
  createOrUpdateGroupingRule,
  exportCustomTimeSeriesFields,
} from 'monitor-api/modules/apm_custom_metric';

import './index.scss';

/** 组件事件接口 */
interface IEmits {
  /** 取消操作事件 */
  onCancel: (v: boolean) => void;
  /** 别名变化事件 */
  onAliasChange: (alias: string) => void;
  /** 分组列表变化事件 */
  onGroupListChange: () => void;
}

/** 组件属性接口 */
interface IProps {
  /** 是否显示对话框 */
  isShow?: boolean;
  /** 标签页 */
  tab?: 'metric' | 'dimension';
}

@Component
export default class AddGroupDialog extends tsc<IProps, IEmits> {
  /** 是否显示对话框 */
  @Prop({ default: true }) isShow: IProps['isShow'];
  @Prop({ default: 'metric' }) tab: IProps['tab'];
  /** 取消操作，清空表单并关闭对话框 */
  @Emit('cancel')
  handleCancel() {
    return false;
  }

  handleAliasChange() {
    this.$emit('aliasChange');
  }

  handleGroupListChange() {
    this.$emit('groupListChange');
  }

  render() {
    return (
      <bk-sideslider
        width={1280}
        {...{ on: { 'update:isShow': this.handleCancel } }}
        extCls={'metric-manage-slider-main'}
        isShow={this.isShow}
        quick-close={true}
        title={this.$t('指标管理')}
        onHidden={this.handleCancel}
      >
        <div
          class='content-main'
          slot='content'
        >
          <IndicatorDimension
            isAPMPage
            tab={this.tab}
            requestMap={{
              getUnitList,
              getFunctions,
              getCustomTsFields,
              deleteGroupingRule,
              previewGroupingRule,
              modifyCustomTsFields,
              customTsGroupingRuleList,
              importCustomTimeSeriesFields,
              createOrUpdateGroupingRule,
              exportCustomTimeSeriesFields,
            }}
            onAliasChange={this.handleAliasChange}
            onGroupListChange={this.handleGroupListChange}
          />
        </div>
      </bk-sideslider>
    );
  }
}
