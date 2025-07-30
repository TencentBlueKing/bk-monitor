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
import { Component, Mixins } from 'vue-property-decorator';

import { random } from 'monitor-common/utils/utils';

import authorityMixinCreate from '../../mixins/authorityMixin';
import * as authorityMap from '../alarm-group/authority-map';
import AlarmGroupList from './alarm-group-common/alarm-group';

Component.registerHooks(['beforeRouteEnter']);
@Component({
  name: 'AlarmGroupListMonitor',
})
export default class AlarmGroupListMonitor extends Mixins(authorityMixinCreate(authorityMap)) {
  fromRouterName = '';

  needRefresh = false;

  beforeRouteEnter(to, from, next) {
    next((vm: AlarmGroupListMonitor) => {
      vm.fromRouterName = `${from.name}-${random(8)}`;
      vm.needRefresh = to.params.needRefresh || false;
    });
  }
  render(): VNode {
    return (
      <AlarmGroupList
        style={{ margin: '24px' }}
        fromRouterName={this.fromRouterName}
        needRefresh={this.needRefresh}
        type='monitor'
      />
    );
  }
}
