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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { K8sConvergeTypeEnum } from '../../typings/k8s-new';

import './k8s-converge-select.scss';

interface K8sConvergeSelectEvents {
  onMethodChange: (method: K8sConvergeTypeEnum) => void;
}
interface K8sConvergeSelectProps {
  enableTip?: boolean;
  method: number | string;
}

@Component
export default class K8sConvergeSelect extends tsc<K8sConvergeSelectProps, K8sConvergeSelectEvents> {
  /** 汇聚方法 */
  @Prop({ type: String, default: K8sConvergeTypeEnum.SUM }) method: string;
  /** 是否展示  汇聚方法tip 提示 */
  @Prop({ type: Boolean, default: true }) enableTip: boolean;

  @Ref('menu')
  menuRef: any;

  popoverInstance = null;

  get IconNameByConverge() {
    switch (this.method) {
      case K8sConvergeTypeEnum.COUNT:
        return 'icon-cnt';
      case K8sConvergeTypeEnum.AVG:
        return 'icon-avg';
      case K8sConvergeTypeEnum.MAX:
        return 'icon-max';
      case K8sConvergeTypeEnum.MIN:
        return 'icon-min';
      default:
        return 'icon-sum';
    }
  }

  get convergeList() {
    return Object.entries(K8sConvergeTypeEnum).map(([key, value]) => ({ id: value, name: key }));
  }

  /** 汇聚方法值改变后回调 */
  @Emit('methodChange')
  handleConvergeChange(method: K8sConvergeTypeEnum) {
    if (this.method === method) return;
    this.popoverInstance?.hide();
    return method;
  }

  async handleConvergeListShow(e: Event) {
    this.popoverInstance = this.$bkPopover(e.target, {
      content: this.menuRef,
      trigger: 'click',
      placement: 'bottom-start',
      theme: 'light common-monitor',
      arrow: false,
      interactive: true,
      followCursor: false,
      onHidden: () => {
        this.popoverInstance?.destroy?.();
        this.popoverInstance = null;
      },
    });
    await this.$nextTick();
    this.popoverInstance?.show(100);
  }

  render() {
    return (
      <div class='k8s-converge-select'>
        <div
          class={{ 'popover-trigger': true, active: !!this.popoverInstance }}
          v-bk-tooltips={{ content: this.$t('汇聚方法'), disabled: !this.enableTip }}
          onClick={e => this.handleConvergeListShow(e)}
        >
          {this.$slots?.trigger || <i class={['icon-monitor', this.IconNameByConverge]} />}
        </div>
        <div style='display: none'>
          <ul
            ref='menu'
            class='k8s-converge-list-menu'
          >
            {this.convergeList.map(item => (
              <li
                key={item.id}
                class={['menu-item', this.method === item.id ? 'is-active' : '']}
                onClick={() => this.handleConvergeChange(item.id)}
              >
                {item.name}
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }
}
