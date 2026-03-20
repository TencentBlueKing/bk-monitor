/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { type PropType, computed, defineComponent } from 'vue';

import { Exception, Sideslider } from 'bkui-vue';

import { ImpactScopeResourceLabelMap } from '../../constant';

import type { ImpactScopeInstance, ImpactScopeResource, ImpactScopeResourceKeyType } from '../../typing';

import './issues-impact-scope-drawer.scss';

export default defineComponent({
  name: 'IssuesImpactScopeDrawer',
  props: {
    /** 是否显示侧滑面板 */
    show: {
      type: Boolean,
      required: true,
    },
    /** 当前展示的资源类型 key（如 host、cluster 等） */
    resourceKey: {
      type: String as PropType<'' | ImpactScopeResourceKeyType>,
      default: '',
    },
    /** 当前展示的资源类型数据 */
    resource: {
      type: Object as PropType<ImpactScopeResource | null>,
      default: null,
    },
  },
  emits: ['update:show'],
  setup(props, { emit }) {
    /**
     * @description 处理侧滑面板显示/隐藏切换
     * @param {boolean} isShow - 是否显示
     */
    const handleShowChange = (isShow: boolean) => {
      emit('update:show', isShow);
    };

    /**
     * @description 处理实例名称点击跳转
     * @param {ImpactScopeInstance} instance - 实例数据
     */
    const handleInstanceClick = (instance: ImpactScopeInstance) => {
      if (!props.resource?.link_tpl) return;
      // TODO: 跳转逻辑待补全
      console.log('issueImpactScopeDrawer handleInstanceClick 跳转逻辑待补全');
    };

    return {
      handleShowChange,
      handleInstanceClick,
    };
  },
  render() {
    const instanceList = this.resource?.instance_list ?? [];
    const isClickable = !!this.resource?.link_tpl;

    return (
      <Sideslider
        width={560}
        extCls='issues-impact-scope-drawer'
        v-slots={{
          header: () => (
            <div class='impact-scope-drawer-header'>
              <span class='header-title'>{ImpactScopeResourceLabelMap[this.resourceKey] || this.resourceKey}</span>
            </div>
          ),
          default: () => (
            <div class='impact-scope-drawer-content'>
              {instanceList.length ? (
                <ul class='instance-list'>
                  {instanceList.map((instance, idx) => (
                    <li
                      key={idx}
                      class='instance-item'
                    >
                      <div
                        class={['instance-item-main', { 'is-clickable': isClickable }]}
                        v-overflow-tips={{
                          placement: 'top',
                          theme: 'text-wrap',
                        }}
                      >
                        <span
                          class='instance-name'
                          onClick={() => this.handleInstanceClick(instance)}
                        >
                          {instance.display_name}
                        </span>
                      </div>
                      <div class='instance-item-operation'>
                        <i class='icon-monitor icon-a-sousuo' />
                        <i class='icon-monitor icon-sousuo-' />
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <Exception
                  class='empty-state'
                  description={window.i18n.t('暂无数据')}
                  scene='part'
                  type='empty'
                />
              )}
            </div>
          ),
        }}
        isShow={this.show}
        render-directive='if'
        onUpdate:isShow={this.handleShowChange}
      />
    );
  },
});
