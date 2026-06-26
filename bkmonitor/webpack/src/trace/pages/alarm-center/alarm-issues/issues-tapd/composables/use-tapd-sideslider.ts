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

import { type Ref, computed, shallowRef, useTemplateRef, watch } from 'vue';

import { mockFields } from '../../components/tapd-field-form/mock';
import useUserConfig from '@/hooks/useUserConfig';

import type tapdFieldForm from '../../components/tapd-field-form/tapd-field-form';
import type tapdRelation from '../tapd-relation/tapd-relation';
import type tapdBasicForm from '../tapd-sideslider/components/tapd-basic-form';
import type { CreateTapdDefaultSetting } from '../typing';
import type { TapdWorkspaceItem } from '../typing';

interface UseTapdSidesliderOptions {
  bizId: Ref<number | string>;
  show: Ref<boolean>;
  workspaceList: Ref<TapdWorkspaceItem[]>;
}

export function useTapdSideslider(options: UseTapdSidesliderOptions) {
  const { show, bizId, workspaceList } = options;

  /** 已关联 TAPD 项目数量 */
  const count = shallowRef(1);
  /** 基础表单组件 ref，用于调用表单校验方法 - 由外部传入 */
  const basicFormRef = useTemplateRef<InstanceType<typeof tapdBasicForm>>('basicForm');
  const tapdFieldFormRef = useTemplateRef<InstanceType<typeof tapdFieldForm>>('tapdFieldForm');
  const tapdRelationRef = useTemplateRef<InstanceType<typeof tapdRelation>>('tapdRelation');
  /** 用户设置的 TAPD 创建单据默认值 */
  const createTapdDefaultValue = shallowRef<CreateTapdDefaultSetting>({
    workspace_id: null,
    tapd_type: '',
  });
  /** 表单数据 */
  const formData = shallowRef<{ sync_status: boolean; tapd_type: string; workspace_id: number | string }>({
    workspace_id: '',
    tapd_type: 'story',
    sync_status: false,
  });
  const filterWorkspaceList = computed(() => workspaceList.value.filter(item => item.is_bound === 'bound'));
  /** 当前激活的 tab */
  const tabActive = shallowRef('add');
  /* 单据字段 */
  const tapdFields = shallowRef([]);
  /* 单据字段值 */
  const tapdFieldValue = shallowRef<Record<string, unknown>>({});
  /* 单据字段表单加载中 */
  const tapdFieldFormLoading = shallowRef(false);
  // Issue 关联指定 TAPD 单据
  const linkTapdIds = shallowRef<string[]>([]);

  /** 用户配置 key */
  const CREATE_TAPD_DETAIL_SETTING = computed(() => `${bizId.value}_CREATE_TAPD_DETAIL_SETTING`);

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
      tapdFields.value = mockFields;
    }, 1000);
  };

  /**
   * 获取 TAPD 创建单据默认值
   */
  const getTapdDefaultValue = () => {
    if (!bizId.value) return;
    handleGetUserConfig<CreateTapdDefaultSetting>(CREATE_TAPD_DETAIL_SETTING.value).then(res => {
      if (res) {
        createTapdDefaultValue.value = res;
        const targetWorkspace = filterWorkspaceList.value.find(item => item.workspace_id === res.workspace_id);
        formData.value = {
          workspace_id: targetWorkspace ? res.workspace_id : filterWorkspaceList.value?.[0]?.workspace_id,
          tapd_type: res.tapd_type || 'story',
          sync_status: false,
        };
      } else {
        createTapdDefaultValue.value = { workspace_id: null, tapd_type: '' };
        formData.value = {
          workspace_id: filterWorkspaceList.value[0]?.workspace_id ?? '',
          tapd_type: 'story',
          sync_status: false,
        };
      }
      getTapdFields();
    });
  };

  watch(
    () => show.value,
    val => {
      if (val) getTapdDefaultValue();
    }
  );

  /**
   * 处理 tab 切换
   */
  const handleTabChange = (value: string) => {
    tabActive.value = value;
  };

  /**
   * 处理设置/取消默认值
   */
  const handleSetDefaultValue = type => {
    createTapdDefaultValue.value = {
      ...createTapdDefaultValue.value,
      [type]: createTapdDefaultValue.value[type] === formData.value[type] ? null : formData.value[type],
    };
    handleSetUserConfig(JSON.stringify(createTapdDefaultValue.value));
  };

  /**
   * 处理确认创建
   */
  const handleConfirm = async () => {
    basicFormRef.value?.validate().then(() => console.log('success'));
    if (tabActive.value === 'link') {
      const linkTapdIdsValid = await tapdRelationRef.value?.validate().catch(() => false);
      console.log(linkTapdIdsValid);
    } else {
      const tapdFieldFormValid = await tapdFieldFormRef.value?.validate().catch(() => false);
      console.log(tapdFieldFormValid);
    }
  };

  const handleFormDataChange = () => {
    getTapdFields();
  };

  /** 单据字段值变化 */
  const handleFieldValueChange = (val: Record<string, unknown>) => {
    tapdFieldValue.value = val;
  };

  const handleLinkTapdIdsChange = (val: string[]) => {
    linkTapdIds.value = val;
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
    handleTabChange,
    handleSetDefaultValue,
    handleConfirm,
    handleFormDataChange,
    handleFieldValueChange,
    handleLinkTapdIdsChange,
  };
}
