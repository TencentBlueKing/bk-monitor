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
import { throttle } from 'lodash';
import { copyText } from 'monitor-common/utils/utils';
import tippy, { type Instance, type SingleTarget } from 'tippy.js';
import type Vue from 'vue';
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './index.scss';

interface IProps {
  /** 是否展示“复制全部标签”按钮 */
  copyenable?: boolean;
  /** 标签原始数据 */
  data: string[];
  /** 标签尺寸 */
  size?: 'default' | 'small';
  /** 标签主题 */
  theme?: string;
}

@Component
export default class TagBlock extends tsc<IProps> {
  @Prop({ type: Boolean, default: false }) copyenable: boolean;
  @Prop({ type: Array, required: true }) data: string[];
  @Prop({ type: String, default: 'default' }) size: IProps['size'];
  @Prop({ type: String, default: '' }) theme: string;

  @Ref('rootRef') rootRef!: HTMLDivElement;
  @Ref('moreRef') moreRef!: Vue;
  @Ref('tagList') tagList!: HTMLDivElement;
  @Ref('tipsPanel') tipsPanel!: HTMLDivElement;

  /** 实际渲染在可视区域内的标签数量 */
  renderTagNum = 1;

  /** “+N” 悬浮层实例 */
  tippyIns?: Instance;
  /** 根节点尺寸监听器，用于容器宽度变化时重算 */
  resizeObserver?: ResizeObserver;
  /** 计算版本号：用于丢弃过期的异步计算结果 */
  calcVersion = 0;
  /** requestAnimationFrame 任务 id，避免重复排队 */
  calcFrameId = 0;

  /** 当前真正参与渲染的标签数据 */
  get renderData() {
    return this.data.slice(0, this.renderTagNum);
  }

  /** 被折叠到“+N”中的标签数量 */
  get moreTagCount() {
    return this.data.length - this.renderTagNum;
  }

  /**
   * 计算在当前容器宽度下可展示的标签数量。
   * 核心思路：
   * 1. 先在隐藏测量区域拿到每个标签宽度；
   * 2. 预留 “+N” 占位和复制按钮占位；
   * 3. 逐个累加，直到超出可用宽度。
   */
  calcRenderTagNum() {
    // 每次进入计算都递增版本号；旧版本的异步回调将自动失效
    const version = ++this.calcVersion;
    // 若上一轮还存在未执行的 rAF，先取消，避免短时间内重复计算
    if (this.calcFrameId) {
      cancelAnimationFrame(this.calcFrameId);
    }
    // 等待本轮数据变更后的 DOM 更新完成，再读取尺寸
    this.$nextTick(() => {
      // 若期间又触发了新一轮计算，或组件已不可用，直接终止当前回调
      if (version !== this.calcVersion || !this.rootRef) {
        return;
      }
      // 空数据时直接归零，避免后续不必要计算
      if (this.data.length < 1) {
        this.renderTagNum = 0;
        return;
      }
      // 通过 rAF 把读取布局和计算放到下一帧，降低同步布局抖动风险
      this.calcFrameId = requestAnimationFrame(() => {
        // 执行后立即清空 id，表示当前帧任务已消费
        this.calcFrameId = 0;
        // 二次兜底：如果版本过期，丢弃这次结果
        if (version !== this.calcVersion) {
          return;
        }
        // 先拿到根容器可用于标签展示的理论最大宽度
        const maxWidth = this.getAvailableWidth();

        // renderTagCount: 逐个试算后“可实际容纳”的标签数
        let renderTagCount = 0;
        // +N 标签大致占位（含内边距/字体）预估值，用于提前预留空间
        const tipsTagPlaceholderWidth = 45;
        // 复制按钮启用时需要额外预留宽度
        const copyBtnWidth = this.copyenable ? 30 : 0;

        // 从隐藏测量区中抓取所有标签节点，以读取每个标签真实宽度
        const allTagEleList = Array.from(this.tagList?.querySelectorAll('.bk-tag') || []);
        // 极端场景（DOM 尚未生成）下直接退出，等待下一次触发重算
        if (!allTagEleList.length) {
          return;
        }
        // 默认沿用旧值，只有计算出新结果后再一次性覆盖，减少无效更新
        let nextRenderTagNum = this.renderTagNum;
        // 全量标签都能放下时，直接全部渲染
        if (this.tagList.getBoundingClientRect().width + copyBtnWidth <= maxWidth) {
          nextRenderTagNum = this.data.length;
        } else {
          // 标签之间在样式中存在固定间距
          const tagMargin = 6;
          // 初始化为 -tagMargin，抵消第一次累加时多加的一次间距
          let totalTagWidth = -tagMargin;

          for (let i = 0; i < allTagEleList.length; i++) {
            // 当前候选标签的实际像素宽度
            const { width: tagWidth } = allTagEleList[i].getBoundingClientRect();

            // 非最后一个标签时，需要预留“+N”位置；最后一个可不预留
            const availableWidth =
              maxWidth - copyBtnWidth - (i < allTagEleList.length - 1 ? tipsTagPlaceholderWidth : 0);
            // 单个标签本身就超出可用宽度时，不再继续
            if (tagWidth > availableWidth) {
              break;
            }

            // 先把当前标签尝试累加进总宽度（标签宽 + 间距）
            totalTagWidth += tagWidth + tagMargin;
            // 若累加后仍能保留“+N”和复制按钮的空间，则计入可渲染数
            if (totalTagWidth + tipsTagPlaceholderWidth + copyBtnWidth <= maxWidth) {
              renderTagCount = renderTagCount + 1;
            } else {
              // 一旦超限，后续标签只会更超，直接结束循环
              break;
            }
          }
          // 记录本次循环最终可渲染数量
          nextRenderTagNum = renderTagCount;
        }

        // 仅在结果发生变化时赋值，避免触发无意义的响应式更新
        if (this.renderTagNum !== nextRenderTagNum) {
          this.renderTagNum = nextRenderTagNum;
        }
      });
    });
  }

  @Watch('data', { deep: true, immediate: true })
  onDataChange() {
    // 标签数据变化后，重新计算可展示数量
    this.calcRenderTagNum();
  }

  @Watch('moreTagCount', { immediate: true })
  onMoreTagCountChange() {
    // 没有折叠项时，销毁并释放 tippy 实例
    if (this.moreTagCount < 1) {
      if (this.tippyIns) {
        this.tippyIns.hide();
        this.tippyIns.disable();
        this.tippyIns.destroy();
        this.tippyIns = undefined;
      }
      return;
    }

    this.$nextTick(() => {
      // 已存在实例仅更新内容，避免重复创建
      if (this.tippyIns) {
        this.syncTippyTipsProps();
        // 可能在“无折叠项”分支被 disable，这里确保重新可用
        this.tippyIns.enable();
        return;
      }
      // 首次出现“+N”时创建 tippy
      const moreEl = this.moreRef?.$el;
      if (!moreEl || !this.tipsPanel) {
        return;
      }
      const placement = this.getTipsPlacement(moreEl as HTMLElement, this.tipsPanel);
      // tippy 返回实例对象，后续复用并在销毁阶段统一清理
      this.tippyIns = tippy(moreEl as SingleTarget, {
        allowHTML: true,
        appendTo: () => document.body,
        arrow: true,
        content: this.getTippyContent(),
        hideOnClick: true,
        interactive: true,
        maxWidth: 400,
        onShow: instance => {
          this.applyTipsPanelScrollLimitOnShow(instance);
        },
        placement,
        popperOptions: {
          modifiers: [
            {
              name: 'preventOverflow',
              options: {
                padding: 20,
              },
            },
            {
              name: 'flip',
              options: {
                padding: 20,
              },
            },
          ],
        },
        theme: 'monitor-pc-tag-block-more',
        trigger: 'mouseenter',
        zIndex: 999999,
      });
    });
  }

  @Watch('renderTagNum')
  onRenderTagNumChange() {
    // 可见数量变化会影响“+N”面板内容，需要同步刷新
    if (!this.tippyIns || this.moreTagCount < 1) {
      return;
    }
    this.$nextTick(() => {
      this.syncTippyTipsProps();
    });
  }

  syncTippyTipsProps() {
    const moreEl = this.moreRef?.$el as HTMLElement | undefined;
    if (!this.tippyIns || !moreEl || !this.tipsPanel) {
      return;
    }
    this.tippyIns.setProps({
      content: this.getTippyContent(),
      placement: this.getTipsPlacement(moreEl, this.tipsPanel),
    });
  }

  getTippyContent() {
    // 返回克隆节点，避免 tippy 接管原始 DOM 导致渲染副作用
    if (!this.tipsPanel) {
      return '';
    }
    const panel = this.tipsPanel.cloneNode(true) as HTMLDivElement;
    const moreEl = this.moreRef?.$el as HTMLElement | undefined;
    if (moreEl) {
      this.applyTipsPanelScrollLimit(panel, moreEl);
    }
    return panel;
  }

  /** 测量面板自然高度，用于预判 flip 方向 */
  measureTipsPanelHeight(panelSource: HTMLElement) {
    const measureEl = panelSource.cloneNode(true) as HTMLElement;
    measureEl.style.maxHeight = 'none';
    measureEl.style.position = 'fixed';
    measureEl.style.top = '-9999px';
    measureEl.style.left = '-9999px';
    measureEl.style.visibility = 'hidden';
    measureEl.style.pointerEvents = 'none';
    document.body.appendChild(measureEl);
    const height = measureEl.scrollHeight;
    document.body.removeChild(measureEl);
    return height;
  }

  /**
   * 预判 tip 展示在参考元素上方还是下方（对齐 Popper flip 逻辑）。
   * 优先 top；上方放不下且下方更充裕时取 bottom。
   */
  getTipsPlacement(referenceEl: HTMLElement, panelSource: HTMLElement): 'top' | 'bottom' {
    const viewportGap = 20;
    const offset = 10;
    const tippyBoxExtra = 20;
    const refRect = referenceEl.getBoundingClientRect();
    const topSpace = refRect.top - viewportGap - offset;
    const bottomSpace = window.innerHeight - refRect.bottom - viewportGap - offset;
    const popperHeight = this.measureTipsPanelHeight(panelSource) + tippyBoxExtra;

    if (popperHeight <= topSpace) {
      return 'top';
    }
    if (popperHeight <= bottomSpace) {
      return 'bottom';
    }
    return topSpace >= bottomSpace ? 'top' : 'bottom';
  }

  calcTipsPanelMaxHeight(referenceEl: HTMLElement, placement: 'top' | 'bottom') {
    const viewportGap = 20;
    const offset = 10;
    const refRect = referenceEl.getBoundingClientRect();
    const availableHeight =
      placement === 'top'
        ? refRect.top - viewportGap - offset
        : window.innerHeight - refRect.bottom - viewportGap - offset;
    return Math.max(80, availableHeight);
  }

  applyTipsPanelScrollLimit(panel: HTMLElement, referenceEl: HTMLElement) {
    if (!this.tipsPanel) {
      return;
    }
    const placement = this.getTipsPlacement(referenceEl, this.tipsPanel);
    panel.style.maxHeight = `${this.calcTipsPanelMaxHeight(referenceEl, placement)}px`;
    panel.style.overflowY = 'auto';
  }

  /** onShow 内同步兜底：按当前位置重新预判并限制高度 */
  applyTipsPanelScrollLimitOnShow(instance: Instance) {
    const panel = instance.popper?.querySelector('.monitor-pc-tag-block-more-panel') as HTMLElement | null;
    const referenceEl = instance.reference as HTMLElement | undefined;
    if (!panel || !referenceEl || !this.tipsPanel) {
      return;
    }
    const placement = this.getTipsPlacement(referenceEl, this.tipsPanel);
    panel.style.maxHeight = `${this.calcTipsPanelMaxHeight(referenceEl, placement)}px`;
    panel.style.overflowY = 'auto';
    if (instance.props.placement !== placement) {
      instance.setProps({ placement });
    }
  }

  /**
   * 计算当前组件可用于展示标签的最大宽度。
   * 当父容器是 flex 布局时，需要扣除兄弟节点占用空间与外边距。
   */
  getAvailableWidth() {
    // 当前组件自身的可视宽度（含内容区），作为下限参考
    const rootWidth = this.rootRef.getBoundingClientRect().width;
    // 读取自身样式，用于计算 margin / maxWidth 等约束
    const rootStyle = getComputedStyle(this.rootRef);
    // 在 flex 场景下，可用空间需扣除自身水平外边距
    const rootHorizontalMargin = parseFloat(rootStyle.marginLeft) + parseFloat(rootStyle.marginRight);
    // 父节点用于判断布局类型与可分配总宽度
    const parentEl = this.rootRef.parentElement;
    const parentStyle = parentEl ? getComputedStyle(parentEl) : undefined;
    // 默认以自身宽度作为可用值，避免出现负值导致界面抖动
    let availableWidth = rootWidth;

    if (parentEl && parentStyle?.display.includes('flex')) {
      // 统计同级兄弟节点总占用（宽度 + 外边距）
      const siblingWidth = Array.from(parentEl.children).reduce((totalWidth, child) => {
        // 跳过自己，只计算“其他兄弟”占位
        if (child === this.rootRef) {
          return totalWidth;
        }
        const childStyle = getComputedStyle(child);
        const childHorizontalMargin = parseFloat(childStyle.marginLeft) + parseFloat(childStyle.marginRight);
        return totalWidth + child.getBoundingClientRect().width + childHorizontalMargin;
      }, 0);

      // 父容器总宽度 - 兄弟占位 - 自身 margin = 理论可分配宽度
      availableWidth = parentEl.getBoundingClientRect().width - siblingWidth - rootHorizontalMargin;
    }

    // 如果设置了 max-width，则再做一次上限约束
    const maxWidth = parseFloat(rootStyle.maxWidth);
    if (Number.isFinite(maxWidth)) {
      availableWidth = Math.min(availableWidth, maxWidth);
    }

    // 最终不小于 rootWidth，保证已渲染内容不会因计算值过小而被反复压缩
    return Math.max(availableWidth, rootWidth);
  }

  handleCopy(e: MouseEvent) {
    // 阻止冒泡，避免触发父级点击事件
    e.stopPropagation();
    // hasErr 用于区分 copyText 回调是否返回错误信息
    let hasErr = false;
    // 按行拼接后复制；失败时展示错误消息
    copyText(this.data.join('\n'), errMsg => {
      this.$bkMessage({
        message: errMsg,
        theme: 'error',
      });
      hasErr = !!errMsg;
    });
    // 无报错时提示成功，并带上复制条数
    if (!hasErr) {
      this.$bkMessage({
        message: this.$t('复制成功，共n条', { n: this.data.length }) as string,
        theme: 'success',
      });
    }
  }

  mounted() {
    // 首次挂载后计算一次展示数量
    this.calcRenderTagNum();

    // 监听自身尺寸变化（窗口缩放、父容器变化等）
    this.resizeObserver = new ResizeObserver(
      throttle(() => {
        // 容器尺寸频繁变化时，节流触发重算，避免高频布局计算
        this.calcRenderTagNum();
      }, 500)
    );
    // 仅观察根节点尺寸即可覆盖大多数展示变化场景
    this.resizeObserver.observe(this.rootRef);
  }

  beforeDestroy() {
    // 组件销毁时，主动清理浮层和监听器，避免内存泄漏
    if (this.tippyIns) {
      // 先隐藏再卸载，避免销毁前短暂闪烁
      this.tippyIns.hide();
      this.tippyIns.unmount();
      this.tippyIns.destroy();
    }
    // 断开 ResizeObserver，防止组件销毁后继续触发回调
    this.resizeObserver?.disconnect();
    if (this.calcFrameId) {
      // 清理可能尚未执行的 rAF 任务，避免访问已销毁实例
      cancelAnimationFrame(this.calcFrameId);
    }
  }

  render() {
    const hasData = this.data?.length;
    const { size, theme, copyenable } = this;

    return (
      <div
        ref='rootRef'
        class='monitor-pc-tag-block'
      >
        {hasData ? (
          [
            ...this.renderData.map(item => (
              <bk-tag
                key={item}
                size={size}
                theme={theme}
                v-bk-overflow-tips
              >
                <span>{item}</span>
              </bk-tag>
            )),
            this.moreTagCount > 0 ? (
              <bk-tag
                key='more'
                ref='moreRef'
                size={size}
                theme={theme}
                style='cursor: pointer;'
              >
                +{this.moreTagCount}
              </bk-tag>
            ) : undefined,
            copyenable ? (
              <div
                key='copy'
                class='copy-btn'
                v-bk-tooltips={this.$t('复制所有')}
                onClick={this.handleCopy}
              >
                <i class='icon-monitor icon-mc-copy' />
              </div>
            ) : undefined,
          ]
        ) : (
          <span>--</span>
        )}
        <div
          ref='tagList'
          style={{
            position: 'fixed',
            top: '-9999px',
            left: '-9999px',
            pointerEvents: 'none',
            wordBreak: 'keep-all',
            whiteSpace: 'nowrap',
            visibility: 'hidden',
          }}
        >
          {/* 隐藏测量区域：用于预渲染所有标签并获取真实宽度，不参与可视展示 */}
          {this.data.map(item => (
            <bk-tag
              key={item}
              size={size}
              theme={theme}
            >
              {item}
            </bk-tag>
          ))}
        </div>
        <div style={{ display: 'none' }}>
          <div
            ref='tipsPanel'
            class='monitor-pc-tag-block-more-panel'
          >
            {/* “+N” 悬浮面板内容：展示被折叠的剩余标签 */}
            {this.data.slice(this.renderData.length).map(item => (
              <div
                key={item}
                class='monitor-pc-tag-block-more-panel-item'
              >
                {item}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }
}
