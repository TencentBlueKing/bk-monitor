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

import { defineComponent, ref, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';

import InfoTips from '../../common-comp/info-tips';
import InputAddGroup from '../../common-comp/input-add-group';

import './log-path-config.scss';

export default defineComponent({
  name: 'LogPathConfig',
  props: {
    paths: {
      type: Array as PropType<{ value: string }[]>,
      required: true,
      default: () => [],
    },
    excludeFiles: {
      type: Array as PropType<{ value: string }[]>,
      required: true,
      default: () => [],
    },
  },
  emits: ['update'],

  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const isBlacklist = ref(false);
    const pathsRef = ref<{ validate: () => boolean } | null>(null);

    // 处理日志路径更新
    const handleUpdateUrl = (valueList: { value: string }[]) => {
      emit('update', 'paths', valueList);
    };

    // 处理黑名单显示切换
    const handleBlacklist = () => {
      isBlacklist.value = !isBlacklist.value;
    };

    // 处理黑名单路径更新
    const handleUpdateBlacklist = (valueList: { value: string }[]) => {
      emit('update', 'exclude_files', valueList);
    };

    /**
     * 校验方法，暴露给父组件
     * @returns {boolean} 校验是否通过
     */
    const validate = (): boolean => {
      if (pathsRef.value) {
        return pathsRef.value.validate();
      }
      return false;
    };

    // 暴露校验方法给父组件
    expose({
      validate,
    });

    return () => (
      <div class='log-path-config-main'>
        <div class='config-title-box'>
          <span class='config-title'>{t('日志路径')}</span>
          <InfoTips tips={t('日志文件的绝对路径，可使用 通配符')} />
        </div>
        <div class='config-box'>
          <div class='config-box-url'>
            <InputAddGroup
              ref={pathsRef}
              valueList={props.paths}
              on-update={handleUpdateUrl}
            />
          </div>
          <span
            class='config-link'
            on-click={handleBlacklist}
          >
            <i class={`bklog-icon link-icon bklog-${isBlacklist.value ? 'collapse' : 'expand'}-small`} />
            {t('路径黑名单')}
          </span>
          <InfoTips tips={t('可通过正则语法排除符合条件的匹配项 。如：匹配任意字符：.*')} />
          {isBlacklist.value && (
            <InputAddGroup
              valueList={props.excludeFiles}
              on-update={handleUpdateBlacklist}
            />
          )}
        </div>
      </div>
    );
  },
});
