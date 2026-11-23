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

import { Input as TInput, Popup as TPopup } from 'tdesign-vue-next';

import { defineComponent, ref, computed, watch } from 'vue';

import useLocale from '@/shared/composables/use-locale';

import './files-input.scss';

export default defineComponent({
  emits: ["update:value","update:select"],

  name: 'FilesInput',
  props: {
    value: {
      type: String,
      required: true,
    },
    availablePaths: {
      type: Array,
      required: true,
    },
  },
  setup(props, { emit }) {
    const { t } = useLocale();

    const isError = ref(false); // 输入错误状态
    const showValue = ref(''); // 显示的输入值
    const searchValue = ref(''); // 搜索框的值

    const isDropdownVisible = ref(false);

    // 过滤后的文件路径列表
    const filesSearchedPath = computed(() => {
      return props.availablePaths.filter((item: string) =>
        item.toLowerCase().includes(searchValue.value.toLowerCase()),
      );
    });

    // 监听可用路径变化
    watch(
      () => props.availablePaths,
      () => {
        if (showValue.value) {
          handleChange(showValue.value);
        }
      },
    );

    // 监听value值变化
    watch(
      () => props.value,
      val => {
        showValue.value = val;
      },
      { immediate: true },
    );

    // 处理输入值变化
    const handleChange = (val: string) => {
      if (validate(val)) {
        emit('update:value', val);
      } else {
        emit('update:value', '');
      }
    };

    // 处理选择选项
    const handleSelectOption = (val: string) => {
      validate(val);
      showValue.value = val;
      emit('update:value', val);
      emit('update:select', val);
      isDropdownVisible.value = false;
    };

    // 验证路径是否有效
    const validate = (val: string) => {
      let isAvailable = false;
      for (const path of props.availablePaths as string[]) {
        if (val.startsWith(path)) {
          isAvailable = true;
          break;
        }
      }
      const isValidated = isAvailable && !/\.\//.test(val);
      isError.value = !isValidated;
      return isValidated;
    };

    // 主渲染函数
    return () => (
      <TPopup
        class='extract-files-input'
        overlayClassName='extract-files-dropdown'
        placement='bottom-left'
        showArrow={false}
        trigger='click'
        visible={isDropdownVisible.value}
        onVisibleChange={visible => (isDropdownVisible.value = visible)}
        v-slots={{
          // 默认插槽：输入框
          default: () => (
            <TInput
              data-test-id='addNewExtraction_input_specifyFolder'
              status={isError.value ? 'error' : 'default'}
              value={showValue.value}
              onChange={value => {
                const val = String(value);
                showValue.value = val;
                handleChange(val);
              }}
            />
          ),
          // 内容插槽：下拉选项列表
          content: () => (
            <div class='extract-files-dropdown-content'>
              {/* 搜索框 */}
              <TInput
                class='extract-files-search'
                borderless
                placeholder={t('输入关键字搜索')}
                prefixIcon={() => <i class='bk-icon icon-search' />}
                value={searchValue.value}
                onChange={value => (searchValue.value = String(value))}
              />
              {/* 选项列表容器 */}
              <ul class='extract-files-options'>
                {/* 渲染过滤后的选项列表 */}
                {filesSearchedPath.value.map((option: string) => (
                  <li key={option}>
                    <button
                      class={['extract-files-option', { 'is-selected': option === showValue.value }]}
                      type='button'
                      aria-pressed={option === showValue.value}
                      onClick={() => handleSelectOption(option)}
                    >
                      {option}
                    </button>
                  </li>
                ))}
              </ul>
              {/* 空状态显示 */}
              {!filesSearchedPath.value.length && <div class='extract-files-empty'>{t('暂无选项')}</div>}
            </div>
          ),
        }}
      />
    );
  },
});
