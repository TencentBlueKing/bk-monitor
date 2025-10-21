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
import { computed, defineComponent, ref, watch } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import BkUserSelector from '@blueking/bk-user-selector/vue2';

import './index.scss';

export default defineComponent({
  name: 'ValidateUserSelector',
  components: {
    BkUserSelector,
  },
  props: {
    // 输入值
    value: {
      type: Array<string>,
      default: () => [],
    },
    // 占位符
    placeholder: {
      type: String,
      default: '',
    },
    // API 地址
    api: {
      type: String,
      default: '',
    },
    // 是否禁用
    disabled: {
      type: Boolean,
      default: false,
    },
    multiple: {
      type: Boolean,
      default: true,
    },
    customStyle: {
      type: String,
      default: 'width: 400px',
    },
    onChange: { type: Function },
  },
  emits: ['change', 'update'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();

    const localValue = ref<string[]>([]);
    const isError = ref(false); // 是否显示错误状态

    const tenantId = computed(() => store.state.userMeta.bk_tenant_id);

    // 开发环境放自己的本地测试地址即可
    const apiBaseUrl = window.BK_LOGIN_URL;

    watch(
      () => props.value,
      () => {
        localValue.value = structuredClone(props.value);
      },
      {
        immediate: true,
        deep: true,
      },
    );

    // 处理选择变化
    const handleChange = (val: string[]) => {
      const realVal = val.filter((item) => item !== undefined);
      localValue.value = realVal;
      isError.value = !realVal.length;
      emit('change', realVal);
      emit('update', realVal);
    };

    // 失焦时校验
    const handleBlur = () => {
      isError.value = !props.value.length;
    };

    return () => (
      <div class='validate-user-selector'>
        <bk-user-selector
          style={props.customStyle}
          class={isError.value ? 'is-error' : ''}
          api-base-url={apiBaseUrl}
          disabled={props.disabled}
          empty-text={t('无匹配人员')}
          enableMultiTenantMode={!!tenantId.value}
          modelValue={localValue.value}
          multiple={props.multiple}
          placeholder={props.placeholder}
          tenant-id={tenantId.value}
          onBlur={handleBlur}
          onChange={handleChange}
        />
      </div>
    );
  },
});
