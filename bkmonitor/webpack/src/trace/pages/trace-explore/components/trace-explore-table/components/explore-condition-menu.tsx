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

import { defineComponent, useTemplateRef } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import { Popover } from 'bkui-vue';
import { bkMessage } from 'monitor-api/utils';
import { copyText } from 'monitor-common/utils';

import { EMethod, EMode } from '../../../../../components/retrieval-filter/typing';

import './explore-condition-menu.scss';

export default defineComponent({
  name: 'ExploreConditionMenu',
  props: {
    conditionKey: {
      type: String,
    },
    conditionValue: {
      type: String,
    },
  },
  emits: ['conditionChange', 'onMenuClick'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const route = useRoute();
    const router = useRouter();

    const menuRef = useTemplateRef<HTMLElement>('menuRef');

    const menuList = [
      {
        id: 'copy',
        name: t('复制'),
        icon: 'icon-mc-copy',
        onClick: handleCopy,
      },
      {
        id: 'add',
        name: t('添加到本次检索'),
        icon: 'icon-a-sousuo',
        suffixRender: menuItemSuffixRender({ method: EMethod.eq }),
        onClick: () => handleConditionChange(EMethod.eq),
      },
      {
        id: 'delete',
        name: t('从本次检索中排除'),
        icon: 'icon-sousuo-',
        suffixRender: menuItemSuffixRender({ method: EMethod.ne }),
        onClick: () => handleConditionChange(EMethod.ne),
      },
      {
        id: 'new-page',
        name: t('新建检索'),
        icon: 'icon-mc-search',
        suffixRender: menuItemSuffixRender({ hasClick: false }),
        onClick: handleNewExplorePage,
      },
    ];

    /**
     * @description 弹出菜单popover 自定义后缀icon渲染
     * @param {EMethod} config.method 条件类型（eq等于 / ne不等于） 如果为空未传则走新建检索逻辑
     * @param {boolean} config.hasClick 是否有点击事件及 hover新开标签页 tooltip 提示
     *
     */
    function menuItemSuffixRender(config: { method?: EMethod; hasClick?: boolean }) {
      const { method, hasClick = true } = config;
      return () => (
        <Popover
          arrow={true}
          boundary={menuRef.value}
          content={t('新开标签页')}
          disabled={!hasClick}
          placement='top'
          theme='dark'
        >
          <i
            class={`icon-monitor icon-mc-goto ${hasClick ? 'hover-blue' : ''}`}
            onClick={e => handleNewExplorePage(e, method)}
          />
        </Popover>
      );
    }

    /**
     * @description 添加/删除 检索 回调
     */
    function handleConditionChange(method: EMethod) {
      if (!props.conditionValue) {
        return;
      }
      emit('conditionChange', {
        key: props.conditionKey,
        method: method,
        value: props.conditionValue,
      });
      emit('onMenuClick');
    }

    /**
     * @description 新建检索 回调
     * @param {MouseEvent} event 点击事件
     * @param {EMethod} method 条件类型（eq等于 / ne不等于） 如果为空未传则走新建检索逻辑
     *
     */
    function handleNewExplorePage(event, method?: EMethod) {
      event.stopPropagation();
      if (!props.conditionValue) {
        return;
      }
      const { where: routeWhere, queryString: routerQueryString, ...rest } = route.query;
      const value = props.conditionValue;
      let queryString = '';
      const where = [];
      const actualMethod = method || EMethod.eq;

      if (method) {
        where.push(...JSON.parse((routeWhere as string) || '[]'));
        queryString = (routerQueryString || '') as string;
      }
      if (rest.filterMode === EMode.queryString) {
        let endStr = `${props.conditionKey} : "${value || ''}"`;
        actualMethod === EMethod.ne && (endStr = `NOT ${endStr}`);
        queryString = queryString ? `${queryString} AND ${endStr}` : `${endStr}`;
      } else {
        let whereValue = value;
        try {
          whereValue = JSON.parse(value);
          if (!Array.isArray(whereValue)) {
            whereValue = typeof value === 'string' ? whereValue : value;
          }
        } catch {
          whereValue = value;
        }
        where.push({
          key: props.conditionKey,
          operator: actualMethod,
          value: Array.isArray(whereValue) ? whereValue : [whereValue || ''],
        });
      }
      const query = {
        ...rest,
        queryString: queryString,
        where: JSON.stringify(where),
      };
      const targetRoute = router.resolve({
        query,
      });
      emit('onMenuClick');
      window.open(`${location.origin}${location.pathname}${location.search}${targetRoute.href}`, '_blank');
    }

    /**
     * @description 处理复制事件
     *
     */
    function handleCopy() {
      copyText(props.conditionValue || '--', msg => {
        bkMessage({
          message: msg,
          theme: 'error',
        });
        return;
      });
      bkMessage({
        message: t('复制成功'),
        theme: 'success',
      });
      emit('onMenuClick');
    }

    return {
      menuList,
    };
  },
  render() {
    return (
      <ul
        ref='menuRef'
        class='explore-condition-menu'
      >
        {this.menuList.map(item => (
          <li
            key={item.id}
            class='menu-item'
            onClick={item.onClick}
          >
            <i class={`icon-monitor ${item.icon}`} />
            <span>{item.name}</span>
            <div class='item-suffix'>{item?.suffixRender?.()}</div>
          </li>
        ))}
      </ul>
    );
  },
});
