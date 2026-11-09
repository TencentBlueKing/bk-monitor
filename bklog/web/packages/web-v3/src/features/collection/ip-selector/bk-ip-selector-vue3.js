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

import { getCurrentInstance, h, onBeforeUnmount, onMounted, onUpdated, ref } from 'vue';

import { Component, merge, Vue2 } from '@blueking/ip-selector/dist/vue2.6.x.esm';

/**
 * Vue3 适配。上游用字符串 ref 绑定 setup 返回的 rootRef，Vue 3.5 会把 DOM 写进
 * setupState 而不是 rootRef.value，onMounted 里 appendChild 会抛错并中断后续组件的更新。
 */
export default options => {
  merge(options);

  return {
    name: 'bk-ip-selector',
    props: Object.assign({}, Component.props),
    emits: [...Component.emits],
    setup(props, context) {
      const rootRef = ref();

      let app = new Vue2({
        render: createElement => createElement(Component, {
          ref: 'componentRef',
          props,
        }),
      });

      const mountHost = () => rootRef.value || getCurrentInstance()?.vnode?.el;

      onMounted(() => {
        app.$mount();
        const host = mountHost();
        if (host && app.$el) {
          host.appendChild(app.$el);
        }
        Component.emits.forEach(eventName => {
          app.$refs.componentRef.$on(eventName, (...args) => {
            context.emit(eventName, ...args);
          });
        });
        onUpdated(() => {
          app.$forceUpdate();
        });
      });

      onBeforeUnmount(() => {
        if (app?.$el?.parentNode) {
          app.$el.parentNode.removeChild(app.$el);
        }
        app?.$destroy();
        app = null;
      });

      context.expose({
        getHostList() {
          return app.$refs.componentRef.getHostList();
        },
        getHostIpv4List() {
          return app.$refs.componentRef.getHostIpv4List();
        },
        getHostIpv6List() {
          return app.$refs.componentRef.getHostIpv6List();
        },
        getAbnormalHostIpv4List() {
          return app.$refs.componentRef.getAbnormalHostIpv4List();
        },
        getAbnormalHostIpv6List() {
          return app.$refs.componentRef.getAbnormalHostIpv6List();
        },
        getIpv4HostList() {
          return app.$refs.componentRef.getIpv4HostList();
        },
        getIpv6HostList() {
          return app.$refs.componentRef.getIpv6HostList();
        },
        getAbnormalIpv4HostList() {
          return app.$refs.componentRef.getAbnormalIpv4HostList();
        },
        getAbnormalIpv6HostList() {
          return app.$refs.componentRef.getAbnormalIpv6HostList();
        },
        resetValue() {
          app.$refs.componentRef.resetValue();
        },
        refresh() {
          app.$refs.componentRef.refresh();
        },
        collapseToggle(lastStatus) {
          app.$refs.componentRef.collapseToggle(lastStatus);
        },
        removeInvalidData() {
          app.$refs.componentRef.removeInvalidData();
        },
        showAllHostAgentStatistics() {
          app.$refs.componentRef.showAllHostAgentStatistics();
        },
      });

      return {
        rootRef,
        app,
      };
    },
    render() {
      return h('div', {
        role: 'bk-ip-selector',
        ref: 'rootRef',
        style: {
          height: 'inherit',
        },
      });
    },
  };
};
