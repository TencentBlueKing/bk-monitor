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

import { getExperience, saveExperience } from '../../../../monitor-api/modules/alert';
import Editor from '../../../../monitor-ui/markdown-editor/editor';

import './handle-experience.scss';

interface IHandleExperienceProps {
  show?: boolean;
  alertId?: number | string;
  bkBizId?: number;
}

@Component({
  name: 'HandleExperience'
})
export default class HandleExperience extends tsc<IHandleExperienceProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: [Number, String], default: 0 }) alertId: number | string;
  @Prop({ type: Number, default: 0 }) bkBizId: number;

  public text = '';
  public isLoading = true;

  @Watch('show')
  handleShow(v) {
    if (v) {
      this.getData();
    }
  }

  async getData() {
    this.isLoading = true;
    const data = await getExperience({ alert_id: this.alertId, bk_biz_id: this.bkBizId }).finally(
      () => (this.isLoading = false)
    );
    this.text = data.description;
  }
  async saveData() {
    this.isLoading = true;
    const params = {
      bk_biz_id: this.bkBizId,
      alert_id: this.alertId,
      description: this.text
    };
    const data = await saveExperience(params).finally(() => (this.isLoading = false));
    this.text = data.description;
  }

  render() {
    return (
      <div
        v-bkloading={{ isLoading: this.isLoading }}
        class={['event-detail-handleexperience', { displaynone: !this.show }]}
      >
        <div class='handleexperience-tip'>
          <span class='icon-monitor icon-hint'></span>
          <span class='tip-text'>
            {this.$t('处理经验是与指标绑定出现的，如果同一个指标有多种情况，可以追加多种处理经验方便经验的共享。')}
          </span>
        </div>
        <Editor
          height='400px'
          class='detail-content-editor'
          v-model={this.text}
        ></Editor>
        <bk-button
          ext-cls={'handleexperience-btn'}
          theme='primary'
          on-click={this.saveData}
        >
          {' '}
          {this.$t('保存')}{' '}
        </bk-button>
      </div>
    );
  }
}
