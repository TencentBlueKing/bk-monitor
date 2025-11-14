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
import { defineComponent, shallowRef } from 'vue';

import { Alert, Dialog, Radio } from 'bkui-vue';

import MarkdownEditor from '../../../../../components/markdown-editor/editor';

import './handle-experience.scss';
export default defineComponent({
  name: 'HandleExperience',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['update:show'],

  setup(props, { emit }) {
    const bindTarget = shallowRef('metric');
    const editorValue = shallowRef('');

    const handleShowChange = (isShow: boolean) => {
      emit('update:show', isShow);
    };

    return {
      bindTarget,
      editorValue,
      handleShowChange,
    };
  },
  render() {
    return (
      <Dialog
        width={960}
        class='handle-experience-dialog'
        isShow={this.show}
        title={this.$t('处理经验')}
        onUpdate:isShow={this.handleShowChange}
      >
        <div class='handle-experience-dialog-wrapper'>
          <Alert
            theme='info'
            title={this.$t('处理经验可以与指标或维度进行绑定，可以追加多种处理经验方便共享。')}
          />
          <div class='bind-target form-item'>
            <div class='form-label'>{this.$t('绑定')}</div>
            <div class='form-content'>
              <Radio.Group v-model={this.bindTarget}>
                <Radio label='metric'>
                  <span>{this.$t('指标')}: kube_pod_status_phase,kube_pod_owner</span>
                </Radio>
                <Radio label='dimension'>
                  <span>{this.$t('维度')}</span>
                </Radio>
              </Radio.Group>
            </div>
          </div>
          <div class='edit-experience form-item'>
            <div class='form-label'>{this.$t('经验')}</div>
            <div class='form-content'>
              <MarkdownEditor
                height={'100%'}
                value={this.editorValue}
              />
            </div>
          </div>
        </div>
      </Dialog>
    );
  },
});
