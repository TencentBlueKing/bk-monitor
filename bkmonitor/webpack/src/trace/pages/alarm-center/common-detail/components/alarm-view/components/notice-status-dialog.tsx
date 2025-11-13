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

import { Dialog } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './notice-status-dialog.scss';

export default defineComponent({
  name: 'NoticeStatusDialog',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    actionId: {
      type: String,
      default: '',
    },
  },
  emits: {
    showChange: (_val: boolean) => true,
  },
  setup(_props, { emit }) {
    const { t } = useI18n();

    const handleShowChange = (val: boolean) => {
      emit('showChange', val);
    };
    return {
      t,
      handleShowChange,
    };
  },
  render() {
    return (
      <Dialog
        width={800}
        headerAlign='left'
        isShow={this.show}
        quickClose={true}
        title={this.t('通知状态')}
        onUpdate:isShow={this.handleShowChange}
      >
        <div class='notice-status-dialog-content'>ddd</div>
      </Dialog>
    );
  },
});
