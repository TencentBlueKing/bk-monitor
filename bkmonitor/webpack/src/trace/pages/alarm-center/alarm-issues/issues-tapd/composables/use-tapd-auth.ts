/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 THL A29 Limited, a Tencent company.  All rights reserved.
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

import { type Ref, shallowRef, watch } from 'vue';

import { getUserWorkspace } from '../services/tapd';

import type { TapdWorkspaceItem } from '../typing';

interface UseTapdAuthOptions {
  bizId: Ref<number | string>;
  show: Ref<boolean>;
}

export function useTapdAuth(options: UseTapdAuthOptions) {
  const { show, bizId } = options;

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
      const data = await getUserWorkspace({ bk_biz_id: bizId.value });
      workspaceList.value = data.items || [];
      installUrl.value = data.install_url;
    } catch (err) {
      const { code, data: errData } = err as { code: number; data?: { auth_url: string } };
      if (code === 403) {
        window.location.href = errData.auth_url;
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
    () => show.value,
    val => {
      if (val) {
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
    }
  };

  const handleAddWorkspace = () => {
    authDialogShow.value = true;
  };

  return {
    loading,
    authDialogShow,
    createTapdSliderShow,
    workspaceList,
    handleWorkspaceSelect,
    handleAddWorkspace,
  };
}
