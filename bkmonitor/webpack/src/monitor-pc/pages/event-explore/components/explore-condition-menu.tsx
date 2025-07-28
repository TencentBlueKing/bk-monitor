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

import { copyText } from 'monitor-common/utils';

import { ECondition, EMethod, EMode } from '../../../components/retrieval-filter/utils';
import { SceneAliasMap } from '../../monitor-k8s/k8s-dimension';
import { SceneEnum } from '../../monitor-k8s/typings/k8s-new';

import type { ConditionChangeEvent } from '../typing';
import type { KVFieldList } from './explore-kv-list';

import './explore-condition-menu.scss';

interface ExploreConditionMenuProps {
  fieldTarget: KVFieldList;
  activeColumnOrIndex: 'key' | 'value' | number;
}

interface ExploreConditionMenuEvents {
  onConditionChange(condition: ConditionChangeEvent): void;
  onMenuClick(): void;
}

@Component
export default class ExploreConditionMenu extends tsc<ExploreConditionMenuProps, ExploreConditionMenuEvents> {
  /** 当前选中的条件对象 */
  @Prop({ type: Object }) fieldTarget: KVFieldList;
  /** 当前激活触发弹出 popover 的列或者激活的分词下标 */
  @Prop({ type: [String, Number] }) activeColumnOrIndex: 'key' | 'value' | number;

  /** 场景下拉菜单 dom 实例 */
  @Ref('sceneRef') sceneRef: any;

  menuList = [
    {
      id: 'copy',
      name: this.$t('复制'),
      icon: 'icon-mc-copy',
      onClick: this.handleCopy,
    },
    {
      id: 'add',
      name: this.$t('添加到本次检索'),
      icon: 'icon-a-sousuo',
      suffixRender: this.menuItemSuffixRender({ method: EMethod.eq }),
      onClick: () => this.handleConditionChange(EMethod.eq),
    },
    {
      id: 'delete',
      name: this.$t('从本次检索中排除'),
      icon: 'icon-sousuo-',
      suffixRender: this.menuItemSuffixRender({ method: EMethod.ne }),
      onClick: () => this.handleConditionChange(EMethod.ne),
    },
    {
      id: 'new-page',
      name: this.$t('新建检索'),
      icon: 'icon-mc-search',
      suffixRender: this.menuItemSuffixRender({ hasClick: false }),
      onClick: this.handleNewExplorePage,
    },
    // TODO 暂不支持配置，隐藏事件快捷跳转容器监控其他场景功能，等后续后端接口实现后补充逻辑
    // {
    //   id: 'other-scene',
    //   name: this.$t('查看该对象的其他场景'),
    //   icon: 'icon-switch',
    //   suffixRender: () => <i class={'icon-monitor icon-arrow-right '} />,
    //   onClick: this.handleScenePopoverShow,
    // },
  ];

  /** 二级 popover 实例(切换场景菜单) */
  childrenPopoverInstance = null;

  @Emit('conditionChange')
  conditionChange(condition: ConditionChangeEvent) {
    return condition;
  }

  @Emit('menuClick')
  menuClick() {
    return;
  }

  /**
   * @description 二级 popover (场景菜单)显示
   *
   */
  async handleScenePopoverShow(e: MouseEvent) {
    this.childrenPopoverInstance = this.$bkPopover(e.currentTarget, {
      content: this.sceneRef,
      trigger: 'click',
      placement: 'right-start',
      theme: 'light common-monitor event-to-k8s-scene-popover',
      arrow: false,
      interactive: true,
      boundary: 'viewport',
      distance: 4,
      offset: '-2, 0',
      onHidden: () => {
        this.handleScenePopoverHide();
      },
    });
    await this.$nextTick();
    this.childrenPopoverInstance?.show(100);
  }

  /**
   * @description 二级 popover (场景菜单)隐藏
   *
   */
  handleScenePopoverHide() {
    this.childrenPopoverInstance?.hide?.();
    this.childrenPopoverInstance?.destroy?.();
    this.childrenPopoverInstance = null;
  }

  /**
   * @description 获取当前激活menu 弹窗popover的 value
   * 由于存在分词，所以 fieldTarget 的 value 并不一定是最终激活的 value
   */
  getActiveValue() {
    const { value } = this.fieldTarget;
    if (!Array.isArray(value)) {
      return value;
    }
    return value?.[this.activeColumnOrIndex]?.value;
  }

  /**
   * @description 切换场景(新开页跳转至k8s容器监控实现)
   * @param {SceneEnum} targetScene 想要切换到的目标场景
   *
   */
  handleNewK8sPage(targetScene: SceneEnum) {
    // TODO 暂不支持配置，隐藏事件快捷跳转容器监控其他场景功能，等后续后端接口实现后补充逻辑
    // const { scene: currentScene, groupBy, filterBy, ...rest } = this.$route.query;
    // const targetPageGroupInstance = K8sGroupDimension.createInstance(targetScene);
    // targetPageGroupInstance.addGroupFilter(this.groupByField);

    // const query = {
    //   ...rest,
    //   filterBy: JSON.stringify({ [this.groupByField]: [this.filterValue] }),
    //   groupBy: JSON.stringify(targetPageGroupInstance.groupFilters),
    //   scene: targetScene,
    // };
    // const targetRoute = this.$router.resolve({
    //   query,
    // });
    // this.menuClick();
    // window.open(`${location.origin}${location.pathname}${location.search}${targetRoute.href}`, '_blank');
    this.handleScenePopoverHide();
    this.menuClick();
  }

  /**
   * @description 处理复制事件
   *
   */
  handleCopy() {
    copyText(this.getActiveValue() || '--', msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error',
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success',
    });
    this.menuClick();
  }

  /**
   * @description 新建检索 回调
   * @param {MouseEvent} event 点击事件
   * @param {EMethod} method 条件类型（eq等于 / ne不等于） 如果为空未传则走新建检索逻辑
   *
   */
  handleNewExplorePage(event, method?: EMethod) {
    event.stopPropagation();
    if (!this.fieldTarget?.value) {
      return;
    }
    const { targets, ...rest } = this.$route.query;
    const targetsList = targets ? JSON.parse(decodeURIComponent(targets as string)) : [];
    const sourceTarget = targetsList?.[0] || {};
    const queryConfig = sourceTarget?.data?.query_configs?.[0] || {};
    const { name, sourceName } = this.fieldTarget;
    const value = this.getActiveValue();
    let queryString = '';
    const where = [];
    const actualMethod = method || EMethod.eq;

    if (method) {
      where.push(...(queryConfig?.where || []));
      queryString = queryConfig?.query_string || '';
    }
    if (rest.filterMode === EMode.queryString) {
      let endStr = `${name} : "${value || ''}"`;
      actualMethod === EMethod.ne && (endStr = `NOT ${endStr}`);
      queryString = queryString ? `${queryString} AND ${endStr}` : `${endStr}`;
    } else {
      where.push({
        condition: ECondition.and,
        key: sourceName,
        method: actualMethod,
        value: [value || '""'],
      });
    }
    const query = {
      ...rest,
      targets: JSON.stringify([
        {
          ...sourceTarget,
          data: {
            query_configs: [
              {
                ...queryConfig,
                where,
                query_string: queryString,
              },
            ],
          },
        },
      ]),
    };
    const targetRoute = this.$router.resolve({
      query,
    });
    this.menuClick();
    window.open(`${location.origin}${location.pathname}${location.search}${targetRoute.href}`, '_blank');
  }

  /**
   * @description 添加/删除 检索 回调
   */
  handleConditionChange(method: EMethod) {
    if (!this.fieldTarget?.value) {
      return;
    }
    this.conditionChange({
      key: this.fieldTarget?.sourceName,
      method: method,
      value: this.getActiveValue(),
    });
    this.menuClick();
  }

  /**
   * @description kv 值点击弹出菜单popover 自定义后缀icon渲染
   * @param {EMethod} config.method 条件类型（eq等于 / ne不等于） 如果为空未传则走新建检索逻辑
   * @param {boolean} config.hasClick 是否有点击事件及 hover新开标签页 tooltip 提示
   *
   */
  menuItemSuffixRender(config: { method?: EMethod; hasClick?: boolean }) {
    const { method, hasClick = true } = config;
    return () => (
      <i
        class={`icon-monitor icon-mc-goto ${hasClick ? 'hover-blue' : ''}`}
        v-bk-tooltips={{ content: this.$t('新开标签页'), disabled: !hasClick }}
        onClick={e => this.handleNewExplorePage(e, method)}
      />
    );
  }

  /**
   * @description 场景 下拉菜单渲染
   *
   */
  sceneMenuListRender() {
    return (
      <div style='display: none'>
        <ul
          ref='sceneRef'
          class='scene-list-menu'
        >
          {[SceneEnum.Performance, SceneEnum.Capacity].map(scene => (
            <li
              key={scene}
              class='menu-item'
              onClick={() => this.handleNewK8sPage(scene)}
            >
              {SceneAliasMap[scene]}
            </li>
          ))}
        </ul>
      </div>
    );
  }

  render() {
    return (
      <ul
        ref='menuRef'
        class='explore-kv-list-menu'
      >
        {this.menuList.map(item => (
          <li
            key={item.id}
            class='menu-item'
            onClick={item.onClick}
          >
            <i class={`prefix-icon icon-monitor ${item.icon}`} />
            <span>{item.name}</span>
            <div class='item-suffix'>{item?.suffixRender?.()}</div>
          </li>
        ))}
        {/* TODO 暂不支持配置，隐藏事件快捷跳转容器监控其他场景功能，等后续后端接口实现后补充逻辑 */}
        {/* {this.sceneMenuListRender()} */}
      </ul>
    );
  }
}
