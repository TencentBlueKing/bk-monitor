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
import { Component, Emit, InjectReactive, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

interface K8sDimensionDrillDownEvents {
  onHandleDrillDown: (val: { dimension: string; id: number | string }) => void;
}
import { SceneEnum } from 'monitor-pc/pages/monitor-k8s/typings/k8s-new';

import type { K8sGroupDimension } from 'monitor-pc/pages/monitor-k8s/k8s-dimension';

import './k8s-dimension-drilldown.scss';

interface K8sDimensionDrillDownProps {
  dimension: string;
  enableTip?: boolean;
  value: number | string;
}

const drillListMap = {
  [SceneEnum.Performance]: {
    namespace: ['workload', 'pod', 'container'],
    workload: ['pod', 'container'],
    pod: ['container'],
    container: [],
  },
  [SceneEnum.Network]: {
    namespace: ['ingress', 'service', 'pod'],
    ingress: ['service', 'pod'],
    service: ['ingress', 'pod'],
    pod: ['ingress', 'service'],
  },
  [SceneEnum.Capacity]: {
    node: [],
  },
};
@Component
export default class K8sDimensionDrillDown extends tsc<K8sDimensionDrillDownProps, K8sDimensionDrillDownEvents> {
  /** 场景 */
  @InjectReactive({ from: 'scene', default: SceneEnum.Performance }) scene: SceneEnum;
  /** 维度 */
  @Prop({ type: String }) dimension: string;
  /** 下钻id */
  @Prop({ type: [String, Number], required: true }) value: number | string;
  /** 是否下转 tip 提示 */
  @Prop({ type: Boolean, default: true }) enableTip: boolean;

  @InjectReactive('groupInstance') readonly groupInstance!: K8sGroupDimension;

  @Ref('menu')
  menuRef: any;

  drillDownId = null;

  popoverInstance = null;

  /** 可选的下钻列表 */
  get drillDownList() {
    const list = drillListMap[this.scene][this.dimension] || [];
    if (this.scene === SceneEnum.Performance) return list.filter(item => item !== this.groupInstance.getResourceType());
    if (this.scene === SceneEnum.Network) return list;
    return list;
  }

  /** 下钻icon是否展示 */
  get disabledDownDrill() {
    if (!this.drillDownList?.length) {
      return 'none';
    }
    return 'block';
  }

  async handleDrillDown(id: number | string, e: Event) {
    this.drillDownId = id;
    /** 下钻列表只有一个选项，直接下钻，不需要popover */
    if (this.drillDownList.length === 1) {
      this.handleDrillDownChange(this.drillDownList[0]);
    } else {
      this.popoverInstance = this.$bkPopover(e.target, {
        content: this.menuRef,
        trigger: 'click',
        placement: 'bottom-start',
        theme: 'light common-monitor',
        arrow: false,
        interactive: true,
        followCursor: false,
        onHidden: () => {
          this.drillDownId = null;
          this.popoverInstance?.destroy?.();
          this.popoverInstance = null;
        },
      });
      await this.$nextTick();
      this.popoverInstance?.show(100);
    }
  }

  /** 下钻 */
  @Emit('handleDrillDown')
  handleDrillDownChange(val: string) {
    const id = this.drillDownId;
    this.popoverInstance?.hide();
    this.drillDownId = null;
    return {
      id,
      dimension: val,
    };
  }

  render() {
    return (
      <div
        style={{ display: this.disabledDownDrill }}
        class='k8s-dimension-drillDown'
      >
        <div
          class={{
            'drill-down-icon': true,
            active: this.drillDownId === this.value,
          }}
          v-bk-tooltips={{ content: this.$t('下钻'), disabled: !this.enableTip }}
        >
          <div
            class='popover-trigger'
            onClick={e => this.handleDrillDown(this.value, e)}
          >
            {this.$slots?.trigger || <i class='icon-monitor icon-xiazuan' />}
          </div>
        </div>
        <div style='display: none'>
          <ul
            ref='menu'
            class='drill-down-list-menu'
          >
            {this.drillDownList.map(item => (
              <li
                key={item}
                class='menu-item'
                onClick={() => this.handleDrillDownChange(item)}
              >
                {item}
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }
}
