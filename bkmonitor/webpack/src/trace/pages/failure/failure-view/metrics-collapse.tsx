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
import { computed, defineComponent, ref } from 'vue';

import { Popover } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './metrics-collapse.scss';

const DASHBOARD_PANEL_COLUMN_KEY = '__aiops_metrics_chart_view_type__';

export default defineComponent({
  name: 'MetricsCollapse',
  props: {
    id: {
      type: String,
    },
    info: {
      type: Object,
      default: () => ({}),
    },
    /** 是否展示头部展开收起 */
    showCollapse: {
      type: Boolean,
      default: true,
    },
    title: {
      type: String,
      default: '',
    },
    /** 图表布局方式 0: 一栏 1: 二栏 2: 三栏 */
    layoutActive: {
      type: Number,
      default: 0,
    },
    /** 是否需要图表分栏布局按钮 */
    needLayout: {
      type: Boolean,
      default: true,
    },
  },
  emits: ['layoutChange'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const popover = ref(null);
    /** 是否展示布局描述 */
    const showLayoutName = ref<boolean>(true);
    /** 展开收起 */
    const isCollapse = ref<boolean>(false);
    /** 是否展示修改布局icon */
    const showLayoutPopover = ref<boolean>(false);
    /** 图表布局图表 */
    const panelLayoutList = [
      {
        id: 1,
        name: t('一列'),
      },
      {
        id: 3,
        name: t('三列'),
      },
    ];
    const currentLayout = computed(() => {
      return panelLayoutList[props.layoutActive > 0 ? 1 : 0];
    });
    const handleResize = (el: HTMLElement) => {
      const react = el.getBoundingClientRect();
      showLayoutName.value = react.width > 600;
    };
    /** 切换展开收起 */
    const handleToggleCollapse = (activeAuto = false) => {
      if (activeAuto && !isCollapse.value) {
        return;
      }
      isCollapse.value = !isCollapse.value;
    };
    const handleStop = e => {
      e.stopPropagation();
      e.preventDefault();
      return false;
    };
    const handleChangeLayout = (id: number) => {
      popover.value?.hide();
      localStorage.setItem(DASHBOARD_PANEL_COLUMN_KEY, (id - 1).toString());
      emit('layoutChange', id - 1);
    };
    return {
      handleResize,
      isCollapse,
      showLayoutPopover,
      showLayoutName,
      currentLayout,
      panelLayoutList,
      handleToggleCollapse,
      handleStop,
      handleChangeLayout,
      popover,
    };
  },
  render() {
    return (
      <div class='metrics-collapse'>
        <div class='correlation-metrics-collapse'>
          <div
            class={[
              'correlation-metrics-collapse-head',
              `correlation-metrics-collapse-head-${!this.$props.showCollapse ? 'hide' : 'show'}`,
            ]}
          >
            <i
              class={[
                'icon-monitor bk-card-head-icon collapse-icon',
                this.isCollapse ? 'icon-mc-arrow-right' : 'icon-mc-arrow-down',
              ]}
              onClick={this.handleToggleCollapse.bind(this, false)}
            />
            <span
              class='correlation-metrics-title'
              onClick={this.handleToggleCollapse.bind(this, false)}
            >
              {this.$props.title || this.$slots.title()}
            </span>
            <div class={['correlation-metrics-right', this.showLayoutPopover && 'correlation-metrics-right-show']}>
              {this.$props.needLayout && (
                <Popover
                  ref='popover'
                  extCls='correlation-metrics-layout-popover'
                  v-slots={{
                    content: () => {
                      return (
                        <ul class='layout-list'>
                          {this.panelLayoutList.map(item => (
                            <li
                              key={item.id}
                              class={`layout-list-item ${item.id === this.$props.layoutActive + 1 ? 'item-active' : ''}`}
                              onClick={() => this.handleChangeLayout(item.id)}
                            >
                              {item.name}
                            </li>
                          ))}
                        </ul>
                      );
                    },
                  }}
                  arrow={false}
                  placement='bottom'
                  theme='light'
                  // onHide={() => (this.showLayoutPopover = false)}
                  // onShow={() => (this.showLayoutPopover = true)}
                >
                  <span
                    class='panels-tools-layout right-item'
                    onClick={this.handleStop}
                  >
                    <i
                      class='icon-monitor icon-mc-two-column'
                      v-bk-tooltips={{
                        content: this.currentLayout.name,
                        delay: 200,
                        disabled: !!this.showLayoutName,
                        appendTo: 'parent',
                      }}
                    />
                    {this.showLayoutName ? <span class='layout-name'>{this.currentLayout.name}</span> : undefined}
                  </span>
                </Popover>
              )}
            </div>
          </div>
          {!(this.isCollapse && this.showCollapse) && (
            <div class={['correlation-metrics-collapse-content']}>
              {(this.$slots as any)?.default?.({ column: this.layoutActive + 1 })}
            </div>
          )}
        </div>
      </div>
    );
  },
});
