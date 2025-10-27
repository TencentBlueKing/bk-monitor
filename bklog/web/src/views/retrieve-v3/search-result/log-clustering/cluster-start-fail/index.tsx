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
import { computed, defineComponent, PropType } from 'vue';
import useLocale from '@/hooks/use-locale';
import clusterImg1 from '@/images/clean-image1.png';
import clusterImg2 from '@/images/clean-image2.png';
import clusterImg3 from '@/images/clean-image3.png';
import clusterImgGrayed1 from '@/images/cluster-img/clean-image-grayed1.png';
import clusterImgGrayed2 from '@/images/cluster-img/clean-image-grayed2.png';
import { type ClusteringConfigStatus } from '@/services/retrieve';
import './index.scss';

type StepStatus = keyof Omit<ClusteringConfigStatus, 'access_finished'>;

export default defineComponent({
  name: 'ClusterStartFail',
  props: {
    clusterStepData: {
      type: Object as PropType<ClusteringConfigStatus>,
      required: true,
    },
  },
  setup(props, { expose }) {
    const { t } = useLocale();

    const stepInfoList = [
      {
        key: 'flow_create',
        title: t('模型创建'),
        description: t('系统将创建模型，并将该日志历史数据投入模型中。'),
        successImg: clusterImgGrayed1,
        unSuccessImg: clusterImg1,
      },
      {
        key: 'flow_run',
        title: t('模型启动'),
        description: t('模型首次启动准备，该过程应该会持续5-10分钟。'),
        successImg: clusterImgGrayed2,
        unSuccessImg: clusterImg2,
      },
      {
        key: 'data_check',
        title: t('预测准备'),
        description: t('针对已投入数据进行在线与离线分析，分析结束后，页面将展示聚类结果。'),
        successImg: clusterImg3,
        unSuccessImg: clusterImg3,
      },
    ] as {
      key: StepStatus;
      title: string;
      description: string;
      successImg: string;
      unSuccessImg: string;
    }[];

    const errorMessage = computed(() => {
      for (const step of stepInfoList) {
        const stepData = props.clusterStepData?.[step.key];
        if (stepData?.status === 'FAILED') {
          return stepData.message || '';
        }
      }
      return '';
    });

    const getStatus = (step: StepStatus) => {
      return props.clusterStepData?.[step]?.status || 'SUCCESS';
    };

    const getNumDisplay = (step: StepStatus) => {
      const status = getStatus(step);
      const num = stepInfoList.findIndex(item => item.key === step) + 1;
      if (status === 'SUCCESS') {
        return (
          <log-icon
            common
            type='check-circle-shape'
          />
        );
      }
      if (status === 'FAILED') {
        return (
          <log-icon
            common
            type='close-circle-shape'
          />
        );
      }
      return <div class='step-num'>{num}</div>;
    };

    const getStepStyleClass = (step: StepStatus) => {
      const status = getStatus(step);
      if (status === 'SUCCESS') {
        return 'finish';
      }
    };

    expose({
      errorMessage,
    });

    return () => (
      <div class='cluster-step-container-main'>
        <div>
          <div class='top-time'>
            {errorMessage.value ? (
              <div class='time-str'>
                <log-icon
                  common
                  class='icon-error'
                  type='close-circle-shape'
                />
                <i18n
                  class='error-main-title'
                  path='任务超时失败，请联系 {0}'
                >
                  <span>{t('BK 助手')}</span>
                </i18n>
                {/* <div class='dash-line'></div> */}
              </div>
            ) : (
              <div class='time-str'>
                <i
                  class='rotate-icon'
                  v-bkloading={{
                    isLoading: true,
                    opacity: 1,
                    zIndex: 10,
                    theme: 'primary',
                    mode: 'spin',
                    size: 'small',
                  }}
                ></i>
                <i18n
                  class='time-tips'
                  path='任务启动中，预计等待时长 {0} 分钟'
                >
                  <span class='time'>10 - 30</span>
                </i18n>
              </div>
            )}
            {errorMessage.value && (
              <div class='error-message'>
                <span class='error-reason'>{t('失败原因')}: </span>
                <span class='error'>{errorMessage.value}</span>
              </div>
            )}
          </div>
          <div class='step-container'>
            {stepInfoList.map((item, index) => (
              <div
                class='step-item-container'
                key={item.key}
              >
                <div class='step-item'>
                  <div class='image-content'>
                    <img src={getStatus(item.key) === 'SUCCESS' ? item.successImg : item.unSuccessImg} />
                  </div>
                  <div class='step-description'>
                    <div class='title-box'>
                      <div class='num-div'>{getNumDisplay(item.key)}</div>
                      <div class={[getStepStyleClass(item.key), 'title']}>{item.title}</div>
                    </div>
                    <div class={[getStepStyleClass(item.key), 'description-text']}>{item.description}</div>
                  </div>
                </div>
                {index < stepInfoList.length - 1 && (
                  <div class={[getStepStyleClass(item.key), 'bk-icon icon-angle-double-right-line']}></div>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  },
});
