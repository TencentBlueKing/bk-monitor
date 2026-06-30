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
import { type PropType, defineComponent, toRefs, useTemplateRef } from 'vue';

import { Button, Checkbox, Message, Sideslider } from 'bkui-vue';
import { linkIssueToTapd } from 'monitor-api/modules/issue';

import TapdFieldForm from '../../components/tapd-field-form/tapd-field-form';
import TapdFieldFormLoadingCom from '../../components/tapd-field-form/tapd-field-form-loading';
import { useTapdSideslider } from '../composables/use-tapd-sideslider';
import { type TCreateTapdApiParams, createTapdApi } from '../services/create-tapd';
import TapdRelation from '../tapd-relation/tapd-relation';
import TapdBasicForm from './components/tapd-basic-form';

import type { TapdWorkspaceItem } from '../typing';

import './tapd-sideslider.scss';

export default defineComponent({
  name: 'TapdSideslider',
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
    workspaceList: {
      type: Array as PropType<TapdWorkspaceItem[]>,
      default: () => [],
    },
  },
  emits: ['update:show', 'addWorkspace'],
  setup(props, { emit }) {
    /** 基础表单组件 ref，用于调用表单校验方法 - 由外部传入 */
    const basicFormRef = useTemplateRef<InstanceType<typeof TapdBasicForm>>('basicForm');
    const tapdFieldFormRef = useTemplateRef<InstanceType<typeof TapdFieldForm>>('tapdFieldForm');
    const tapdRelationRef = useTemplateRef<InstanceType<typeof TapdRelation>>('tapdRelation');

    const { show, bizId, issuesId, workspaceList } = toRefs(props);

    const {
      count,
      formData,
      tabActive,
      createTapdDefaultValue,
      filterWorkspaceList,
      tapdFieldValue,
      tapdFields,
      tapdFieldFormLoading,
      linkTapdIds,
      confirmLoading,
      linkTapdItems,
      handleTabChange,
      handleSetDefaultValue,
      handleFormDataChange,
      handleFieldValueChange,
      handleLinkTapdIdsChange,
      handleLinkTapdItemsChange,
    } = useTapdSideslider({ show, bizId, workspaceList, issuesId });

    const handleShowChange = (isShow: boolean) => emit('update:show', isShow);
    const handleAddWorkspace = () => emit('addWorkspace');

    /**
     * 处理确认创建
     */
    const handleConfirm = async () => {
      if (confirmLoading.value) {
        return;
      }
      const basicFormValid = await basicFormRef.value
        ?.validate()
        .then(() => true)
        .catch(() => false);
      if (tabActive.value === 'link') {
        const linkTapdIdsValid = await tapdRelationRef.value?.validate().catch(() => false);

        if (basicFormValid && linkTapdIdsValid) {
          const params = {
            bk_biz_id: bizId.value,
            issue_id: issuesId.value,
            workspace_id: formData.value.workspace_id,
            sync_status: formData.value.sync_status,
            tapd_items: linkTapdItems.value,
          };
          confirmLoading.value = true;
          const success = await linkIssueToTapd(params).catch(() => null);
          Message({
            type: success ? 'success' : 'error',
            message: success ? window.i18n.t('关联单据成功') : window.i18n.t('关联单据失败'),
          });
          if (success) {
            handleShowChange(false);
          }
        }
      } else {
        const tapdFieldFormValid = await tapdFieldFormRef.value?.validate().catch(() => false);
        if (basicFormValid && tapdFieldFormValid) {
          const params = {
            bk_biz_id: bizId.value,
            issue_id: issuesId.value,
            workspace_id: formData.value.workspace_id,
            sync_status: formData.value.sync_status,
            tapd_type: formData.value.tapd_type,
            ...tapdFieldValue.value,
          };
          confirmLoading.value = true;
          const success = await createTapdApi(params as TCreateTapdApiParams).catch(() => null);
          Message({
            type: success ? 'success' : 'error',
            message: success ? window.i18n.t('创建单据成功') : window.i18n.t('创建单据失败'),
          });
          if (success) {
            handleShowChange(false);
          }
        }
      }
      confirmLoading.value = false;
    };

    return {
      count,
      formData,
      tabActive,
      createTapdDefaultValue,
      filterWorkspaceList,
      tapdFieldValue,
      tapdFields,
      tapdFieldFormLoading,
      linkTapdIds,
      confirmLoading,
      handleShowChange,
      handleTabChange,
      handleSetDefaultValue,
      handleConfirm,
      handleFormDataChange,
      handleFieldValueChange,
      handleLinkTapdIdsChange,
      handleAddWorkspace,
      handleLinkTapdItemsChange,
    };
  },
  render() {
    return (
      <Sideslider
        width='800px'
        extCls='create-tapd-sides-slider'
        v-slots={{
          header: () => (
            <div class='create-tapd-side-slider-header'>
              <div class='create-tapd-side-slider-header-title'>{this.$t('TAPD 单据')}</div>
              <div class='tapd-auth-text'>
                <i class='icon-monitor icon-mc-check-fill' />
                <span class='tips-text'>
                  {this.$t('已授权 TAPD 项目列表 · 已关联 {count} 个项目', { count: this.count })},
                </span>
                <span class='cancel-auth-btn'>{this.$t('解除授权')}</span>
              </div>
            </div>
          ),
          default: () => (
            <div class='create-tapd-side-slider-content'>
              <TapdBasicForm
                ref='basicForm'
                v-model={this.formData}
                defaultValue={this.createTapdDefaultValue}
                tabActive={this.tabActive}
                workspaceList={this.filterWorkspaceList}
                onAddWorkspace={this.handleAddWorkspace}
                onSetDefaultValue={this.handleSetDefaultValue}
                onTabChange={this.handleTabChange}
                onUpdate:modelValue={this.handleFormDataChange}
              />
              {(() => {
                if (this.tabActive === 'add') {
                  if (this.tapdFieldFormLoading) {
                    return <TapdFieldFormLoadingCom style='margin: 13px 40px' />;
                  }
                  if (this.tapdFields.length) {
                    return (
                      <TapdFieldForm
                        ref='tapdFieldForm'
                        style='margin: 13px 40px'
                        fields={this.tapdFields}
                        value={this.tapdFieldValue}
                        onChange={this.handleFieldValueChange}
                      />
                    );
                  }
                }
                if (this.tabActive === 'link') {
                  return (
                    <TapdRelation
                      ref='tapdRelation'
                      style='margin: 13px 40px'
                      bizId={this.bizId}
                      modelValue={this.linkTapdIds}
                      tapdType={this.formData.tapd_type}
                      workspaceId={this.formData.workspace_id}
                      onChangeTapdItems={this.handleLinkTapdItemsChange}
                      onUpdate:modelValue={this.handleLinkTapdIdsChange}
                    />
                  );
                }
                return undefined;
              })()}
              <div class='create-tapd-content'>
                <div class='sync-tapd-status'>
                  <Checkbox v-model={this.formData.sync_status}>
                    <span class='sync-tapd-status-title'>{this.$t('同步单据状态')}</span>
                  </Checkbox>
                  <div class='sync-tapd-status-tips'>
                    <div class='tip-item'>
                      <span class='tip-dot' />
                      <span class='tip-text'>
                        <i18n-t keypath='开启后，当本单据在外部平台进入「已完成」类状态{0}时，本 Issue 将自动流转为「已解决」。'>
                          <span style='color: #21A380'>（如 TAPD「已关闭 / 已解决」、GitHub closed）</span>
                        </i18n-t>
                      </span>
                    </div>
                    <div class='tip-item'>
                      <span class='tip-dot' />
                      <span class='tip-text'>{this.$t('未勾选，则仅保留关联，不因单据关闭而自动关 Issue。')}</span>
                    </div>
                  </div>
                </div>
              </div>
              <div class='create-tapd-footer'>
                <Button
                  loading={this.confirmLoading}
                  theme='primary'
                  onClick={this.handleConfirm}
                >
                  {this.$t('确认创建')}
                </Button>
                <Button onClick={() => this.handleShowChange(false)}>{this.$t('取消')}</Button>
              </div>
            </div>
          ),
        }}
        isShow={this.show}
        onUpdate:isShow={this.handleShowChange}
      />
    );
  },
});
