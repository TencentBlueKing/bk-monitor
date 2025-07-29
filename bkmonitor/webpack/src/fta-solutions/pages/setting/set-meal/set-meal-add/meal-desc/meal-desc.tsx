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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import Viewer from 'monitor-ui/markdown-editor/viewer';

import SetMealAddModule from '../../../../../store/modules/set-meal-add';
import VariableList from './variable-list/variable-list';

import './meal-desc.scss';

interface IMealDescEvent {
  onChange?: boolean;
}
interface IMealDescProps {
  pluginType?: string;
  pluginTypeId?: number;
  show?: boolean;
}

@Component({
  name: 'MealDesc',
})
export default class MealDesc extends tsc<IMealDescProps, IMealDescEvent> {
  @Prop({ default: true }) show: boolean;
  @Prop({ default: '', type: String }) pluginType: string;
  @Prop({ default: 0, type: Number }) pluginTypeId: number;

  /**
   * 点击展开/收起侧栏
   */
  handleDescShow() {
    this.$emit('change', !this.show);
  }
  mealDescription() {
    return (
      <pre class='format-content'>
        {`{
    "alarm_def_id": 1, // 自愈定义id
    "ip": "10.0.0.1", // 告警主机ip
    "source_type": "NAGIOS", // 告警源
    "alarm_type": "NAGIOS-ping", // 告警类型
    "cc_biz_id": "21480" // 业务id
}`}
      </pre>
    );
  }
  get pluginDescription() {
    return SetMealAddModule.getPluginDescription;
  }
  protected render() {
    return (
      <div class={['meal-desc-wrap', { 'meal-desc-show': this.show }]}>
        <div class='meal-desc-main'>
          <div class='desc-header'>{this.$i18n.t('套餐说明')}</div>
          <div class='desc-content'>
            {!this.pluginTypeId && [
              <div class='detail'>
                <i18n path='套餐是业务运维设计制作的一套恢复故障的方案，可以复用于不同的告警，也可作为原子套餐用于制作组合套餐' />
                。
              </div>,
              // <div class="see-detail">
              //   <i18n path="更多详情查看"></i18n>
              //   <span class="see-detail-btn">
              //     <i18n path="自愈套餐大全"></i18n> <span>{'>'}</span>
              //   </span>
              // </div>
            ]}
            <div class='format-desc'>
              {this.pluginDescription?.[this.pluginTypeId] && (
                <div class='view-content'>
                  <Viewer value={this.pluginDescription[this.pluginTypeId]} />
                </div>
              )}
              {/* <div class="format-title">
                <i18n path="格式说明"></i18n>
              </div>
              {this.mealDescription()} */}
              <div class='variable'>
                <div class='variable-title'>
                  <i18n
                    class='variable-title-left'
                    path='变量列表'
                  />
                  <span class='variable-title-right'>{/* {this.$t('帮助文档')} <span>{'>'}</span> */}</span>
                </div>
                <VariableList pluginType={this.pluginType} />
              </div>
            </div>
          </div>
        </div>
        <div
          class='slider-btn'
          onClick={this.handleDescShow}
        >
          <i class='icon-monitor icon-double-down' />
        </div>
      </div>
    );
  }
}
