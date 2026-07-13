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
import { type PropType, defineComponent, toRefs } from 'vue';

import { Message } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useTapdAuth } from './composables/use-tapd-auth';
import { revokeAuthApi } from './services/tapd';
import TapdAuthDialog from './tapd-auth-dialog/tapd-auth-dialog';
import TapdSideslider from './tapd-sideslider/tapd-sideslider';

import type { IssueDetail } from '../typing/detail';

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
    /** issues 第一个告警产生时间 (秒级时间戳) */
    firstAlarmTime: {
      type: [Number, String],
      default: 'now-1h',
    },
    issueDetail: {
      type: Object as PropType<IssueDetail>,
      default: () => null,
    },
  },
  emits: ['update:show'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const { show, bizId, issuesId, firstAlarmTime } = toRefs(props);

    const {
      loading,
      authDialogShow,
      createTapdSliderShow,
      workspaceList,
      authUrl,
      isAuth,
      revokeAuthLoading,
      handleWorkspaceSelect,
      handleAddWorkspace,
    } = useTapdAuth({ show, bizId, issuesId, firstAlarmTime });

    const handleShowChange = (val: boolean) => emit('update:show', val);

    /** 取消授权 */
    const handleRevokeAuth = () => {
      revokeAuthLoading.value = true;
      revokeAuthApi({
        bk_biz_id: bizId.value,
      })
        .then(() => {
          authDialogShow.value = false;
          createTapdSliderShow.value = false;
          isAuth.value = false;
          Message({
            theme: 'success',
            message: t('取消授权成功'),
          });
          handleShowChange(false);
        })
        .finally(() => {
          revokeAuthLoading.value = false;
        });
    };

    const handleAuthDialogShowChange = (val: boolean) => {
      if (createTapdSliderShow.value) {
        authDialogShow.value = val;
      } else {
        handleShowChange(val);
      }
    };

    return {
      loading,
      createTapdSliderShow,
      authDialogShow,
      workspaceList,
      authUrl,
      isAuth,
      revokeAuthLoading,
      handleWorkspaceSelect,
      handleAddWorkspace,
      handleRevokeAuth,
      handleShowChange,
      handleAuthDialogShowChange,
    };
  },
  render() {
    return (
      <div class='display: none'>
        <TapdSideslider
          bizId={this.bizId}
          issueDetail={this.issueDetail}
          issuesId={this.issuesId}
          show={this.createTapdSliderShow}
          workspaceList={this.workspaceList}
          onAddWorkspace={this.handleAddWorkspace}
          onRevokeAuth={this.handleRevokeAuth}
          onUpdate:show={this.handleShowChange}
        />
        <TapdAuthDialog
          authUrl={this.authUrl}
          isAuth={this.isAuth}
          loading={this.loading}
          revokeAuthLoading={this.revokeAuthLoading}
          show={this.authDialogShow}
          workspaceList={this.workspaceList}
          onRevokeAuth={this.handleRevokeAuth}
          onSelect={this.handleWorkspaceSelect}
          onUpdate:show={this.handleAuthDialogShowChange}
        />
      </div>
    );
  },
});
