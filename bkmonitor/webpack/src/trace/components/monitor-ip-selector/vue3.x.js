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
import { h, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { Component, merge, Vue2 } from '@blueking/ip-selector/dist/vue2.6.x.esm';

export default options => {
  merge(options);

  return {
    name: 'bk-ip-selector',
    props: Object.assign({}, Component.props),
    emits: [...Component.emits],
    setup(props, context) {
      const rootRef = ref();

      let app = new Vue2(Component);
      const syncProps = () => {
        Object.keys(props).forEach(propName => {
          const newValue = props[propName];
          if (Object.prototype.toString.call(newValue) === '[object Object]') {
            const v = Object.keys(newValue).reduce(
              (result, item) => ({
                ...result,
                [item]: Array.isArray(newValue[item]) ? [...newValue[item]] : newValue[item],
              }),
              {}
            );

            app._props[propName] = Object.freeze(v);
          } else if (Object.prototype.toString.call(newValue) === '[object Array]') {
            app._props[propName] = [...newValue];
          } else {
            app._props[propName] = newValue;
          }
        });
      };

      const propWatchStack = [];
      Object.keys(props).forEach(propName => {
        const unwatch = watch(
          () => props[propName],
          () => {
            syncProps();
          },
          {
            immediate: true,
          }
        );
        propWatchStack.push(unwatch);
      });

      Component.emits.forEach(eventName => {
        app.$on(eventName, (...agrs) => {
          context.emit(eventName, ...agrs);
        });
      });
      syncProps();

      onMounted(() => {
        app.$mount();
        rootRef.value.appendChild(app.$el);
      });

      onBeforeUnmount(() => {
        propWatchStack.forEach(unwatch => unwatch());
        app.$el.parentNode.removeChild(app.$el);
        app.$destroy();
        app = null;
      });

      context.expose({
        getHostList() {
          return app.getHostList();
        },
        // 获取所有主机的 ipv4 列表
        getHostIpv4List() {
          return app.getHostIpv4List();
        },
        // 获取所有主机的 ipv6 列表
        getHostIpv6List() {
          return app.getHostIpv6List();
        },
        // 获取所有 agent 异常主机的 ipv4 列表
        getAbnormalHostIpv4List() {
          return app.getAbnormalHostIpv4List();
        },
        // 获取所有 agent 异常主机的 ipv6 列表
        getAbnormalHostIpv6List() {
          return app.getAbnormalHostIpv6List();
        },
        resetValue() {
          app.resetValue();
        },
        refresh() {
          app.refresh();
        },
        collapseToggle(lastStatus) {
          app.collapseToggle(lastStatus);
        },
        removeInvalidData() {
          app.removeInvalidData();
        },
      });

      return {
        rootRef,
        app,
        propWatchStack,
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
