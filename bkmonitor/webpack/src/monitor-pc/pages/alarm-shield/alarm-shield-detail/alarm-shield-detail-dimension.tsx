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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import WhereDisplay from 'fta-solutions/pages/event/event-detail/where-display';
import { random } from 'monitor-common/utils/utils';

import './alarm-shield-detail-dimension.scss';

interface IProps {
  shieldData?: any;
}
@Component
export default class AlarmShieldDetailDimension extends tsc<IProps> {
  /* 编辑时后台返回的数据 */
  @Prop({ default: () => null, type: Object }) detailData: any;
  // 条件数据
  conditionList = [];
  conditionKey = random(8);
  allNames = {};

  @Watch('detailData', { immediate: true, deep: true })
  handleShieldData(data) {
    if (data.id) {
      this.conditionList = data.dimensionConfig?.dimensionConditions || [];
      this.conditionList.forEach(item => {
        this.allNames[item.key] = item.name || item.key;
      });
      this.conditionKey = random(8);
    }
  }

  render() {
    return (
      <div class='alarm-shield-detail-dimension'>
        <div class='scope-item'>
          <div class='item-label'>{this.$t('维度条件')}</div>
          <div class='item-content'>
            {this.conditionList.length ? (
              <WhereDisplay
                key={this.conditionKey}
                allNames={this.allNames}
                readonly={true}
                value={this.conditionList as any}
              />
            ) : (
              '--'
            )}
          </div>
        </div>
      </div>
    );
  }
}
