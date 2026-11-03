
import { Button as TButton } from 'tdesign-vue-next';
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
import { defineComponent, ref } from 'vue';
import TextHighlight from '@/shared/ui/text-highlight';

import FilterRule from '@/features/collection/filter-rule/index';
import useLocale from '@/shared/composables/use-locale';

import DebugTool from './debug-tool/index';

import './index.scss';

export default defineComponent({
  emits: ["submit","reset"],

  name: 'RuleConfigOperate',
  components: {
    FilterRule,
    TextHighlight,
    DebugTool,
  },
  props: {
    maxLogLength: {
      type: Number,
      default: 10_000,
    },
    ruleList: {
      type: Array,
      default: () => [],
    },
    collectorConfigId: {
      type: String,
      default: '',
    },
    indexSetId: {
      type: [String, Number],
      default: '',
    },
    isExternal: {
      type: Boolean,
      default: false,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();

    const isSaving = ref(false); // 保存loading
    const showDebug = ref(false); // 是否展开调试弹窗

    const handleSubmit = () => {
      isSaving.value = true;
      emit('submit');
    };

    const handleReset = () => {
      emit('reset');
    };

    expose({
      setSaveLoading: (loading: boolean) => {
        isSaving.value = loading;
      },
    });

    return () => (
      <div class='rule-config-operate'>
        <div class='btns-main'>
          <TButton
            loading={isSaving.value}
            theme='primary'
            onClick={handleSubmit}
          >
            {t('保存')}
          </TButton>
          <TButton
            theme='primary'
            
            onClick={() => (showDebug.value = !showDebug.value)} variant={(true) ? 'outline' : 'base'}
          >
            <span style='margin-right: 4px'>{t('调试工具')}</span>
            <log-icon
              type={showDebug.value ? 'angle-double-down' : 'angle-double-up'}
              common
            />
          </TButton>
          <TButton onClick={handleReset}>{t('重置')}</TButton>
        </div>
        {showDebug.value && (
          <debug-tool
            collectorConfigId={props.collectorConfigId}
            indexSetId={props.indexSetId}
            isExternal={props.isExternal}
            maxLogLength={props.maxLogLength}
            ruleList={props.ruleList}
          />
        )}
      </div>
    );
  },
});
