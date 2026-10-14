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
import { defineComponent } from 'vue';

import { Button } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import illustration from './assets/collection-onboarding.svg';

import './collection-onboarding.scss';

export default defineComponent({
  name: 'CollectionOnboarding',
  props: {
    disabled: Boolean,
    loading: Boolean,
  },
  emits: ['start'],
  setup() {
    const { t } = useI18n();
    return { t };
  },
  render() {
    const steps = [
      { title: this.t('选择目标'), description: this.t('选择需要分析的主机和进程。') },
      { title: this.t('配置采集'), description: this.t('设置采集类型、时长和执行方式。') },
      { title: this.t('分析结果'), description: this.t('查看火焰图与调用栈，定位性能开销。') },
    ];
    return (
      <div class='collection-onboarding'>
        <div class='collection-onboarding-content'>
          <img
            class='collection-onboarding-illustration'
            alt=''
            src={illustration}
          />
          <h2>{this.t('按需采集，定位性能问题')}</h2>
          <p class='collection-onboarding-description'>
            {this.t('针对目标主机或进程发起性能采集，通过火焰图和调用栈分析 CPU 热点与内存分配问题。')}
          </p>
          <ol class='collection-onboarding-steps'>
            {steps.map((step, index) => (
              <li key={step.title}>
                <div class='collection-onboarding-step-heading'>
                  <span class='collection-onboarding-step-number'>{`0${index + 1}`}</span>
                  <h3>{step.title}</h3>
                </div>
                <p>{step.description}</p>
              </li>
            ))}
          </ol>
          <Button
            class='collection-onboarding-start'
            disabled={this.disabled}
            loading={this.loading}
            theme='primary'
            onClick={() => this.$emit('start')}
          >
            {this.t('立即采集')}
          </Button>
        </div>
      </div>
    );
  },
});
