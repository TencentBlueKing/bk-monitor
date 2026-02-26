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

import { defineComponent, onBeforeUnmount, onMounted, ref, computed, watch } from 'vue';

import useLocale from '@/hooks/use-locale';
import { useRoute, useRouter } from 'vue-router/composables';
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
    const router = useRouter();
    const mainRef = ref<HTMLDivElement>();
    const DEFAULT_STEP = 1;
    const step = ref(DEFAULT_STEP);
    const typeKey = ref('linux');
    const firstStep = [{ title: t('索引集分类'), icon: 1, components: StepClassify }];
    const { goListPage } = useCollectList();
    const dataConfig = ref({});
    const showCollectIssuedSlider = ref(false);
    const currentCollectorId = ref<number | null>(null);
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
      { title: t('采集配置'), icon: 2, components: StepConfiguration },
      { title: t('字段清洗'), icon: 3, components: StepClean },
      { title: t('存储'), icon: 4, components: StepStorage },
    ];
    /**
     * 第三方日志新建流程 （计算平台、第三方ES接入)流程
     */
    const thirdLogStep = [{ title: t('采集配置'), icon: 2, components: StepBkDataCollection }];
    /**
     * 自定义日志新建流程
     */
    const customReportStep = [
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
    const collectId = computed(() => route.params.collectorId);
    /**
     *
     */
    const isClone = computed(() => route.query.type === 'clone' && !!route.query.collectorId);
    /**
     * 是否是编辑状态
     */
    const isEdit = computed(() => !!collectId.value);
    /**
     * 是否需要采集下发
     */
    const isNeedIssue = computed(() =>
      ['linux', 'winevent', 'container_file', 'container_stdout'].includes(typeKey.value),
    );
    /**
     * 当前步骤流程
     * 根据不同的日志类型（第三方日志、自定义日志、标准日志）和编辑/新建模式返回对应的步骤配置
     * - 编辑模式：跳过第一步（索引集分类），步骤图标从 1 开始重新编号
     * - 新建模式：包含第一步（索引集分类），保持原有图标编号
     */
    const currentStep = computed(() => {
      // 根据日志类型选择对应的步骤配置
      const targetSteps = ['bkdata', 'es'].includes(typeKey.value)
        ? thirdLogStep // 第三方日志流程（计算平台、第三方ES接入）
        : typeKey.value === 'custom_report'
          ? customReportStep // 自定义日志流程
          : stepDesc; // 标准日志流程（主机日志等）

      // 编辑/克隆模式：跳过第一步，重新编号图标从 1 开始
      if (isEdit.value || isClone.value) {
        return targetSteps.map((item, index) => ({
          ...item,
          icon: index + 1,
        }));
      }

      // 新建模式：包含第一步（索引集分类）+ 后续步骤
      return [...firstStep, ...targetSteps];
    });

    const isShowStatusBtn = computed(() => isNeedIssue.value && step.value !== 1 && !!currentCollectorId.value);

    const containerWidth = ref(0);
    let resizeObserver: ResizeObserver | null = null;
    const pollingTimer = ref<number | null>(null);

    // 在 setup 阶段就初始化 typeKey，避免 watch 导致组件重新挂载
    if (isEdit.value || isClone.value) {
      typeKey.value = (route.query.typeKey as string) || typeKey.value;
    }

    onMounted(() => {
      if (route.query.step) {
        step.value = Number(route.query.step);
      }
      step.value !== 1 && isEdit && collectId.value && getCollectStatus(Number(collectId.value));
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
    /**
     * 清除轮询定时器
     */
    const clearPolling = () => {
      if (pollingTimer.value) {
        clearInterval(pollingTimer.value);
        pollingTimer.value = null;
      }
    };

    onBeforeUnmount(() => {
      if (resizeObserver) {
        resizeObserver.disconnect();
        resizeObserver = null;
      }
      clearPolling();
    });
    /**
     * 选择具体的索引集分类
     */
    const chooseType = (data: { value: string }) => {
      typeKey.value = data.value;
      router.replace({
        query: {
          ...route.query,
          typeKey: typeKey.value,
        },
      });
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
     * 获取采集状态
     */
    const getCollectStatus = (id: number) => {
      $http
        .request('collect/getCollectStatus', {
          query: {
            collector_id_list: id,
          },
        })
        .then(res => {
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
              getCollectStatus(id);
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
    /**
     * 初始化采集分类的类型
     * @param val
     */
    const initTypeKey = (val: boolean) => {
      if (val && route.query.typeKey) {
        // 只在 typeKey 实际变化时才更新，避免不必要的重新渲染
        const newTypeKey = route.query.typeKey as string;
        if (typeKey.value !== newTypeKey) {
          typeKey.value = newTypeKey;
        }
      }
    };
    /**
     * 跳转到接入指引
     */
    const handleOpenGuide = () => {
      const docPath = 'markdown/ZH/LogSearch/4.7/UserGuide/ProductFeatures/integrations-logs/simple_log_collection.md';
      const url = (window as any).BK_DOC_URL.replace(/\/$/, '');
      url && window.open(`${url}/${docPath}`, '_blank');
    };

    watch([() => isEdit.value, () => isClone.value], ([editVal, cloneVal]) => {
      initTypeKey(editVal || cloneVal);
    });

    return () => {
      const Component = currentStep.value.find(item => item.icon === step.value)?.components;
      return (
        <div
          ref={mainRef}
          class='create-operation-main'
        >
          <CollectIssuedSlider
            isShow={showCollectIssuedSlider.value}
            status={currentStatus.value.status}
            config={dataConfig.value}
            collectorConfigId={currentCollectorId.value}
            on-change={value => {
              showCollectIssuedSlider.value = value;
            }}
          />
          {isShowStatusBtn.value && (
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
            <span
              class='step-tips'
              on-click={handleOpenGuide}
            >
              <i class='bklog-icon bklog-help help-icon' />
              {t('接入指引')}
            </span>
          </div>
          <Component
            configData={dataConfig.value}
            scenarioId={typeKey.value}
            on-cancel={handleCancel}
            on-handle={handleFunction}
            isEdit={isEdit.value}
            isClone={isClone.value}
            on-next={data => {
              dataConfig.value = data;
              if (isNeedIssue.value && ((step.value === 2 && !isEdit.value) || (isEdit.value && step.value === 1))) {
                currentCollectorId.value = data.collector_config_id;
                getCollectStatus(data.collector_config_id);
              }
              step.value = step.value + 1;
            }}
            on-prev={() => {
              step.value = step.value - 1;
            }}
          />
        </div>
      );
    };
  },
});
