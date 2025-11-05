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
import { useRoute } from 'vue-router/composables';
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
    const route = useRoute();
    const mainRef = ref<HTMLDivElement>();
    const DEFAULT_STEP = 1;
    const step = ref(DEFAULT_STEP);
    const typeKey = ref('host_log');
    const firstStep = { title: t('索引集分类'), icon: 1, components: StepClassify };
    const { goListPage } = useCollectList();
    const dataConfig = ref({});
    const showCollectIssuedSlider = ref(false);
    const statusMap = {
      success: {
        value: ['SUCCESS'],
        text: t('采集下发成功'),
      },
      running: {
        value: ['PREPARE', 'RUNNING', 'UNKNOWN'],
        text: t('采集下发中...'),
      },
    };

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

    const currentStatus = ref({
      status: 'running',
      text: t('采集下发中...'),
    });
    /**
     * 当前采集id
     */
    const collectId = computed(() => route.params.collectId);
    /**
     * 是否是编辑状态
     */
    const isEdit = computed(() => !!collectId.value);
    /**
     * 是否需要采集下发
     */
    const isNeedIssue = computed(() =>
      ['host_log', 'wineventlog', 'file_log_config', 'std_log_config'].includes(typeKey.value),
    );
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
    const pollingTimer = ref<number | null>(null);

    onMounted(() => {
      step.value !== 1 && isEdit && getCollectStatus();
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
      if (pollingTimer.value) {
        clearInterval(pollingTimer.value);
        pollingTimer.value = null;
      }
    });
    /**
     * 选择具体的索引集分类
     */
    const chooseType = data => {
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

    /**
     * 清除轮询定时器
     */
    const clearPolling = () => {
      if (pollingTimer.value) {
        clearInterval(pollingTimer.value);
        pollingTimer.value = null;
      }
    };
    /**
     * 获取采集状态
     */
    const getCollectStatus = () => {
      $http
        .request('collect/getCollectStatus', {
          query: {
            collector_id_list: 3247,
          },
        })
        .then(res => {
          console.log(res, 'statusRes');

          if (!res.result) {
            return;
          }
          const status = res.data[0]?.status;
          const statusKey = Object.keys(statusMap).find(key => statusMap[key].value.includes(status));
          currentStatus.value = {
            status: statusKey ? statusKey : 'failed',
            text: statusKey ? statusMap[statusKey].text : t('采集下发失败'),
          };

          // 如果状态为 running，开始轮询
          if (statusKey === 'running') {
            // 如果已经有定时器在运行，先清除
            clearPolling();
            // 每 3 秒轮询一次
            pollingTimer.value = window.setInterval(() => {
              getCollectStatus();
            }, 3000);
          } else {
            // 状态不为 running 时，停止轮询
            clearPolling();
          }
        })
        .catch(() => {
          // 请求失败时也停止轮询
          clearPolling();
        });
    };

    return () => {
      console.log(isEdit.value, 'is;Edit');
      const Component = currentStep.value.find(item => item.icon === step.value)?.components;
      return (
        <div
          ref={mainRef}
          class='create-operation-main'
        >
          <CollectIssuedSlider
            isShow={showCollectIssuedSlider.value}
            on-change={value => {
              showCollectIssuedSlider.value = value;
            }}
          />
          {isNeedIssue.value && step.value !== 1 && (
            <div
              class={`status-box ${currentStatus.value.status}`}
              on-Click={() => {
                showCollectIssuedSlider.value = true;
              }}
            >
              <span class='status-icon-box' />
              {currentStatus.value.status === 'running' && <i class='bklog-icon bklog-caijixiafazhong status-icon' />}
              {currentStatus.value.status === 'success' && (
                <i class='bklog-icon bklog-circle-correct-filled status-icon' />
              )}
              {currentStatus.value.status === 'failed' && <i class='bklog-icon bklog-shanchu status-icon' />}
              <span class='status-txt'>{currentStatus.value.text}</span>
            </div>
          )}
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
              console.log(step.value, 'step.value');

              if (isNeedIssue.value && step.value === 2) {
                getCollectStatus();
              }
              step.value++;
            }}
            on-prev={() => step.value--}
          />
        </div>
      );
    };
  },
});
