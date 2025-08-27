/*
 * @Author: EmilyMei 447693773@qq.com
 * @Date: 2025-08-22 15:54:37
 * @LastEditors: EmilyMei 447693773@qq.com
 * @LastEditTime: 2025-08-26 16:55:58
 * @FilePath: /web/src/views/manage-v2/log-collection/components/create-operation/index.tsx
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
 */
/*
 * @Author: EmilyMei 447693773@qq.com
 * @Date: 2025-08-22 15:54:37
 * @LastEditors: EmilyMei 447693773@qq.com
 * @LastEditTime: 2025-08-26 15:53:55
 * @FilePath: /web/src/views/manage-v2/log-collection/components/create-operation/index.tsx
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
 */
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

import { defineComponent, onBeforeUnmount, onMounted, ref } from 'vue';

import useLocale from '@/hooks/use-locale';

import StepClassify from './step1-classify';
import StepConfiguration from './step2-configuration';
import StepClean from './step3-clean';
import StepStorage from './step4-storage';

import './index.scss';

export default defineComponent({
  name: 'CreateOperation',

  setup() {
    const { t } = useLocale();
    const mainRef = ref<HTMLDivElement>();
    const step = ref(3);

    const stepDesc = [
      { title: t('索引集分类'), icon: 1, components: StepClassify },
      { title: t('采集配置'), icon: 2, components: StepConfiguration },
      { title: t('字段清洗'), icon: 3, components: StepClean },
      { title: t('存储'), icon: 4, components: StepStorage },
    ];

    const containerWidth = ref(0);
    let resizeObserver: ResizeObserver | null = null;

    onMounted(() => {
      if (mainRef.value) {
        resizeObserver = new ResizeObserver(entries => {
          const entry = entries[0];
          if (entry) {
            containerWidth.value = entry.contentRect.width;
          }
        });
        resizeObserver.observe(mainRef.value);
      }
    });

    onBeforeUnmount(() => {
      if (resizeObserver) {
        resizeObserver.disconnect();
        resizeObserver = null;
      }
    });

    return () => {
      const Component = stepDesc.find(item => item.icon === step.value).components;
      return (
        <div
          ref={mainRef}
          class='create-operation-main'
        >
          <div
            style={{ width: `${containerWidth.value - 60}px` }}
            class='create-step'
          >
            <div
              style={{ width: `${stepDesc.length * 200}px` }}
              class='step-main'
            >
              <bk-steps
                ext-cls='custom-icon'
                cur-step={step.value}
                line-type={'solid'}
                steps={stepDesc}
              ></bk-steps>
            </div>
            <span class='step-tips'>
              <i class='bklog-icon bklog-help help-icon' />
              {t('接入指引')}
            </span>
          </div>
          <Component
            on-next={() => step.value++}
            on-prev={() => step.value--}
          />
        </div>
      );
    };
  },
});
