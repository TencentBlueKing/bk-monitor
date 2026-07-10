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
import Vue, { h, ref, type Ref } from 'vue';

import useLocale from '@/hooks/use-locale';
import AiSvg from '@/images/ai/ai-bluking-2.svg';

import TaskRunning from '../global/utils/task-pool';

class TaskEventManager {
  taskEventPool: WeakMap<object, any>;
  activeKey: any;
  constructor() {
    this.taskEventPool = new WeakMap();
    this.activeKey = null;
  }

  appendEvent(key: object, fn: (..._args: any) => void) {
    this.taskEventPool.set(key, fn);
  }

  setActiveKey(v) {
    this.activeKey = v;
  }

  getActiveFn() {
    return this.taskEventPool.get(this.activeKey);
  }

  executeFn(...args) {
    this.getActiveFn()?.(...args);
  }
}

const taskEventManager = new TaskEventManager();

export interface UseSegmentPropOptions {
  delineate?: boolean;
  onclick?: (..._args: any) => void;
  stopPropagation?: boolean;
  aiBluekingEnabled?: boolean;
  highlightEnabled?: boolean;
  allowDelineateSearch?: boolean;
}

class UseSegmentProp {
  private className = 'bklog-segment-pop-content';
  private wrapperClassName = 'bklog-pop-wrapper';
  private wrapperIdName = 'bklog_pop_wrapper';
  /** 当前实例的 owner id，用于把弹层内容与实例绑定 */
  private instanceId: string;
  private refContent: Ref<HTMLElement>;
  private delineate: boolean;
  private $t: (_str: string) => string;
  private onclick: (..._args: any) => void;
  private stopPropagation: boolean;
  private aiBluekingEnabled: boolean;
  private highlightEnabled: boolean;
  private allowDelineateSearch: boolean;

  /**
   * 生成实例 owner id（跨 bundle 全局唯一）。
   *
   * 注意：APM 和 Trace 在宿主页里可能是两个独立构建产物，
   * 如果只使用“模块内 static 计数器”，每个 bundle 都会从 1 开始计数，
   * 最终产生同名 owner（例如都叫 segment-pop-1），依然会误复用对方节点。
   *
   * 这里把计数器提升到 window 级别，确保两个独立包共享同一计数空间。
   */
  private static getNextInstanceId() {
    const nextCounter = (window.__BKLOG_SEGMENT_POP_COUNTER__ ?? 0) + 1;
    window.__BKLOG_SEGMENT_POP_COUNTER__ = nextCounter;
    return `segment-pop-${nextCounter}`;
  }

  constructor({
    delineate = false,
    onclick,
    stopPropagation = false,
    aiBluekingEnabled = true,
    highlightEnabled = true,
    allowDelineateSearch = false,
  }: UseSegmentPropOptions = {}) {
    const { $t } = useLocale();
    // 生成全局唯一 owner，后续会写到 DOM data 属性中做精确定位。
    this.instanceId = UseSegmentProp.getNextInstanceId();
    this.$t = $t;
    this.refContent = ref();
    this.delineate = delineate;
    this.aiBluekingEnabled = aiBluekingEnabled;
    this.highlightEnabled = highlightEnabled;
    this.allowDelineateSearch = allowDelineateSearch;
    this.onclick = onclick;
    this.stopPropagation = stopPropagation;
    if (!this.delineate) {
      setTimeout(() => {
        this.onMountedFn();
      });
    }
  }

  /**
   * 创建分段内容
   * @param refName
   * @returns
   */
  createSegmentContent(refName: Ref) {
    const eventBoxList = [
      {
        id: 'copy',
        onClick: (e: MouseEvent) => this.executeClickEvent(e, 'copy'),
        iconName: 'icon bklog-icon bklog-copy-3',
        text: this.$t('复制'),
        disabled: false,
      },
      {
        id: 'highlight',
        onClick: (e: MouseEvent) => this.executeClickEvent(e, 'highlight'),
        iconName: 'icon bklog-icon bklog-highlight',
        text: this.$t('高亮'),
        disabled: !this.highlightEnabled,
      },
      {
        id: 'add-to-ai',
        onClick: (e: MouseEvent) => this.executeClickEvent(e, 'add-to-ai'),
        svg: AiSvg,
        text: this.$t('引用至小鲸'),
        disabled: !this.delineate || !this.aiBluekingEnabled,
      },
      {
        id: 'is',
        onClick: (e: MouseEvent) => this.executeClickEvent(e, 'is'),
        iconName: 'icon bk-icon icon-plus-circle',
        text: this.$t('添加到本次检索'),
        disabled: this.delineate && !this.allowDelineateSearch,
        link: this.delineate ? undefined : {
          tooltip: this.$t('新开标签页'),
          iconName: 'bklog-icon bklog-jump',
          onClick: (e) => {
            e.stopPropagation();
            taskEventManager.executeFn('is', true);
          },
        },
      },
      {
        id: 'not',
        onClick: (e: MouseEvent) => this.executeClickEvent(e, 'not'),
        iconName: 'icon bk-icon icon-minus-circle',
        text: this.$t('从本次检索中排除'),
        disabled: this.delineate,
        link: {
          tooltip: this.$t('新开标签页'),
          iconName: 'bklog-icon bklog-jump',
          onClick: (e) => {
            e.stopPropagation();
            taskEventManager.executeFn('not', true);
          },
        },
      },
      {
        id: 'new-search-page-is',
        onClick: (e: MouseEvent) => this.executeClickEvent(e, 'new-search-page-is', true),
        iconName: 'icon bk-icon icon-plus-circle',
        text: this.$t('新建检索'),
        disabled: this.delineate,
        link: {
          iconName: 'bklog-icon bklog-jump',
        },
      },
      {
        id: 'trace-view',
        onClick: (e: MouseEvent) => this.executeClickEvent(e, 'trace-view', true),
        iconName: 'bklog-icon bklog-jincheng bklog-trace-view',
        text: this.$t('关联Trace检索'),
        disabled: this.delineate,
        link: {
          iconName: 'bklog-icon bklog-jump',
        },
      },
    ]
      .filter((item) => {
        if (window?.__IS_MONITOR_TRACE__) {
          // return item.text !== this.$t('新建检索');
          return !['new-search-page-is', 'add-to-ai'].includes(item.id);
        }
        return !item.disabled;
      })
      .map((item) => {
        if (window?.__IS_MONITOR_TRACE__) {
          return {
            ...item,
            link: undefined,
          };
        }
        return item;
      });

    return h('div', {
      class: 'segment-event-icons event-tippy-content',
      ref: refName,
      attrs: {
        /**
         * 将弹层内容显式声明为“属于哪个 UseSegmentProp 实例”。
         * 当多个独立包并存时，后续 mounted/query 会基于该属性做实例级选择，
         * 避免跨包共享节点造成事件上下文错配，进而出现点击无响应。
         */
        'data-segment-owner': this.instanceId,
      },
    }, [
      eventBoxList.map(item => h(
        'div',
        {
          class: 'segment-event-box',
          attrs: {
            'data-item-id': item.id,
          },
          on: {
            click: item.onClick,
          },
        },
        [
          h(
            'span',
            {
              class: 'segment-event-btn',
            },
            [
              h('span', { class: 'segment-btn-left', style: { display: 'inline-flex' } }, [
                item.svg
                  ? h('img', { attrs: { src: item.svg }, style: 'width: 16px; height: 16px; margin-right: 4px;' })
                  : h('i', { class: item.iconName }),
                h('span', {}, [item.text]),
              ]),
              item.link
                ? h(
                  'div',
                  {
                    class: 'segment-new-link',
                    on: { ...(item.link.onClick ? { click: item.link.onClick } : {}) },
                    directives: item.link.tooltip
                      ? [
                        {
                          name: 'bk-tooltips',
                          value: item.link.tooltip,
                        },
                      ]
                      : [],
                  },
                  [h('i', { class: item.link.iconName })],
                )
                : null,
            ],
          ),
        ],
      ),
      ),
    ]);
  }

  mountedToBody = () => {
    let target = document.body.querySelector(`.${this.wrapperClassName}`);
    if (!target) {
      target = document.createElement('div');
      target.setAttribute('id', this.wrapperIdName);
      target.classList.add(this.wrapperClassName);
      document.body.appendChild(target);
    }

    /**
     * 仅匹配“当前实例拥有”的弹层节点：
     * - 不再使用通配 `.event-tippy-content`，避免命中其他包创建的节点
     * - 如果当前实例节点不存在才创建，存在则直接复用（幂等）
     */
    const ownContentSelector = `.${this.className} .event-tippy-content[data-segment-owner="${this.instanceId}"]`;
    if (!target.querySelector(ownContentSelector)) {
      const app = new Vue({
        render: () => {
          return h('div', { class: this.className, style: 'display: none;' }, [
            this.createSegmentContent(this.refContent),
          ]);
        },
      });
      const tempDiv = document.createElement('div');
      app.$mount(tempDiv);
      target.append(app.$el);
    }

    if (!this.refContent.value) {
      // refContent 只缓存当前实例节点，保证 getSegmentContent 的引用与事件绑定一致。
      this.refContent.value = target.querySelector(ownContentSelector);
    }
  };

  getSegmentContent(keyRef: Ref<HTMLElement | null>, onSegmentEnumClick: (..._args: any) => void) {
    taskEventManager.appendEvent(keyRef, onSegmentEnumClick);
    taskEventManager.setActiveKey(keyRef);
    return this.refContent;
  }

  /**
   * 设置点击上下文
   * @param keyRef
   * @param clickEvent
   */
  setClickContext({ keyRef, clickEvent }) {
    taskEventManager.appendEvent(keyRef, clickEvent);
    taskEventManager.setActiveKey(keyRef);
  }

  onMountedFn() {
    TaskRunning(this.mountedToBody.bind(this));
  }

  private executeClickEvent(e: MouseEvent, ...args) {
    if (this.stopPropagation) {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
    }

    if (this.onclick) {
      this.onclick(e, ...args);
      return;
    }

    taskEventManager.executeFn(...args);
  }
}

const UseSegmentPropInstance = new UseSegmentProp();
export default UseSegmentPropInstance;
export { UseSegmentProp };
