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

import { defineComponent, ref, nextTick, watch, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';

import './append-log-tags.scss';

/**
 * AppendLogTags
 * 附加日志标签组件
 */

type IExtraLabel = { key: string; value: string };
type IData = {
  extra_labels: IExtraLabel[];
  add_pod_label?: boolean;
  add_pod_annotation?: boolean;
};
export default defineComponent({
  name: 'AppendLogTags',

  props: {
    config: {
      type: Object as PropType<IData>,
      default: () => ({
        extra_labels: [],
        add_pod_label: false,
        add_pod_annotation: false,
      }),
    },
  },

  emits: ['change', 'validate-error'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const isExtraError = ref(false);
    // 创建本地数据副本
    const localData = ref({
      extra_labels: [...props.config.extra_labels], // 深拷贝避免引用问题
      add_pod_label: props.config.add_pod_label,
      add_pod_annotation: props.config.add_pod_annotation,
    });

    /**
     * 校验标签合法性：key存在时value不能为空
     * @returns 校验结果
     */
    const validateLabels = (): boolean => {
      isExtraError.value = false; // 重置错误状态

      // 遍历所有标签项检查
      for (const item of localData.value.extra_labels) {
        const keyExists = item.key.trim() !== '';
        const valueEmpty = item.value.trim() === '';

        if (keyExists && valueEmpty) {
          isExtraError.value = true; // 标记错误状态
          return false; // 校验失败
        }
      }

      return true; // 校验通过
    };

    const handleChangeSubmit = () => {
      // 先执行校验，校验通过才提交
      if (!validateLabels()) {
        emit('validate-error', t('当Key存在时，Value不能为空'));
        return;
      }

      emit('change', { ...localData.value }); // 传递拷贝数据避免外部修改影响内部
    };

    /**
     * 自定义标签输入变化处理
     * @param index - 标签索引
     * @param field - 字段名 ('key' | 'value')
     * @param value - 输入值
     */
    const handleExtraLabelChange = (index: number, field: string, value: string) => {
      // 安全校验：避免索引越界
      if (index < 0 || index >= localData.value.extra_labels.length) {
        return;
      }

      localData.value.extra_labels[index][field] = value;
      // 延迟提交变化，避免频繁触发
      nextTick(() => {
        handleChangeSubmit();
      });
    };

    // 添加标签
    const handleAddExtraLabel = () => {
      localData.value.extra_labels.push({ key: '', value: '' });
      handleChangeSubmit();
    };

    // 删除标签
    const handleDeleteExtraLabel = (index: number) => {
      if (localData.value.extra_labels.length <= 1) {
        return;
      }
      localData.value.extra_labels.splice(index, 1);
      handleChangeSubmit();
    };

    // 监听props变化，同步到本地数据
    const syncPropsToLocal = () => {
      localData.value = {
        extra_labels: [...props.config.extra_labels],
        add_pod_label: props.config.add_pod_label,
        add_pod_annotation: props.config.add_pod_annotation,
      };
    };
    watch(
      () => props.config,
      (newVal, oldVal) => {
        // 深度比较，避免相同引用时重复初始化
        if (JSON.stringify(newVal) !== JSON.stringify(oldVal)) {
          syncPropsToLocal();
        }
      },
      { deep: true },
    );

    return () => (
      <div class='append-log-tags-main'>
        {/* 错误提示*/}
        {/* {isExtraError.value && <div class='error-message'>{t('当Key存在时，Value不能为空')}</div>} */}

        <div class='input-group'>
          {localData.value.extra_labels.map((item: IExtraLabel, index: number) => (
            <div
              key={index}
              class='add-log-label'
            >
              <bk-input
                class={{
                  'extra-error': (item.key === '' || (item.key !== '' && item.value === '')) && isExtraError.value,
                }}
                placeholder={t('请输入Key')}
                value={item.key}
                on-Blur={() => {
                  // 失焦时重新校验
                  handleChangeSubmit();
                }}
                onInput={(val: string) => handleExtraLabelChange(index, 'key', val)}
              />
              <span class='symbol'>=</span>
              <bk-input
                class={{ 'extra-error': item.key !== '' && item.value === '' && isExtraError.value }}
                placeholder={t('请输入Value')}
                value={item.value}
                on-Blur={() => {
                  // 失焦时重新校验
                  handleChangeSubmit();
                }}
                onInput={(val: string) => handleExtraLabelChange(index, 'value', val)}
              />
              <div class='ml9'>
                <i
                  class='bk-icon icon-plus-circle-shape icons'
                  on-Click={handleAddExtraLabel}
                />
                <i
                  style={{ cursor: localData.value.extra_labels.length === 1 ? 'not-allowed' : 'pointer' }}
                  class={{
                    'bk-icon icon-minus-circle-shape icons ml9': true,
                    disabled: localData.value.extra_labels.length === 1,
                  }}
                  on-Click={() => handleDeleteExtraLabel(index)}
                />
              </div>
            </div>
          ))}
        </div>
        <div class='checkbox-group'>
          <bk-checkbox
            value={localData.value.add_pod_label}
            onChange={(val: boolean) => {
              localData.value.add_pod_label = val;
              handleChangeSubmit();
            }}
          >
            {t('自动添加 Pod 中的 label')}
          </bk-checkbox>
          <bk-checkbox
            value={localData.value.add_pod_annotation}
            onChange={(val: boolean) => {
              localData.value.add_pod_annotation = val;
              handleChangeSubmit();
            }}
          >
            {t('自动添加 Pod 中的 annotation')}
          </bk-checkbox>
        </div>
      </div>
    );
  },
});
