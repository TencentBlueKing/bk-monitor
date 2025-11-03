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

import { defineComponent, onBeforeUnmount, onMounted, ref, computed } from 'vue';

import useLocale from '@/hooks/use-locale';

import { useCollectList } from '../../hook/useCollectList';
import CollectIssuedSlider from '../business-comp/step3/collect-issued-slider';
import StepClassify from './step1-classify';
import StepBkDataCollection from './step2-bk-data-collection';
import StepConfiguration from './step2-configuration';
import StepCustomReport from './step2-custom-report';
import StepClean from './step3-clean';
import StepStorage from './step4-storage';
import $http from '@/api';

import './index.scss';

export default defineComponent({
  name: 'CreateOperation',

  setup() {
    const { t } = useLocale();
    const mainRef = ref<HTMLDivElement>();
    const DEFAULT_STEP = 3;
    const step = ref(DEFAULT_STEP);
    const typeKey = ref('std_log_config');
    const firstStep = { title: t('索引集分类'), icon: 1, components: StepClassify };
    const { goListPage } = useCollectList();
    const dataConfig = ref({});
    const showCollectIssuedSlider = ref(false);

    const stepDesc = [
      firstStep,
      { title: t('采集配置'), icon: 2, components: StepConfiguration },
      { title: t('字段清洗'), icon: 3, components: StepClean },
      { title: t('存储'), icon: 4, components: StepStorage },
    ];
    /**
     * 第三方日志新建流程 （计算平台、第三方ES接入)流程
     */
    const thirdLogStep = [firstStep, { title: t('采集配置'), icon: 2, components: StepBkDataCollection }];
    /**
     * 自定义日志新建流程
     */
    const customReportStep = [
      firstStep,
      { title: t('采集配置'), icon: 2, components: StepCustomReport },
      { title: t('存储'), icon: 3, components: StepStorage },
    ];
    /**
     * 当前步骤流程
     */
    const currentStep = computed(() => {
      if (['bkdata', 'es'].includes(typeKey.value)) {
        return thirdLogStep;
      }
      if (typeKey.value === 'custom_report') {
        return customReportStep;
      }
      return stepDesc;
    });

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
    /**
     * 选择具体的索引集分类
     */
    const chooseType = data => {
      console.log('chooseType', data);
      typeKey.value = data.value;
    };
    /**
     * 相关操作项
     */
    const handleFunction = (type: string, data?: any) => {
      const functionMap = {
        choose: chooseType,
      };
      functionMap[type]?.(data);
    };

    const handleCancel = () => {
      goListPage();
    };

    const getCollectList = (isLoading = true) => {
      $http
        .request('source/collectList', {
          params: {
            // collector_config_id: this.$route.params.collectorId,
          },
          manualSchema: true,
        })
        .then(res => {
          console.log('getCollectList', res);
        })
        .catch(e => {
          console.warn(e);
          // this.reloadTable = false;
        })
        .finally(() => {
          // this.basicLoading = false;
        });
    };

    return () => {
      const Component = currentStep.value.find(item => item.icon === step.value)?.components;
      return (
        <div
          ref={mainRef}
          class='create-operation-main'
        >
          <CollectIssuedSlider
            // data={log}
            isShow={showCollectIssuedSlider.value}
            on-change={value => {
              showCollectIssuedSlider.value = value;
            }}
          />
          <div
            class='status-box loading'
            on-Click={() => {
              showCollectIssuedSlider.value = true;
            }}
          >
            <span class='status-icon-box' />
            <i class='bklog-icon bklog-caijixiafazhong status-icon' />
            {/* <i class='bklog-icon bklog-circle-correct-filled status-icon' /> */}
            {/* <i class='bklog-icon bklog-shanchu status-icon' /> */}
            <span class='status-txt'>{t('采集下发中...')}</span>
          </div>
          <div
            style={{ width: `${containerWidth.value - 60}px` }}
            class='create-step'
          >
            <div
              style={{ width: `${currentStep.value.length * 200}px` }}
              class='step-main'
            >
              <bk-steps
                ext-cls='custom-icon'
                cur-step={step.value}
                line-type={'solid'}
                steps={currentStep.value}
              />
            </div>
            <span class='step-tips'>
              <i class='bklog-icon bklog-help help-icon' />
              {t('接入指引')}
            </span>
          </div>
          <Component
            configData={dataConfig.value}
            scenarioId={typeKey.value}
            on-cancel={handleCancel}
            on-handle={handleFunction}
            on-next={data => {
              dataConfig.value = data;
              step.value++;
            }}
            on-prev={() => step.value--}
          />
        </div>
      );
    };
  },
});
