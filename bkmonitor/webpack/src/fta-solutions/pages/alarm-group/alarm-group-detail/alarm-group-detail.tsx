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
/*
 * @Date: 2021-06-14 19:47:25
 * @LastEditTime: 2021-06-23 16:04:04
 * @Description:
 */
import { Component, Emit, Model, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import AlarmGroupDetail from 'monitor-pc/pages/alarm-group/alarm-group-detail/alarm-group-detail';

interface IAlarmGroupDeatail {
  id: number | string;
  show?: boolean;
}

@Component
export default class AlarmGroupDetailFta extends tsc<IAlarmGroupDeatail> {
  @Prop({ type: [String, Number], default: 0 }) id: number | string;
  @Model('showChange', { default: false, type: Boolean }) show: boolean;

  @Emit('showChange')
  handleDetailClose() {
    return false;
  }
  render() {
    return (
      <AlarmGroupDetail
        id={this.id}
        onShowChange={this.handleDetailClose}
      />
    );
  }
}
