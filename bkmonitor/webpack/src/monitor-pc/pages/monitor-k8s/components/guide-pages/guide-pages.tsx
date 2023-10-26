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
import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SvgIcon from '../../../../components/svg-icon/svg-icon.vue';

import './guide-pages.scss';

@Component
export default class GuidePages extends tsc<{}> {
  /** 引导描述文案 */
  guideDescData = [
    {
      label: window.i18n.t('场景介绍'),
      content: window.i18n.t(
        'Kubernetes Cluster概览，是以Kubernetes整体视角查看该业务下所有的集群的情况，目的是能快速了解整体情况并且快速进行问题的定位。'
      )
    },
    {
      label: window.i18n.t('开启Kubernetes监控'),
      content: window.i18n.t(
        '当前没有发现任何一个Kubernetes Cluster ，添加Cluster成功后，会自动的采集集群内的指标和事件数据，包含集群中所有的对象 Namespace Service Pod Deamset Deploymente Node 等，提供立体的监控数据。'
      )
    }
  ];

  /** 引导步骤数据 */
  guideStepData = [
    {
      label: window.i18n.t('托管集群'),
      icon: 'k8s-guide-step-1'
    },
    {
      label: window.i18n.t('数据采集'),
      icon: 'k8s-guide-step-2'
    },
    {
      label: window.i18n.t('数据应用'),
      icon: 'k8s-guide-step-3'
    }
  ];

  /** DEMO业务 */
  get demo() {
    return this.$store.getters.bizList.find(item => item.is_demo);
  }

  /** BCS地址 */
  get bcsUrl() {
    return this.$store.getters.bkBcsUrl;
  }

  /**
   * @description: 跳转demo业务
   */
  handleToDemo() {
    if (this.demo?.id) {
      if (+this.$store.getters.bizId === +this.demo.id) {
        location.reload();
      } else {
        /** 切换为demo业务 */
        this.$store.commit('app/handleChangeBizId', {
          bizId: this.demo.id,
          ctx: this
        });
      }
    }
  }

  /** 跳转bcs创建集群 */
  handleCreateCluster() {
    const url = `${this.bcsUrl?.replace?.(/\/$/, '')}/`;
    window.open(url);
  }
  render() {
    const contentMap = {
      1: this.$t('所有的Kubetnetes集群都是通过BCS服务进行托管，托管方式有两种： 第一种： 界面托管 第二种： 命令行托管'),
      2: (
        <i18n path='监控平台会自动的下发Deployment无侵入式的采集集群中的指标数据和事件数据，当然也可以自定义插件采集更多的数据。 监控平台提供了各种数据管理的能力保证数据的安全和稳定性。更多的数据采集方式请查看文档。{0}'>
          <span class='k8s-step-link'>
            {this.$t('文档')}
            <i class='icon-monitor icon-mc-link'></i>
          </span>
        </i18n>
      ),
      3: this.$t(
        '采集上来的数据可以满足跨集群使用满足告警策略和视图查看。还可以与同边系统进行联动实现自愈的目的，同样也可以通过智能异常检测等更有效的发现问题，甚至在计算平台中进行二次的计算和处理。'
      )
    };
    return (
      <div class='k8s-guide-pages-wrap'>
        <div class='k8s-guide-title'>
          <span class='k8s-guide-title-text'>Kubernetes</span>
        </div>
        <div class='k8s-guide-scroll'>
          <div class='k8s-guide-content'>
            {!this.bcsUrl && (
              <bk-alert
                type='warning'
                title={this.$t(
                  '没有部署BCS服务，所有被监控的Kubernetes集群需要先注册到BCS。请检查BCS服务是否已经部署，如果未部署请查看文档'
                )}
              ></bk-alert>
            )}
            <div class='k8s-guide-mian'>
              {this.guideDescData.map(item => (
                <div class='k8s-guide-row'>
                  <div class='k8s-guide-row-label'>{item.label}</div>
                  <div class='k8s-guide-row-content'>{item.content}</div>
                </div>
              ))}
              <div class='k8s-guide-step-container'>
                {this.guideStepData.map((item, index) => [
                  <div class='k8s-guide-step-item'>
                    <div class='k8s-guide-step-item-img'>
                      <SvgIcon
                        icon-name={item.icon}
                        class={item.icon}
                      ></SvgIcon>
                    </div>
                    <div class='k8s-guide-step-item-label'>
                      <span class='step-index'>{index + 1}</span>
                      <span class='step-label-text'>{item.label}</span>
                    </div>
                    <div class='k8s-guide-step-item-content'>{contentMap[index + 1]}</div>
                  </div>,
                  index + 1 < this.guideStepData.length && (
                    <div class='k8s-guide-step-arrow'>
                      <i class='k8s-guide-step-arrow icon-monitor icon-double-up'></i>
                    </div>
                  )
                ])}
              </div>
              <div class='k8s-guide-pages-btn-group'>
                {!!this.demo && (
                  <bk-button
                    theme='primary'
                    onClick={this.handleToDemo}
                  >
                    {this.$t('DEMO')}
                  </bk-button>
                )}
                {!!this.bcsUrl && (
                  <bk-button
                    theme='primary'
                    onClick={this.handleCreateCluster}
                  >
                    {this.$t('创建集群')}
                  </bk-button>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
