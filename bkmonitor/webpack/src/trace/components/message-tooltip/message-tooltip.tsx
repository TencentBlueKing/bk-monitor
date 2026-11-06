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
import { type PropType, computed, defineComponent, nextTick, onBeforeUnmount, shallowRef, watch } from 'vue';

import { useResizeObserver } from '@vueuse/core';
import { Message, Popover } from 'bkui-vue';
import { bkTooltips } from 'bkui-vue/lib/directives';
import { copyText } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import './message-tooltip.scss';

/** Popover 实例中本组件需要的部分 */
interface PopoverInstance {
  /** bkui-vue Popover 暴露的内部显隐状态，置 false 立即隐藏，不受 popoverDelay 影响 */
  localIsShow?: boolean;
  /** Popover 默认插槽渲染出的 Reference 组件实例，$el 为触发元素或其片段锚点 */
  refDefaultReference?: { $el?: Node };
}

/** 弹层控制器：供「当前实例」在出现时立即关闭其他已出现的弹层 */
interface TooltipControl {
  close: () => void;
}

/**
 * 当前已展开的弹层控制器。全模块共享，保证同一时刻只存在一个 MessageTooltip 弹层。
 * 新弹层出现时会调用上一个的 close() 立即关闭，不留任何延迟。
 */
let activeControl: TooltipControl | null = null;

/** 正文美化结果：isJson 用于切换等宽字体，text 为最终展示文本 */
interface FormattedDetail {
  isJson: boolean;
  text: string;
}

/**
 * 美化详情正文：对象 / 数组形态的 JSON 缩进展开，其余文本原样保留（由样式负责保留换行）。
 * 仅做展示，复制仍使用原始 detail，避免粘贴内容被改写。
 */
const formatDetail = (detail: string): FormattedDetail => {
  const trimmed = detail.trim();
  if (!trimmed || !(trimmed.startsWith('{') || trimmed.startsWith('['))) {
    return { isJson: false, text: detail };
  }
  try {
    return { isJson: true, text: JSON.stringify(JSON.parse(trimmed), null, 2) };
  } catch {
    return { isJson: false, text: detail };
  }
};

/**
 * 消息提示 Popover：标题 + 复制 + 详情正文，供各错误 icon 与消息内容复用。
 * 触发图标由默认插槽传入，调用方自行控制图标形态与类名。
 * 全局唯一实例：新弹层出现时会立即关闭上一个已展开的弹层。
 */
export default defineComponent({
  name: 'MessageTooltip',
  directives: { bkTooltips },
  props: {
    /** 详情正文，为空时展示占位「--」 */
    detail: {
      type: String,
      default: '',
    },
    /** 弹层相对触发图标的方向 */
    placement: {
      type: String as PropType<'bottom' | 'left' | 'right' | 'top'>,
      default: 'bottom',
    },
    /** 悬停后延迟弹出，[显示, 隐藏] */
    popoverDelay: {
      type: Array as unknown as PropType<[number, number]>,
      default: () => [200, 100],
    },
    /** 标题，缺省时使用「错误信息」 */
    title: {
      type: String,
      default: '',
    },
    /** 仅当触发元素文本被省略（scrollWidth > clientWidth）时才允许弹出 */
    onlyOnOverflow: {
      type: Boolean,
      default: false,
    },
  },
  setup(props, { slots }) {
    const { t } = useI18n();
    // 实例引用需响应式：既要供单例逻辑即时关闭，也要据此解析触发元素测量溢出
    const popoverRef = shallowRef<PopoverInstance | null>(null);
    /** 触发元素文本是否被省略；测量失败时保持 true，退回「始终可弹」的默认行为 */
    const overflowing = shallowRef(true);

    /** 详情正文美化结果，随 detail 变化重新计算 */
    const formattedDetail = computed(() => formatDetail(props.detail));

    /**
     * 触发元素：Popover 的 Reference 以 Fragment 渲染默认插槽，
     * 此时 $el 是片段起始的文本锚点，需向后取真实元素（与 bkui-vue 内部 resolveTargetElement 一致），
     * 否则测量恒拿不到元素，onlyOnOverflow 会失效。
     */
    const referenceEl = computed<HTMLElement | null>(() => {
      const el = popoverRef.value?.refDefaultReference?.$el;
      if (el instanceof HTMLElement) return el;
      const next = el instanceof Text ? el.nextElementSibling : null;
      return next instanceof HTMLElement ? next : null;
    });

    /** 记录 Popover 实例，供单例逻辑即时关闭与溢出测量使用 */
    const setPopoverRef = (el: unknown) => {
      popoverRef.value = (el as PopoverInstance) ?? null;
    };

    /** 按触发元素是否出现省略来刷新可弹出状态 */
    const syncOverflow = () => {
      const el = referenceEl.value;
      if (!el) {
        overflowing.value = true;
        return;
      }
      overflowing.value = el.scrollWidth > el.clientWidth;
    };

    useResizeObserver(referenceEl, syncOverflow);

    // detail 变化会改变插槽文本宽度，但元素盒子尺寸可能不变，ResizeObserver 不触发，需手动补测
    watch(
      () => props.detail,
      () => {
        nextTick(syncOverflow);
      },
      { immediate: true }
    );

    /** 仅在开启 onlyOnOverflow 且未出现省略时禁用 Popover，避免无意义弹出 */
    const popoverDisabled = computed(() => props.onlyOnOverflow && !overflowing.value);

    /** 文本复制 */
    const handleCopyText = (text: string) => {
      let msgStr = t('复制成功');
      copyText(text, errMsg => {
        msgStr = errMsg as string;
      });
      Message({ theme: 'success', message: msgStr });
    };

    /**
     * 立即关闭：直接置 Popover 内部显隐状态为 false，
     * 绕过 hide() 的 popoverDelay 延时，实现零延迟消失。
     */
    const closeImmediately = () => {
      if (popoverRef.value) {
        popoverRef.value.localIsShow = false;
      }
    };

    const control: TooltipControl = { close: closeImmediately };

    /** 弹层出现：立即关闭其他已出现的弹层，并把自己登记为当前唯一实例 */
    const handleAfterShow = () => {
      if (activeControl && activeControl !== control) {
        activeControl.close();
      }
      activeControl = control;
    };

    /** 弹层收起：若自己仍是当前实例则释放登记，避免持有已关闭的弹层 */
    const handleAfterHidden = () => {
      if (activeControl === control) {
        activeControl = null;
      }
    };

    onBeforeUnmount(() => {
      handleAfterHidden();
    });

    return () => (
      <Popover
        ref={setPopoverRef}
        extCls='message-tooltip'
        placement={props.placement}
        popoverDelay={props.popoverDelay}
        disabled={popoverDisabled.value}
        onAfterShow={handleAfterShow}
        onAfterHidden={handleAfterHidden}
        v-slots={{
          content: () => (
            <div class='message-tooltip-content'>
              <div class='message-tooltip-content-title'>
                <span class='title-text'>{props.title || t('错误信息')}</span>
                {props.detail ? (
                  <i
                    class='icon-monitor icon-mc-copy'
                    // v-bk-tooltips={{ content: t('复制'), delay: 200, boundary: 'window' }}
                    onClick={() => {
                      handleCopyText(props.detail);
                    }}
                  />
                ) : null}
              </div>
              <div class={['message-tooltip-content-main', { 'is-json': formattedDetail.value.isJson }]}>
                {props.detail ? formattedDetail.value.text : '--'}
              </div>
            </div>
          ),
        }}
      >
        {slots.default?.()}
      </Popover>
    );
  },
});
