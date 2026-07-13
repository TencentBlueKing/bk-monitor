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

import { type Ref, reactive, shallowRef, watch } from 'vue';

import { InfoBox } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { getUserWorkspaceApi, rebindWorkspaceApi, unbindWorkspaceApi } from '../services/tapd';

import type { TapdWorkspaceItem } from '../typing';

interface UseTapdAuthOptions {
  bizId: Ref<number | string>;
  firstAlarmTime: Ref<number | string>;
  issuesId: Ref<string>;
  show: Ref<boolean>;
}

export function useTapdAuth(options: UseTapdAuthOptions) {
  const { t } = useI18n();
  const { show, bizId, issuesId, firstAlarmTime } = options;
  const authDialogShow = shallowRef(false);
  const createTapdSliderShow = shallowRef(false);
  /** 项目列表 */
  const workspaceList = reactive<TapdWorkspaceItem[]>([]);
  /** 是否授权 */
  const isAuth = shallowRef(false);
  /** 是否有授权链接, 用于判断是否有访问TAPD关联功能 */
  const authUrl = shallowRef('');
  /** 项目关联链接 */
  const installUrl = shallowRef('');
  const revokeAuthLoading = shallowRef(false);
  const loading = shallowRef(false);

  const getAuth = async () => {
    installUrl.value = '';
    /** 授权成功后跳转的参数 */
    const successUrlParams = new URLSearchParams({
      tapdBizId: `${bizId.value}`,
      tapdIssueId: `${issuesId.value}`,
      tapdAuth: 'true',
      alarmType: 'issues',
    });

    /** 授权失败后跳转的参数，展示issues详情页 */
    const errorUrlParams = new URLSearchParams({
      detailBizId: `${bizId.value}`,
      detailId: `${issuesId.value}`,
      showDetail: 'true',
      issueFirstAlarmTime: `${firstAlarmTime.value}`,
      alarmType: 'issues',
    });
    try {
      loading.value = true;
      const data = await getUserWorkspaceApi({
        bk_biz_id: bizId.value,
        success_url: `${window.location.search}#/trace/alarm-center?${successUrlParams.toString()}`,
        error_url: `${window.location.search}#/trace/alarm-center?${errorUrlParams.toString()}`,
      });
      const list = data.items || [];
      workspaceList.splice(0, workspaceList.length, ...list.map(item => ({ ...item, loading: false })));
      installUrl.value = data.install_url;
      isAuth.value = true;
    } catch (err) {
      const { code, data: errData } = err as { code: number; data?: { auth_url: string } };
      isAuth.value = false;
      authUrl.value = errData?.auth_url || '';
      if (code === 403 && errData?.auth_url) {
        window.open(errData.auth_url, '_self');
      }
    }
    /** 如果有已关联的项目,展示创建单据侧栏，否则展示授权弹窗 */
    if (workspaceList.find(item => item.is_bound === 'bound')) {
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
        authDialogShow.value = true;
        getAuth();
      } else {
        createTapdSliderShow.value = false;
        authDialogShow.value = false;
      }
    },
    { immediate: true }
  );

  const handleUnboundWorkspace = (item: TapdWorkspaceItem) => {
    InfoBox({
      title: t('确认取消关联吗？'),
      onConfirm: async () => {
        try {
          await unbindWorkspaceApi({
            bk_biz_id: bizId.value,
            workspace_id: item.workspace_id,
          });
          // 取消关联成功后，更新本地项目状态，不需要重新获取列表
          const target = workspaceList.find(w => w.workspace_id === item.workspace_id);
          if (target) {
            target.is_bound = 'manually_unbound';
          }
          // 如果取消关联后没有已关联的项目了，关闭创建单据侧栏，展示授权弹窗
          if (!workspaceList.find(w => w.is_bound === 'bound')) {
            createTapdSliderShow.value = false;
            authDialogShow.value = true;
          }
        } catch (err) {
          console.error('取消关联失败', err);
        }
      },
    });
  };

  const handleWorkspaceSelect = (item: TapdWorkspaceItem) => {
    switch (item.is_bound) {
      case 'bound': {
        handleUnboundWorkspace(item);
        break;
      }
      case 'manually_unbound': {
        item.loading = true;
        rebindWorkspaceApi({
          bk_biz_id: bizId.value,
          workspace_id: item.workspace_id,
        })
          .then(() => {
            const target = workspaceList.find(w => w.workspace_id === item.workspace_id);
            if (target) {
              target.is_bound = 'bound';
              createTapdSliderShow.value = true;
              authDialogShow.value = false;
            }
          })
          .finally(() => {
            item.loading = false;
          });
        break;
      }
      default: {
        window.location.href = installUrl.value.replace('{workspace_id}', item.workspace_id);
      }
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
    authUrl,
    isAuth,
    revokeAuthLoading,
    handleWorkspaceSelect,
    handleAddWorkspace,
  };
}
