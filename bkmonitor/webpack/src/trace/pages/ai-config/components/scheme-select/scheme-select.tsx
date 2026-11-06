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
import { type PropType, defineComponent } from 'vue';

import { Popover, Select } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import type { ISchemeItem, PlanIdValue } from '../../typings';

import './scheme-select.scss';

/**
 * @description 默认方案表单项：必填 label + 方案下拉（悬浮展示方案详情）+ 错误提示
 */
export default defineComponent({
  name: 'SchemeSelect',
  props: {
    modelValue: {
      type: [String, Number] as PropType<PlanIdValue>,
      default: '',
    },
    list: {
      type: Array as PropType<ISchemeItem[]>,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
    errorMsg: {
      type: String,
      default: '',
    },
  },
  emits: {
    change: (_planId: PlanIdValue) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    /** 方案详情：悬浮在选项上时展示，帮助判断方案适用性 */
    const renderSchemeDetail = (item: ISchemeItem) => (
      <div class='scheme-detail'>
        <div class='detail-item'>
          <span class='detail-label'>{t('依赖历史数据长度')}:</span>
          <span>{item.ts_depend}</span>
        </div>
        <div class='detail-item'>
          <span class='detail-label'>{t('数据频率')}:</span>
          <span>{item.ts_freq || t('无限制')}</span>
        </div>
        <div class='detail-item'>
          <span class='detail-label'>{t('描述')}:</span>
          <span class='detail-desc'>{item.description}</span>
        </div>
      </div>
    );

    return () => (
      <div class='scheme-select'>
        <div class='scheme-select-main'>
          <label class='scheme-select-label'>{t('默认方案')}</label>
          {props.loading ? (
            <div class='skeleton-element scheme-select-skeleton' />
          ) : (
            <Select
              class={['scheme-select-input', { 'is-error': !!props.errorMsg }]}
              clearable={false}
              filterable={true}
              modelValue={props.modelValue}
              placeholder={t('选择方案')}
              searchPlaceholder={t('请输入 关键字')}
              onChange={(planId: PlanIdValue) => emit('change', planId)}
            >
              {props.list.map(item => (
                <Select.Option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                >
                  <Popover
                    extCls='scheme-detail-popover'
                    placement='right-end'
                    popoverDelay={[200, 0]}
                    theme='light'
                  >
                    {{
                      default: () => <div class='scheme-option-name'>{item.name}</div>,
                      content: () => renderSchemeDetail(item),
                    }}
                  </Popover>
                </Select.Option>
              ))}
            </Select>
          )}
        </div>
        {props.errorMsg ? <p class='scheme-select-error'>{props.errorMsg}</p> : null}
      </div>
    );
  },
});
