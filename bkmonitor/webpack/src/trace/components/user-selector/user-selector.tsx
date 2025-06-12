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
import { type PropType, computed, defineComponent, onMounted, shallowRef } from 'vue';

import { BkUserSelector } from '@blueking/bk-user-selector/vue3';
import { getUserComponentConfig } from 'monitor-pc/common/user-display-name';

import type { IUserGroup } from './user-group';
import type { ConfigOptions } from '@blueking/bk-user-display-name';

import '@blueking/bk-user-selector/vue3/vue3.css';

export default defineComponent({
  name: 'UserSelector',
  props: {
    /**
     * 选中的用户ID列表
     */
    modelValue: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /**
     * 用户组列表
     */
    userGroupList: {
      type: Array as PropType<IUserGroup[]>,
      default: () => [],
    },
    /**
     * 用户组（备用字段）
     */
    userGroup: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    /**
     * 是否支持多选
     */
    multiple: {
      type: Boolean,
      default: true,
    },
    /**
     * 是否支持拖拽
     */
    draggable: {
      type: Boolean,
      default: false,
    },
    /**
     * 占位文本
     */
    placeholder: {
      type: String,
    },
    emptyText: {
      type: String,
    },
  },
  emits: {
    'update:modelValue': (value: string[]) => Array.isArray(value),
  },
  setup(props, { emit }) {
    const componentConfig = shallowRef<Partial<ConfigOptions>>({});
    const enableMultiTenantMode = computed(() => window.enable_multi_tenant_mode ?? false);
    onMounted(() => {
      componentConfig.value = getUserComponentConfig();
    });

    const handleUpdateModuleValue = (value: string[]) => {
      emit('update:modelValue', value);
    };

    return {
      enableMultiTenantMode,
      componentConfig,
      handleUpdateModuleValue,
    };
  },
  render() {
    if (!this.componentConfig.apiBaseUrl) {
      return undefined;
    }
    return (
      <BkUserSelector
        apiBaseUrl={this.componentConfig.apiBaseUrl}
        draggable={this.draggable}
        emptyText={this.emptyText}
        enableMultiTenantMode={this.enableMultiTenantMode}
        modelValue={this.modelValue}
        multiple={this.multiple}
        placeholder={this.placeholder}
        tenantId={this.componentConfig.tenantId}
        userGroup={this.userGroupList}
        onUpdate:modelValue={this.handleUpdateModuleValue}
      />
    );
  },
});
