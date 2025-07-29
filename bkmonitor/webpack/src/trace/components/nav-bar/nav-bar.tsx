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
import { computed, defineComponent, inject } from 'vue';

import { useRoute, useRouter } from 'vue-router';

import type { ICommonNavBarProps, INavItem } from './type';

import './nav-bar.scss';

export default defineComponent({
  name: 'NavBar',
  props: {
    routeList: {
      type: Array,
      default: () => [],
    },
    needBack: {
      type: Boolean,
      default: false,
    },
    needShadow: {
      type: Boolean,
      default: false,
    },
    needCopyLink: {
      type: Boolean,
      default: false,
    },
    navMode: {
      type: String,
      default: 'share',
    },
    positionText: {
      type: String,
      default: '',
    },
    backGotoItem: {
      type: Object,
      default: () => ({ isBack: false }),
    },
    callbackRouterBack: {
      type: Function,
      default: undefined,
    },
  },
  setup(props: any | ICommonNavBarProps, { slots }) {
    const router = useRouter();
    const route = useRoute();
    const readonly = inject('readonly');
    const navList = computed(() => {
      if (window.__POWERED_BY_BK_WEWEB__ && window.token) {
        return window.__BK_WEWEB_DATA__.navList || props.routeList || [];
      }
      return props.routeList;
    });

    function handleGotoPage(item: INavItem) {
      if (readonly) return;
      const targetRoute = router.resolve({ name: item.id, query: item.query || {} });
      /** 防止出现跳转当前地址导致报错 */
      if (targetRoute.fullPath !== route.fullPath) {
        router.push({ name: item.id, query: item.query || {} });
      }
    }
    function handleBackGotoPage() {
      if (props.callbackRouterBack) {
        return props.callbackRouterBack();
      }
      if (props.backGotoItem?.id && !props.backGotoItem?.isBack) {
        router.push({ name: props.backGotoItem.id, query: props.backGotoItem.query || {} });
        return;
      }
      router.back();
    }
    function renderFn() {
      const len = props.routeList.length;
      return (
        <div
          key='navigationBar'
          class={`navigation-bar common-nav-bar ${props.needShadow ? 'detail-bar' : ''}`}
        >
          {!readonly && (props.needBack || ((props.needBack ?? true) && len > 1)) && (
            <span
              class='icon-monitor icon-back-left navigation-bar-back'
              onClick={() => handleBackGotoPage()}
            />
          )}
          {slots.custom ? (
            <div class='navigation-bar-list'>{slots.custom()}</div>
          ) : (
            <ul class='navigation-bar-list'>
              {navList.value.map((item, index) => (
                <li
                  key={index}
                  class='bar-item'
                >
                  {/* {index > 0 ? <span class="item-split icon-monitor icon-arrow-right"></span> : undefined} */}
                  {index > 0 ? <span class='item-split'>/</span> : undefined}
                  <span
                    class={`item-name ${!!item.id && index < len - 1 ? 'parent-nav' : ''} ${
                      len === 1 ? 'only-title' : ''
                    }`}
                    onClick={() => item.id && index < len - 1 && handleGotoPage(item)}
                  >
                    <span class='item-name-text'>{item.name}</span>
                    {!!item.subName && (
                      <span class='item-sub-name'>
                        {item.name ? '-' : ''}&nbsp;{item.subName}
                      </span>
                    )}
                  </span>
                </li>
              ))}
            </ul>
          )}
          {!!slots.append && <span class='nav-append-wrap'>{slots.append()}</span>}
        </div>
      );
    }
    return {
      renderFn,
    };
  },
  render() {
    return this.renderFn();
  },
});
