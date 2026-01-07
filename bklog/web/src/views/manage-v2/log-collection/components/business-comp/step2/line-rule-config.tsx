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

import { defineComponent, ref, reactive, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';
import type { ICollectionParams } from '../../../type';

import MultilineRegDialog from '../../business-comp/step2/multiline-reg-dialog';
import InfoTips from '../../common-comp/info-tips'; // 多行正则对话框组件

import './line-rule-config.scss';

/**
 * LineRuleConfig 组件，用于配置行首正则规则
 */
export default defineComponent({
  name: 'LineRuleConfig', // 组件名称
  props: {
    data: {
      type: Object as PropType<ICollectionParams>,
      required: true, // 必需属性
      default: () => ({
        // 默认值
        multiline_pattern: '', // 多行模式
        multiline_max_lines: '', // 最大匹配行数
        multiline_timeout: '', // 超时时间
      }),
    },
  },
  emits: ['debug-reg', 'update'], // 组件触发的事件

  setup(props, { emit, expose }) {
    const { t } = useLocale(); // 国际化翻译函数
    const showMultilineRegDialog = ref(false); // 控制正则调试弹窗的显示状态
    // 错误状态管理
    const errorState = reactive({
      multiline_pattern: false,
      multiline_max_lines: false,
      multiline_timeout: false,
    });
    /**
     * 处理输入框内容变化
     * @param field - 字段名
     * @param val - 新的值
     */
    const handleInputChange = (field: string, val: string) => {
      const MULTILINE_FIELDS = ['multiline_pattern', 'multiline_max_lines', 'multiline_timeout'];
      emit('update', {
        // 触发更新事件
        ...props.data, // 保留原有数据
        [field]: val, // 更新指定字段
      });
      // 输入时清除对应字段的错误状态
      if (MULTILINE_FIELDS.includes(field) && errorState[field] && val && String(val).trim()) {
        errorState[field] = false;
      }
    };

    /**
     * 显示行首正则调试弹窗
     */
    const handleDebugReg = () => {
      showMultilineRegDialog.value = true;
    };
    /**
     * 关闭行首正则调试弹窗
     * @param val - 控制弹窗显示状态的布尔值
     */
    const handleCancelMultilineReg = (val: boolean) => {
      showMultilineRegDialog.value = val;
    };
    /**
     * 检查值是否为空
     * @param field
     * @returns
     */
    const checkField = (field: string) => {
      const value = props.data[field as keyof typeof props.data];
      return !value || !String(value).trim();
    };
    /**
     * 校验方法：检查 multiline_pattern、multiline_max_lines、multiline_timeout 是否为空值
     * @returns {boolean} 校验是否通过，true表示通过，false表示失败
     */
    const validate = (): boolean => {
      const fields = ['multiline_pattern', 'multiline_max_lines', 'multiline_timeout'];
      fields.forEach((field: string) => {
        errorState[field] = checkField(field);
      });
      /**
       * 返回校验结果：所有字段都不为空才返回 true
       */
      return fields.every(field => !errorState[field]);
    };

    // 暴露校验方法给父组件
    expose({
      validate,
    });

    return () => (
      <div class='line-rule'>
        <div class='label-title text-left'>{t('行首正则')}</div>
        <div class='rule-reg'>
          <bk-input
            class={{ 'reg-input': true, 'input-error': errorState.multiline_pattern }}
            value={props.data.multiline_pattern}
            on-input={(val: string) => handleInputChange('multiline_pattern', val)}
          />
          <span
            class='form-link debug'
            on-Click={handleDebugReg}
          >
            {t('调试')}
          </span>
        </div>
        <div class='line-rule-box'>
          <div class='line-rule-box-item'>
            <div class='label-title no-require text-left'>{t('最多匹配')}</div>
            <bk-input
              class={{ 'input-error': errorState.multiline_max_lines }}
              value={props.data.multiline_max_lines}
              on-input={(val: string) => handleInputChange('multiline_max_lines', val)}
            >
              <div
                class='group-text'
                slot='append'
              >
                {t('行')}
              </div>
            </bk-input>
          </div>
          <div class='line-rule-box-right'>
            <div class='label-title no-require text-left'>{t('最大耗时')}</div>
            <bk-input
              class={{ 'time-box': true, 'input-error': errorState.multiline_timeout }}
              value={props.data.multiline_timeout}
              on-input={(val: string) => handleInputChange('multiline_timeout', val)}
            >
              <div
                class='group-text'
                slot='append'
              >
                {t('秒')}
              </div>
            </bk-input>
            <InfoTips tips={t('建议配置 1s, 配置过长时间可能会导致日志积压')} />
          </div>
        </div>

        <MultilineRegDialog
          oldPattern={props.data.multiline_pattern}
          showDialog={showMultilineRegDialog.value}
          on-cancel={handleCancelMultilineReg}
          on-update={(val: string) => {
            handleInputChange('multiline_pattern', val);
          }}
        />
      </div>
    );
  },
});
