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
import { defineComponent, toRef } from 'vue';

import { useTapdAuth } from './composables/use-tapd-auth';
import TapdAuthDialog from './tapd-auth-dialog/tapd-auth-dialog';
import TapdSideslider from './tapd-sideslider/tapd-sideslider';

export default defineComponent({
  name: 'IssuesTapd',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    bizId: {
      type: [Number, String],
      default: '',
    },
    issuesId: {
      type: String,
      default: '',
    },
  },
  emits: ['update:show'],
  setup(props, { emit }) {
    const showRef = toRef(props, 'show');
    const bizIdRef = toRef(props, 'bizId');

    const { loading, authDialogShow, createTapdSliderShow, workspaceList, handleWorkspaceSelect, handleAddWorkspace } =
      useTapdAuth({ show: showRef, bizId: bizIdRef });

    const handleShowChange = (val: boolean) => emit('update:show', val);

    const handleAuthDialogShowChange = (val: boolean) => {
      if (createTapdSliderShow.value) {
        authDialogShow.value = val;
      } else {
        emit('update:show', val);
      }
    };

    return {
      loading,
      createTapdSliderShow,
      authDialogShow,
      workspaceList,
      handleWorkspaceSelect,
      handleAddWorkspace,
      handleShowChange,
      handleAuthDialogShowChange,
    };
  },
  render() {
    return (
      <div class='display: none'>
        <TapdSideslider
          bizId={this.bizId}
          show={this.createTapdSliderShow}
          workspaceList={this.workspaceList}
          onAddWorkspace={this.handleAddWorkspace}
          onUpdate:show={this.handleShowChange}
        />
        <TapdAuthDialog
          loading={this.loading}
          show={this.authDialogShow}
          workspaceList={this.workspaceList}
          onSelect={this.handleWorkspaceSelect}
          onUpdate:show={this.handleAuthDialogShowChange}
        />
      </div>
    );
  },
});
