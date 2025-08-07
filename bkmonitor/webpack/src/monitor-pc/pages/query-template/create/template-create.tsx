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
import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import BasicInfoCreate from '../components/basic-info/basic-info-create';
import TemplateConfig from '../components/template-config/template-config';
import VariablesManage from '../variables/variables-manage/variables-manage';

import type { VariableModel } from '../typings';

import './template-create.scss';

@Component
export default class TemplateCreate extends tsc<object> {
  @Ref() createContentWrap: HTMLDivElement;

  steps = [
    { title: this.$t('模板配置'), icon: 1 },
    { title: this.$t('模板预览'), icon: 2 },
  ];

  curStep = 1;

  resizeObserver = null;
  isSticky = false;

  basicInfoData = {
    name: '',
    desc: '',
    effect: [],
  };

  variablesList: VariableModel[] = [{ type: 'agg_method' }, { type: 'dimension' }];

  handleNextStep() {
    this.curStep += 1;
  }

  handlePrevStep() {
    this.curStep -= 1;
  }

  handleBackGotoPage() {
    this.$router.push({ name: 'query-template' });
  }

  observerCreateConfigResize() {
    this.resizeObserver = new ResizeObserver(() => {
      this.isSticky = this.createContentWrap.scrollHeight > this.createContentWrap.clientHeight;
    });
    this.resizeObserver.observe(this.createContentWrap);
  }

  mounted() {
    this.observerCreateConfigResize();
  }

  beforeDestroy() {
    this.resizeObserver.unobserve(this.createContentWrap);
  }

  render() {
    return (
      <div class='template-create'>
        <div class='template-create-nav'>
          <span
            class='icon-monitor icon-back-left navigation-bar-back'
            onClick={() => this.handleBackGotoPage()}
          />
          <span class='title'>{this.$t('新建查询模板')}</span>
          <bk-steps
            class='template-steps'
            cur-step={this.curStep}
            lineType='solid'
            steps={this.steps}
          />
        </div>
        <div class='template-create-content'>
          <div
            ref='createContentWrap'
            class='create-content-wrap'
          >
            <div class='create-config'>
              <BasicInfoCreate formData={this.basicInfoData} />
              <TemplateConfig />
            </div>
            <div class={['submit-btns', { sticky: this.isSticky }]}>
              <bk-button
                theme='primary'
                onClick={this.handleNextStep}
              >
                {this.$t(this.curStep === 2 ? '提交' : '下一步')}
              </bk-button>
              {this.curStep === 2 && (
                <bk-button
                  theme='default'
                  onClick={this.handlePrevStep}
                >
                  {this.$t('上一步')}
                </bk-button>
              )}
              <bk-button
                theme='default'
                onClick={this.handleBackGotoPage}
              >
                {this.$t('取消')}
              </bk-button>
            </div>
          </div>
          <VariablesManage variablesList={this.variablesList} />
        </div>
      </div>
    );
  }
}
