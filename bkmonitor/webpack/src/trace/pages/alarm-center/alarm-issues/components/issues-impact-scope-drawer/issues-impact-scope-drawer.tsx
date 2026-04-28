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

import { type PropType, defineComponent } from 'vue';

import { Exception, Sideslider } from 'bkui-vue';

import { IMPACT_SCOPE_ID_FIELD_MAP } from '../../constant';

import type { CommonCondition } from '../../../typings/services';
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
  emits: ['update:show', 'filterByInstance'],
  setup(props, { emit }) {
    /**
     * @description 处理侧滑面板显示/隐藏切换
     * @param {boolean} isShow - 是否显示
     */
    const handleShowChange = (isShow: boolean) => {
      emit('update:show', isShow);
    };

    /**
     * @description 处理实例名称点击跳转，将 link_tpl 模板占位符替换为实例实际值后在新标签页打开
     * @param {ImpactScopeInstance} instance - 实例数据
     */
    const handleInstanceClick = (instance: ImpactScopeInstance) => {
      if (!props.resource?.link_tpl) return;
      const url = props.resource.link_tpl.replace(/\{(\w+)\}/g, (_, key: string) => String(instance[key] ?? ''));
      if (url) {
        window.open(url, '_blank');
      }
    };

    /**
     * @description 处理实例级检索过滤（正排/反排），构建 CommonCondition 后 emit 给宿主页面
     * @param {ImpactScopeInstance} instance - 实例数据
     * @param {'eq' | 'neq'} method - 过滤方式：eq=正排精确匹配，neq=反排排除
     */
    const handleFilterByInstance = (instance: ImpactScopeInstance, method: 'eq' | 'neq') => {
      const idField = IMPACT_SCOPE_ID_FIELD_MAP[props.resourceKey];
      if (!idField) return;
      const idValue = instance[idField];
      if (idValue === undefined) return;
      const condition: CommonCondition = {
        key: `impact_scope.${props.resourceKey}`,
        // key: `impact_scope.${props.resourceKey}.${idField}`,
        method,
        value: [String(idValue)],
      };
      emit('filterByInstance', condition);
    };

    /**
     * @description 渲染实例行的正排/反排操作图标，tooltip 展示实际的过滤条件表达式
     * @param {ImpactScopeInstance} instance - 实例数据
     * @returns {JSX.Element} 操作图标 JSX
     */
    const renderOperationIcons = (instance: ImpactScopeInstance) => {
      const idField = IMPACT_SCOPE_ID_FIELD_MAP[props.resourceKey];
      // 这里只需要两段式
      const conditionKey = idField ? `impact_scope.${props.resourceKey}` : '';
      // const conditionKey = idField ? `impact_scope.${props.resourceKey}.${idField}` : '';
      const idValue = instance?.[idField] ?? '""';

      return (
        <div class='instance-item-operation'>
          <i
            class='icon-monitor icon-a-sousuo'
            v-bk-tooltips={{
              content: `${conditionKey} = ${idValue}`,
              placement: 'top',
            }}
            onClick={() => handleFilterByInstance(instance, 'eq')}
          />
          <i
            class='icon-monitor icon-sousuo-'
            v-bk-tooltips={{
              content: `${conditionKey} != ${idValue}`,
              placement: 'top',
            }}
            onClick={() => handleFilterByInstance(instance, 'neq')}
          />
        </div>
      );
    };

    return {
      handleShowChange,
      handleInstanceClick,
      handleFilterByInstance,
      renderOperationIcons,
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
              <span class='header-title'>{this.resource?.display_name || this.resourceKey}</span>
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
                      {this.renderOperationIcons(instance)}
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
