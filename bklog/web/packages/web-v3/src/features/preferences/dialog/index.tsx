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


import { useApplicationStore } from '@/app/state/domains/application-store';
import { defineComponent, type PropType } from 'vue';

import { Dialog } from 'tdesign-vue-next';


import './index.scss';

interface IProps {
  value: boolean;
  title: string;
}

export default defineComponent({
compatConfig: { MODE: 3 },
name: 'global-dialog',
props: {value: { type: Boolean, default: false },
title: { type: String, required: true, default: '' }},
emits: ['change', 'menu-change', "menuChange"],
computed: {},
methods: {},
setup(props, { slots, emit }) {
    const store = useApplicationStore();
    return () => props.value ? (
      <Dialog
        style='z-index: var(--bklog-z-dialog);'
        width='100%'
        dialogClassName='global-dialog'
        top={0}
        header={false}
        closeBtn={false}
        draggable={false}
        destroyOnClose={true}
        footer={false}
        showOverlay={false}
        visible={props.value}
      >
        <div class={`global-container ${store.showAlert ? 'is-show-notice' : ''}`}>
          <div class='global-title'>
            <div />
            <span>{props.title}</span>
            <div
              class='bk-icon icon-close'
              onClick={() => {
                emit('change', false);
              }}
            />
          </div>
          <div class='center-box'>
            <div class='content-panel'>{slots.default?.()}</div>
          </div>
        </div>
      </Dialog>
    ) : null;
  }
});
