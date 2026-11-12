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

import { defineComponent, ref, watch } from 'vue';
import { Dialog as TDialog } from 'tdesign-vue-next';

import { useDialogVisible } from '@/shared/global/overlay/index';
import { RelatedLogDialogPanel } from '../standalone-tab/related-log-dialog-panel';

import '../standalone-tab/index.scss';
import './index.scss';

export default defineComponent({
  emits: ['close-dialog', 'closeDialog', 'update:isShow'],

  name: 'ContextLog',
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    retrieveParams: {
      type: Object,
      required: true,
    },
    rowKey: {
      type: String,
      default: '',
    },
    logParams: {
      type: Object,
      default: () => ({}),
    },
    targetFields: {
      type: Array,
      default: () => [],
    },
    indexSetId: {
      type: Number,
      default: 0,
    },
    rowIndex: {
      type: Number,
      default: 0,
    },
  },
  setup(props, { emit }) {
    const { visible, setVisible, zIndex } = useDialogVisible(false, {
      id: 'retrieve-context-log-dialog',
      type: 'dialog',
      group: 'retrieve-related-log',
      rootSelector: '.log-context-dialog-main',
    });
    /** 每次打开递增，强制销毁并重建 panel，避免复用旧状态/缓存 */
    const mountKey = ref(0);

    watch(
      () => [props.isShow, props.rowKey] as const,
      ([show]) => {
        if (show) {
          mountKey.value += 1;
          setVisible(true);
          return;
        }
        setVisible(false);
      },
      { immediate: true },
    );

    const handleClose = () => {
      setVisible(false);
    };

    // Internal close / Escape / overlay exclusion must also reset the parent prop.
    watch(visible, (show, previous) => {
      if (!show && previous) emit('update:isShow', false);
    });

    const handleAfterLeave = () => {
      // A previous leave transition may finish after this panel is reopened.
      if (!visible.value) emit('close-dialog');
    };

    return () => (
      <TDialog
        dialogClassName='log-context-dialog-main'
        mode='full-screen'
        zIndex={zIndex.value}
        header={false}
        footer={false}
        draggable={false}
        closeOnEscKeydown
        closeOnOverlayClick={false}
        destroyOnClose
        visible={visible.value}
        onClosed={handleAfterLeave}
        onClose={handleClose}
      >
        {visible.value && (
          <RelatedLogDialogPanel
            key={mountKey.value}
            indexSetId={props.indexSetId}
            logParams={props.logParams}
            retrieveParams={props.retrieveParams}
            rowIndex={props.rowIndex}
            rowKey={props.rowKey}
            targetFields={props.targetFields as string[]}
          />
        )}
      </TDialog>
    );
  },
});
