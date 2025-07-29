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
import type { VNode } from 'vue';

import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import AlarmGroupAdd from 'monitor-pc/pages/alarm-group/alarm-group-add/alarm-group-add-common/alarm-group-add';

import type { Route } from 'vue-router';

interface IAlarmGroupAdd {
  id?: number | string;
}

Component.registerHooks(['beforeRouteEnter']);
@Component
export default class AlarmGroupAddFta extends tsc<IAlarmGroupAdd> {
  @Prop({ default: null, type: [Number, String] }) id: number | string;

  fromRoute = '';
  beforeRouteEnter(to: Route, from: Route, next: (a: (vm: AlarmGroupAddFta) => void) => void) {
    next((vm: AlarmGroupAddFta) => {
      vm.fromRoute = from.name;
    });
  }
  render(): VNode {
    return (
      <AlarmGroupAdd
        style='padding: 40px 159px 0px 48px; height: 100%;'
        fromRoute={this.fromRoute}
        groupId={+this.id}
        type='fta'
      />
    );
  }
}
