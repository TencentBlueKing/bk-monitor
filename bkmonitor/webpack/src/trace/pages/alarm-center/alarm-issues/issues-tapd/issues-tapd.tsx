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
import { defineComponent, shallowRef, watch } from 'vue';

import { request } from 'monitor-api/base';

import TapdAuthDialog from './tapd-auth-dialog/tapd-auth-dialog';
import TapdSideslider from './tapd-sideslider/tapd-sideslider';

import type { TapdWorkspaceItem } from '../typing/tapd';

const getUserWorkspace = request('GET', '/fta/issue/tapd/user_workspace/');

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
    const authDialogShow = shallowRef(false);
    const createTapdSliderShow = shallowRef(false);
    /** 项目列表 */
    const workspaceList = shallowRef<TapdWorkspaceItem[]>([]);
    /** 项目关联链接 */
    const installUrl = shallowRef('');
    const loading = shallowRef(false);

    const getAuth = async () => {
      workspaceList.value = [];
      installUrl.value = '';
      try {
        loading.value = true;
        const data = await getUserWorkspace({ bk_biz_id: props.bizId });
        workspaceList.value = data.items || [];
        installUrl.value = data.install_url;
      } catch (err) {
        const { code, data } = err as { code: number; data?: { auth_url: string } };
        if (code === 403) {
          window.location.href = data.auth_url;
        }
      }
      /** 如果有已关联的项目,展示创建单据侧栏，否则展示授权弹窗 */
      if (workspaceList.value.find(item => item.is_bound === 'bound')) {
        createTapdSliderShow.value = true;
        authDialogShow.value = false;
      } else {
        createTapdSliderShow.value = false;
        authDialogShow.value = true;
      }
      loading.value = false;
    };

    watch(
      () => props.show,
      show => {
        if (show) {
          getAuth();
        } else {
          createTapdSliderShow.value = false;
          authDialogShow.value = false;
        }
      }
    );

    const handleWorkspaceSelect = (item: TapdWorkspaceItem) => {
      if (item.is_bound !== 'bound') {
        window.location.href = installUrl.value.replace('{workspace_id}', item.workspace_id);
        return;
      }
    };

    const handleAddWorkspace = () => {
      authDialogShow.value = true;
    };

    const handleShowChange = (show: boolean) => {
      emit('update:show', show);
    };

    const handleAuthDialogShowChange = (show: boolean) => {
      /** 如果侧栏是打开的，只需要关闭授权弹窗 */
      if (createTapdSliderShow.value) {
        authDialogShow.value = show;
      } else {
        emit('update:show', show);
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
