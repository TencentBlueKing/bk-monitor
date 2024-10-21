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

import AlarmDispatchConfig from 'monitor-pc/pages/alarm-dispatch/alarm-dispatch-config';
import * as authorityMap from 'monitor-pc/pages/alarm-dispatch/authority-map';
import authorityMixinCreate from 'monitor-ui/mixins/authorityMixin';

Component.registerHooks(['beforeRouteLeave']);
@Component
export default class FtaAlarmDispatchConfig extends Mixins(authorityMixinCreate(authorityMap)) {
  get isEffect() {
    return (this.$refs.alarmDispatchConfig as InstanceType<typeof AlarmDispatchConfig>)?.isEffect;
  }
  get isRuleChange() {
    return (this.$refs.alarmDispatchConfig as InstanceType<typeof AlarmDispatchConfig>)?.isRuleChange;
  }

  async beforeRouteLeave(to, from, next) {
    if (!to.params.refresh) {
      // 生效保存
      if (this.isEffect) {
        next();
        return;
      }
      // 修改规则 且 放弃修改
      if (this.isRuleChange) {
        const needNext = await this.confirmDialog();
        next(needNext);
        return;
      }
      next();
    } else {
      next();
    }
  }

  confirmDialog() {
    return new Promise(resolve => {
      this.$bkInfo({
        title: this.$t('是否放弃本次操作？'),
        confirmFn: () => {
          resolve(true);
        },
        cancelFn: () => {
          resolve(false);
        },
      });
    });
  }
  render() {
    return <AlarmDispatchConfig ref='alarmDispatchConfig' />;
  }
}
