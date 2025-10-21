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

import EmptyStatus from '@/components/empty-status/empty-status';

import './variable-guide.scss';

interface VariablesGuideEvents {
  onClear: () => void;
}

interface VariablesGuideProps {
  mode?: 'guide' | 'search-empty';
}

@Component
export default class VariablesGuide extends tsc<VariablesGuideProps, VariablesGuideEvents> {
  @Prop({ default: 'guide' }) readonly mode!: VariablesGuideProps['mode'];

  guideSteps = [
    { id: 1, title: this.$t('使用变量') },
    { id: 2, title: this.$t('定义变量') },
    { id: 3, title: this.$t('后续消费') },
  ];

  renderGuideDesc(id: number) {
    if (id === 1) {
      return (
        <div class='description'>
          <div class='description-item'>
            <span class='dot' />
            <i18n
              class='text'
              path='输入框：直接输入 {0} 即可新建变量'
            >
              <div class='variable-tag'>{'${variable_name}'}</div>
            </i18n>
          </div>
          <div class='description-item'>
            <span class='dot' />
            <i18n
              class='text'
              path='选择框：在选项中选择 {0} 然后输入变量名'
            >
              <span class='variable-tag'>
                {this.$t('创建变量')}
                {' ${}'}
              </span>
            </i18n>
          </div>
        </div>
      );
    }
    if (id === 2) {
      return (
        <div class='description'>
          <div class='description-item'>
            <span class='dot' />
            <i18n
              class='text'
              path='新建后，右侧会出现 {0}'
            >
              <div class='variable-tag'>{this.$t('变量配置框')}</div>
            </i18n>
          </div>
          <div class='description-item'>
            <span class='dot' />
            <i18n
              class='text'
              path='可以定义 {0} {1}'
            >
              <span class='variable-tag'>{this.$t('变量别名')}</span>
              <span class='variable-tag'>{this.$t('变量类型')}</span>
            </i18n>
          </div>
        </div>
      );
    }
    return (
      <div class='description'>
        <div class='description-item'>
          <span class='dot' />
          <i18n
            class='text'
            path='在各消费场景，选择 {0} 后，可填入 {1}'
          >
            <div class='variable-tag'>{this.$t('查询模板')}</div>
            <div class='variable-tag'>{this.$t('变量值')}</div>
          </i18n>
        </div>
      </div>
    );
  }

  @Emit('clear')
  handleOperation() {}

  render() {
    if (this.mode === 'search-empty')
      return (
        <div class='variable-guide'>
          <EmptyStatus
            type='search-empty'
            onOperation={this.handleOperation}
          />
        </div>
      );

    return (
      <div class='variable-guide'>
        <div class='guide-title'>
          <i class='icon-monitor icon-bangzhu' />
          <span class='title'>{this.$t('如何使用变量')}</span>
        </div>
        <div class='guide-steps'>
          {this.guideSteps.map((step, index) => (
            <div
              key={step.id}
              class='step-item'
            >
              <div class='step-index'>
                <div class='index'>{index + 1}</div>
                {index < this.guideSteps.length - 1 && <div class='line' />}
              </div>
              <div class='step-content'>
                <div class='title'>{step.title}</div>
                {this.renderGuideDesc(step.id)}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }
}
