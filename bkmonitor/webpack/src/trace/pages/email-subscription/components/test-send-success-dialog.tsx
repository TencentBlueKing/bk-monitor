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
import { defineComponent } from 'vue';
import { useI18n } from 'vue-i18n';
import { Dialog } from 'bkui-vue';

import './test-send-success-dialog.scss';

export default defineComponent({
  name: 'TestSendSuccessDialog',
  props: {
    modelValue: {
      type: Boolean,
      default: false
    }
  },
  emits: ['update:modelValue'],
  setup(props, { emit }) {
    const { t } = useI18n();
    return {
      t,
      props,
      emit
    };
  },
  render() {
    return (
      <Dialog
        isShow={this.modelValue}
        dialog-type='show'
        ext-cls='test-send-result-dialog'
        onClosed={() => {
          this.emit('update:modelValue', false);
        }}
        v-slots={{
          default: () => {
            return (
              <div style='margin-left: 30px;padding-top: 14px;'>{this.t('邮件任务已生成，请一分钟后到邮箱查看')}</div>
            );
          },
          header: () => {
            return (
              <div>
                <i
                  class='icon-monitor icon-mc-check-fill'
                  style='color: #2dca56;'
                />
                <span style='margin-left: 10px;font-weight: bold;'>{this.t('发送测试邮件成功')}</span>
              </div>
            );
          }
        }}
      ></Dialog>
    );
  }
});
