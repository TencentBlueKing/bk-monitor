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

import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import clusterImg1 from '@/images/clean-image1.png';
import clusterImg2 from '@/images/clean-image2.png';
import clusterImg3 from '@/images/clean-image3.png';
import clusterImgGrayed1 from '@/images/cluster-img/clean-image-grayed1.png';
import clusterImgGrayed2 from '@/images/cluster-img/clean-image-grayed2.png';

import './quick-cluster-step.scss';

const { $i18n } = window.mainComponent;

interface IProps {
  clusterStepData: object;
}

@Component
export default class QuickClusterStep extends tsc<IProps> {
  @Prop({ type: Object, required: true }) clusterStepData: object;

  stepIndexKeyMappingList = {
    1: 'flow_create',
    2: 'flow_run',
    3: 'data_check',
  };
  imgSrcMapping = {
    1: clusterImg1,
    2: clusterImg2,
    3: clusterImg3,
  };
  imgSuccessSrcMapping = {
    1: clusterImgGrayed1,
    2: clusterImgGrayed2,
    3: clusterImg3,
  };

  get errorMessage() {
    const clusterDataList = Object.entries(this.clusterStepData).reduce((acc, [key, val]) => {
      if (Object.values(this.stepIndexKeyMappingList).includes(key)) {
        acc.push(val);
      }
      return acc;
    }, []);
    const failedObj = clusterDataList.find(item => item.status === 'FAILED');
    return failedObj?.message || '';
  }

  getStatus(step) {
    return this.clusterStepData?.[this.stepIndexKeyMappingList[step]]?.status || 'SUCCESS';
  }
  getNumHTMLShow(step) {
    const status = this.getStatus(step);
    if (status === 'SUCCESS') {
      return <i class='bk-icon icon-check-circle-shape' />;
    }
    if (status === 'FAILED') {
      return <i class='bk-icon icon-close-circle-shape' />;
    }
    return <span class='step-num'>{step}</span>;
  }
  getImageSrc(step) {
    const status = this.getStatus(step);
    if (status === 'SUCCESS') {
      return this.imgSuccessSrcMapping[step];
    }
    return this.imgSrcMapping[step];
  }
  getStepStyleClass(step, originClass = '') {
    const status = this.getStatus(step);
    if (status === 'SUCCESS') {
      return `finish ${originClass}`;
    }
    return originClass;
  }

  render() {
    return (
      <div class='cluster-step-container'>
        <div>
          <div class='top-time'>
            {this.errorMessage ? (
              <div class='time-str'>
                <i class='bk-icon icon-close icon-error' />
                <span class='time-tips'>{$i18n.t('聚类启动失败')}</span>
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
                />
                <i18n
                  class='time-tips'
                  path='任务启动中，预计等待时长 {0} 分钟'
                >
                  <span class='time'>10 - 30</span>
                </i18n>
              </div>
            )}
            {/* {this.errorMessage && (
              <bk-button
                class='re-access'
                theme='primary'
              >
                <i class='bk-icon icon-right-turn-line'></i>
                <span>{$i18n.t('重新接入')}</span>
              </bk-button>
            )} */}
            {this.errorMessage && (
              <span class='error-message'>
                <span class='error-reason'>{$i18n.t('失败原因')}: </span>
                <span class='error'>{this.errorMessage}</span>
              </span>
            )}
          </div>
          <div class='step-container'>
            <div class='step-item'>
              <div class='image-content'>
                {/** biome-ignore lint/performance/noImgElement: reason */}
                {/** biome-ignore lint/nursery/useImageSize: reason */}
                <img
                  alt='图片显示状态'
                  src={this.getImageSrc(1)}
                />
              </div>
              <div class='step-description'>
                <div class='title-box'>
                  <div class='num-div'>{this.getNumHTMLShow(1)}</div>
                  <span class={this.getStepStyleClass(1, 'title')}>{$i18n.t('模型创建')}</span>
                </div>
                <span class={this.getStepStyleClass(1, 'description-text')}>
                  {$i18n.t('系统将创建模型，并将该日志历史数据投入模型中。')}
                </span>
              </div>
            </div>
            <span class={this.getStepStyleClass(1, 'bk-icon icon-angle-double-right-line')} />
            <div class='step-item'>
              <div class='image-content'>
                {/** biome-ignore lint/nursery/useImageSize: reason */}
                {/** biome-ignore lint/performance/noImgElement: reason */}
                <img
                  alt='图片显示状态'
                  src={this.getImageSrc(2)}
                />
              </div>
              <div class='step-description'>
                <div class='title-box'>
                  <div class='num-div'>{this.getNumHTMLShow(2)}</div>
                  <span class={this.getStepStyleClass(2, 'title')}>{$i18n.t('模型启动')}</span>
                </div>
                <span class={this.getStepStyleClass(2, 'description-text')}>
                  {$i18n.t('模型首次启动准备，该过程应该会持续5-10分钟。')}
                </span>
              </div>
            </div>
            <span class={this.getStepStyleClass(2, 'bk-icon icon-angle-double-right-line')} />
            <div class='step-item'>
              <div class='image-content'>
                {/** biome-ignore lint/nursery/useImageSize: reason */}
                {/** biome-ignore lint/performance/noImgElement: reason */}
                <img
                  alt='图片显示状态'
                  src={this.getImageSrc(3)}
                />
              </div>
              <div class='step-description'>
                <div class='title-box'>
                  <div class='num-div'>{this.getNumHTMLShow(3)}</div>
                  <span class='title'>{$i18n.t('预测准备')}</span>
                </div>
                <span class={this.getStepStyleClass(3, 'description-text')}>
                  {$i18n.t('针对已投入数据进行在线与离线分析，分析结束后，页面将展示聚类结果。')}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
