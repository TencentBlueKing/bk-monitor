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

import './status-tips.scss';

export type MapType<T extends number | string> = { [key in T]?: any };

// 已启用 ENABLED
// 有更新 UPDATABLE
// 无数据 NO_DATA
// 将下架 REMOVE_SOON
// 已下架 REMOVED
// 已停用 DISABLED
// 可用 AVAILABLE
export type StatusType = 'AVAILABLE' | 'DISABLED' | 'ENABLED' | 'NO_DATA' | 'REMOVE_SOON' | 'REMOVED' | 'UPDATABLE';

interface StatusTipsProps {
  status: StatusType;
}
@Component({ name: 'StatusTips' })
export default class StatusTips extends tsc<StatusTipsProps> {
  @Prop({ type: String, default: 'success' }) readonly status: StatusType;
  @Prop({ type: Number, default: 2 }) readonly lineHeight: number;
  @Prop({ type: Number, default: 14 }) readonly titleHeight: number;
  @Prop({ type: Number, default: 115 }) readonly titleWidth: number;

  statusMap: MapType<StatusType> = {
    ENABLED: this.$t('已启用'),
    UPDATABLE: this.$t('有更新'),
    NO_DATA: this.$t('无数据'),
    REMOVE_SOON: this.$t('将下架'),
    REMOVED: this.$t('已下架'),
    DISABLED: this.$t('已停用'),
  };

  colorMap: MapType<StatusType> = {
    UPDATABLE: '#14A568 ',
    NO_DATA: '#EA3535',
    REMOVE_SOON: '#FF9C00',
    REMOVED: '#ADAFB6',
  };

  get lineStyle() {
    return {
      height: `${this.lineHeight}px`,
      background: this.colorMap[this.status],
    };
  }

  get nameStyle() {
    return {
      height: `${this.titleHeight}px`,
      background: this.colorMap[this.status],
      width: `${this.titleWidth}px`,
    };
  }

  get titleStyle() {
    return {
      marginTop: `-${this.lineHeight / 2}px`,
      lineHeight: 1,
    };
  }

  render() {
    return (
      <div class='status-tips'>
        <div
          style={this.lineStyle}
          class='line'
        />
        <div
          style={this.nameStyle}
          class='title'
        >
          <span style={this.titleStyle}>{this.statusMap[this.status]}</span>
        </div>
      </div>
    );
  }
}
