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
import { computed, defineComponent, onMounted, shallowRef, useTemplateRef } from 'vue';

import { Button, Checkbox, Sideslider } from 'bkui-vue';

import { mockFields } from '../../components/tapd-field-form/mock';
import TapdFieldForm from '../../components/tapd-field-form/tapd-field-form';
import TapdFieldFormLoadingCom from '../../components/tapd-field-form/tapd-field-form-loading';
import TapdBasicForm from './components/tapd-basic-form';
import useUserConfig from '@/hooks/useUserConfig';

import type { IField } from '../../components/tapd-field-form/typing';
import type { CreateTapdDefaultSetting, CreateTapdIssueRequest, TapdWorkspaceItem } from '../../typing/tapd';

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
      default: '2',
    },
  },
  emits: ['update:show'],
  setup(props, { emit }) {
    /** 已关联 TAPD 项目数量 */
    const count = shallowRef(1);

    /** 基础表单组件 ref，用于调用表单校验方法 */
    const basicFormRef = useTemplateRef<InstanceType<typeof TapdBasicForm>>('basicForm');
    const tapdFieldFormRef = useTemplateRef<InstanceType<typeof TapdFieldForm>>('tapdFieldForm');
    /** 项目列表 */
    const workspaceList = shallowRef<TapdWorkspaceItem[]>([]);
    /** 用户设置的 TAPD 创建单据默认值 */
    const createTapdDefaultValue = shallowRef<CreateTapdDefaultSetting>({
      workspace_id: null,
      tapd_type: '',
    });
    /** 表单数据 */
    const formData = shallowRef<Pick<CreateTapdIssueRequest, 'sync_status' | 'tapd_type' | 'workspace_id'>>({
      workspace_id: null,
      tapd_type: 'story',
      sync_status: false,
    });
    /** 当前激活的 tab */
    const tabActive = shallowRef('add');
    /* 单据字段 */
    const tapdFields = shallowRef<IField[]>([]);
    /* 单据字段值 */
    const tapdFieldValue = shallowRef<Record<string, unknown>>({});
    /* 单据字段表单加载中 */
    const tapdFieldFormLoading = shallowRef(false);

    /** 用户配置 key */
    const CREATE_TAPD_DETAIL_SETTING = computed(() => {
      return `${props.bizId}_CREATE_TAPD_DETAIL_SETTING`;
    });

    /** 用户配置 hook */
    const { handleGetUserConfig, handleSetUserConfig } = useUserConfig();

    /**
     * @description 获取tapd单据字段
     */
    const getTapdFields = () => {
      tapdFieldFormLoading.value = true;
      tapdFieldValue.value = {};
      const params = {
        workspace_id: formData.value.workspace_id,
        tapd_type: formData.value.tapd_type,
      };
      console.log(params);
      setTimeout(() => {
        tapdFieldFormLoading.value = false;
        tapdFields.value = mockFields as IField[];
      }, 1000);
    };

    /**
     * 获取 TAPD 创建单据默认值
     */
    const getTapdDefaultValue = () => {
      if (!props.bizId) return;
      handleGetUserConfig<CreateTapdDefaultSetting>(CREATE_TAPD_DETAIL_SETTING.value).then(res => {
        if (res) {
          createTapdDefaultValue.value = res;
          formData.value = {
            workspace_id: res.workspace_id,
            tapd_type: res.tapd_type || 'story',
            sync_status: false,
          };
        } else {
          createTapdDefaultValue.value = {
            workspace_id: null,
            tapd_type: '',
          };
          formData.value = {
            workspace_id: null,
            tapd_type: 'story',
            sync_status: false,
          };
        }
        getTapdFields();
      });
    };

    /**
     * 处理 Sideslider 显示状态变化
     * @param isShow 是否显示
     */
    const handleShowChange = (isShow: boolean) => {
      emit('update:show', isShow);
    };

    /**
     * 处理 tab 切换
     * @param value tab 值
     */
    const handleTabChange = (value: string) => {
      tabActive.value = value;
    };

    /**
     * 处理设置/取消默认值
     * @param type 字段类型
     */
    const handleSetDefaultValue = type => {
      createTapdDefaultValue.value = {
        ...createTapdDefaultValue.value,
        // 如果当前选中值和默认值一致说明需要取消默认值，否则设置为当前选中值
        [type]: createTapdDefaultValue.value[type] === formData.value[type] ? null : formData.value[type],
      };
      // 取消默认
      handleSetUserConfig(JSON.stringify(createTapdDefaultValue.value));
    };

    /**
     * 处理确认创建
     */
    const handleConfirm = async () => {
      basicFormRef.value?.validate().then(() => {
        console.log('success');
      });
      const tapdFieldFormValid = await tapdFieldFormRef.value?.validate().catch(() => false);
      console.log(tapdFieldFormValid);
    };

    const handleFormDataChange = () => {
      getTapdFields();
    };

    /**
     * @description 单据字段值变化
     */
    const handleFieldValueChange = val => {
      tapdFieldValue.value = val;
    };

    onMounted(() => {
      getTapdDefaultValue();
    });

    return {
      count,
      formData,
      tabActive,
      workspaceList,
      createTapdDefaultValue,
      tapdFieldValue,
      tapdFields,
      tapdFieldFormLoading,
      handleShowChange,
      handleTabChange,
      handleSetDefaultValue,
      handleConfirm,
      handleFormDataChange,
      handleFieldValueChange,
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
                workspaceList={this.workspaceList}
                onSetDefaultValue={this.handleSetDefaultValue}
                onTabChange={this.handleTabChange}
                onUpdate:modelValue={this.handleFormDataChange}
              />
              {(() => {
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
                  theme='primary'
                  onClick={this.handleConfirm}
                >
                  {this.$t('确认创建')}
                </Button>
                <Button
                  onClick={() => {
                    this.handleShowChange(false);
                  }}
                >
                  {this.$t('取消')}
                </Button>
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
