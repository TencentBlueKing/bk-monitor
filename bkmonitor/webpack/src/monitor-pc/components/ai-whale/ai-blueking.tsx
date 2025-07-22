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
import { Component, Watch, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import AIBlueking from '@blueking/ai-blueking/vue2';
import { random } from 'monitor-common/utils/utils';

import aiWhaleStore from '../../store/modules/ai-whale';

import '@blueking/ai-blueking/dist/vue2/style.css';

@Component
export default class AiBluekingWrapper extends tsc<object> {
  @Ref('aiBlueking') aiBluekingRef: typeof AIBlueking;
  headers = {
    Traceparent: `00-${random(32, 'abcdef0123456789')}-${random(16, 'abcdef0123456789')}-01`,
  };
  get apiUrl() {
    return '/ai_agents/chat';
  }
  get showDialog() {
    return aiWhaleStore.showAIBlueking;
  }
  get message() {
    return aiWhaleStore.message;
  }
  get shortcuts() {
    return [
      {
        id: 'explanation',
        name: this.$t('解释'),
        // icon: 'bkai-help',
        components: [
          {
            type: 'textarea',
            key: 'content',
            name: this.$t('内容'),
            fillBack: true,
            placeholder: this.$t('请输入需要解释的内容'),
          },
        ],
      },
      {
        id: 'translate',
        name: this.$t('翻译'),
        // icon: 'bkai-translate',
        components: [
          {
            type: 'textarea',
            key: 'content',
            name: this.$t('待翻译文本'),
            fillBack: true,
            placeholder: this.$t('请输入需要翻译的内容'),
          },
          {
            type: 'select',
            key: 'language',
            name: this.$t('语言'),
            placeholder: this.$t('请选择语言'),
            default: 'english',
            options: [
              { label: 'English', value: 'english' },
              { label: '中文', value: 'chinese' },
            ],
          },
        ],
      },
      {
        id: 'metadata_diagnosis',
        name: this.$t('链路排障'),
        // icon: 'bk-icon icon-monitors-cog',
        components: [
          {
            type: 'textarea',
            key: 'bk_data_id',
            fillBack: true,
            name: this.$t('数据源ID'),
            placeholder: this.$t('请输入数据源ID'),
          },
        ],
      },
    ];
  }
  @Watch('showDialog')
  handleShowDialogChange(newVal: boolean) {
    if (newVal) {
      this.aiBluekingRef.handleShow();
      return;
    }
    this.aiBluekingRef.handleClose();
  }
  @Watch('message')
  handleMessageChange(newVal: string) {
    if (!newVal) {
      return;
    }
    this.aiBluekingRef.handleStop();
    this.aiBluekingRef.handleSendMessage(newVal);
  }
  render() {
    return (
      <div class='ai-blueking-wrapper'>
        <AIBlueking
          ref='aiBlueking'
          requestOptions={{
            headers: this.headers,
          }}
          enablePopup={true}
          hideNimbus={true}
          prompts={[]}
          shortcuts={this.shortcuts}
          url={this.apiUrl}
          on-send-message={() => {
            this.headers.Traceparent = `00-${random(32, 'abcdef0123456789')}-${random(16, 'abcdef0123456789')}-01`;
          }}
          onClose={() => {
            aiWhaleStore.setShowAIBlueking(false);
          }}
          onShow={() => {
            aiWhaleStore.setShowAIBlueking(true);
          }}
        />
      </div>
    );
  }
}
