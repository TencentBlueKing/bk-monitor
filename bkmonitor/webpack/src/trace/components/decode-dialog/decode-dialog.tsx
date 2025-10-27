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
import { computed, defineComponent, shallowRef } from 'vue';

import { Dialog, Message } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import { autoDecodeString, detectEncodingType } from '@/pages/common/formatter-utils';

import './decode-dialog.scss';

export default defineComponent({
  name: 'DecodeDialog',
  props: {
    content: {
      type: String,
      default: '',
    },
  },
  setup(props) {
    const t = useI18n().t;
    const isDecode = computed(() => !!detectEncodingType(props.content));
    const showDialog = shallowRef(false);
    const decodeContent = computed(() => autoDecodeString(props.content));
    const handleDecode = () => {
      showDialog.value = true;
    };
    const handleCopy = () => {
      copyText(decodeContent.value);
      Message({ theme: 'success', message: t('复制成功') });
      showDialog.value = false;
    };
    return {
      t,
      isDecode,
      showDialog,
      decodeContent,
      handleDecode,
      handleCopy,
    };
  },
  render() {
    return (
      <div class='decode-dialog'>
        <div
          class={{
            'decode-content': this.isDecode,
          }}
        >
          {this.content}
          {this.isDecode && (
            <div
              class='decode-text'
              onClick={this.handleDecode}
            >
              <i
                key='decode-icon'
                class='icon-monitor icon-mc-decode decode-icon'
              />
              {this.t('解码')}
            </div>
          )}
        </div>
        {this.isDecode && (
          <Dialog
            class='decode-dialog-modal'
            cancelText={this.t('关闭')}
            confirmText={this.t('复制')}
            isShow={this.showDialog}
            title={this.t('解码结果')}
            quick-close
            onConfirm={this.handleCopy}
            onUpdate:isShow={v => {
              this.showDialog = v;
            }}
          >
            {this.decodeContent}
          </Dialog>
        )}
      </div>
    );
  },
});
