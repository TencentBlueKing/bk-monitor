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
import { Component, Mixins, Prop, Provide, ProvideReactive } from 'vue-property-decorator';

import { random } from 'monitor-common/utils/utils';

import { destroyTimezone } from '../../i18n/dayjs';
import authorityMixinCreate from '../../mixins/authorityMixin';
import * as ruleAuth from './authority-map';
import StrategyConfigSet from './strategy-config-set-new/strategy-config-set';

import type { strategyType } from './strategy-config-set-new/typings';

import './strategy-config-set.scss';
const allowJumpMap = ['alarm-group-add', 'alarm-group-edit', 'set-meal-add', 'set-meal-edit'];

Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);
@Component
export default class MonitorStrategyConfigSet extends Mixins(authorityMixinCreate(ruleAuth)) {
  @Prop({ type: [String, Number] }) readonly id: number | string;
  needCheck = true;
  fromRouteName = '';
  refreshKey = random(10);
  isActivated = false;
  showCancel = false;
  @ProvideReactive('authority') authority: Record<string, boolean> = {};
  @Provide('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Provide('authorityMap') authorityMap;
  @Provide('strategyType') strategyType: strategyType = 'monitor';
  beforeRouteEnter(to, from, next) {
    next((vm: MonitorStrategyConfigSet) => {
      vm.needCheck = to.name !== 'strategy-config-detail';
      vm.fromRouteName = `${from.name}-${random(10)}`;
      if (!allowJumpMap.includes(from.name) && vm.isActivated) {
        vm.refreshKey = random(10);
      }
    });
  }
  async beforeRouteLeave(to, _from, next) {
    if (this.needCheck && !allowJumpMap.includes(to.name) && this.$store.getters.bizIdChangePending !== to.name) {
      const needNext = await this.handleCancel(false);
      if (needNext) {
        destroyTimezone();
      }
      next(needNext);
    } else {
      destroyTimezone();
      next();
    }
  }
  // 点击取消
  handleCancel(needBack = true) {
    return new Promise(resolve => {
      this.$bkInfo({
        extCls: 'strategy-config-cancel',
        title: this.$t('是否放弃本次操作？'),
        confirmFn: () => {
          this.needCheck = false;
          needBack && this.$router.back();
          resolve(true);
        },
        cancelFn: () => resolve(false),
      });
    });
  }
  handleSave() {
    this.needCheck = false;
    this.$router.push({ name: 'strategy-config' });
  }
  async activated() {
    await this.$nextTick();
    this.isActivated = true;
  }
  render() {
    return (
      <StrategyConfigSet
        id={this.id}
        key={this.refreshKey}
        class={`strategy-config-set ${this.$route.name === 'strategy-config-detail' ? 'is-detail' : ''}`}
        fromRouteName={this.fromRouteName}
        onCancel={this.handleCancel}
        onSave={this.handleSave}
      />
    );
  }
}
