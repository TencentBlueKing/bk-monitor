/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { type Ref, onBeforeUnmount, onMounted, shallowRef } from 'vue';

import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

/** 引用文本超出这个长度就截断，和左侧划词引用保持一致 */
const MAX_CONTEXT_TEXT_LENGTH = 300;

/**
 * 菜单紧贴触发项下沿，不留视觉缝隙：缝隙由菜单自己的透明桥接区（padding-top）补，
 * 指针从触发项移到菜单全程都在这两者之上，不会掉进没人管的死区。
 */
const MENU_OFFSET_Y = 0;

/** 指针从触发项移到菜单的缓冲时间 */
const HIDE_DELAY = 500;

/** 可引用的明细项用这个属性标记，值即引用文本 */
const TRIGGER_ATTR = 'data-chat-text';

/** 菜单根节点类名，指针移进菜单时据此免掉隐藏倒计时 */
const MENU_CLASS = 'ai-diagnostic-hover-menu';

/** 指针离开触发项与菜单多远才算真的移开 */
const ZONE_PADDING = 10;

interface IHoverMenuState {
  category: string;
  label: string;
  text: string;
  x: number;
  y: number;
}

/**
 * 悬浮 AI 诊断里的分析明细时弹出「添加至聊天」，点击后把这条明细作为引用交给底部会话输入框。
 * 触发项通过 data-chat-text / data-chat-label / data-chat-category 标记，这里统一做事件委派。
 */
export function useHoverToChat(containerRef: Ref<HTMLElement | null>) {
  const store = useAlarmCenterDetailStore();
  const hoverMenu = shallowRef<IHoverMenuState | null>(null);

  let hideTimer: ReturnType<typeof setTimeout> | null = null;
  /** 当前菜单归属的触发项，用来判断指针是否还在「触发项 + 菜单」这片区域里 */
  let activeTrigger: HTMLElement | null = null;

  const clearHideTimer = () => {
    if (hideTimer) {
      clearTimeout(hideTimer);
      hideTimer = null;
    }
  };

  const hideMenu = () => {
    clearHideTimer();
    activeTrigger = null;
    hoverMenu.value = null;
  };

  const scheduleHide = () => {
    if (hideTimer) return;
    hideTimer = setTimeout(() => {
      activeTrigger = null;
      hoverMenu.value = null;
      hideTimer = null;
    }, HIDE_DELAY);
  };

  const resolveTrigger = (target: EventTarget | null): HTMLElement | null => {
    const element = target instanceof Element ? target : null;
    const trigger = element?.closest(`[${TRIGGER_ATTR}]`) as HTMLElement | null;
    if (!trigger || !containerRef.value?.contains(trigger)) return null;
    return trigger;
  };

  const handleMouseover = (event: MouseEvent) => {
    const trigger = resolveTrigger(event.target);
    if (!trigger) return;
    const text = (trigger.getAttribute(TRIGGER_ATTR) || '').replace(/\s+/g, ' ').trim();
    if (!text) return;
    clearHideTimer();
    activeTrigger = trigger;
    const rect = trigger.getBoundingClientRect();
    hoverMenu.value = {
      text: text.slice(0, MAX_CONTEXT_TEXT_LENGTH),
      label: trigger.getAttribute('data-chat-label') || '',
      category: trigger.getAttribute('data-chat-category') || '',
      x: rect.left + rect.width / 2,
      y: rect.bottom + MENU_OFFSET_Y,
    };
  };

  const isNearRect = (rect: DOMRect | undefined, x: number, y: number) =>
    !!rect &&
    x >= rect.left - ZONE_PADDING &&
    x <= rect.right + ZONE_PADDING &&
    y >= rect.top - ZONE_PADDING &&
    y <= rect.bottom + ZONE_PADDING;

  /**
   * 以指针实际位置判断去留，而不是依赖 mouseout / mouseenter 的先后顺序：
   * 只要指针还在触发项或菜单附近就保留，真的移开了才收起。
   */
  const handleMousemove = (event: MouseEvent) => {
    if (!hoverMenu.value) return;
    const menuEl = (eventRoot as Document | ShadowRoot).querySelector?.(`.${MENU_CLASS}`);
    const inZone =
      isNearRect(activeTrigger?.getBoundingClientRect(), event.clientX, event.clientY) ||
      isNearRect(menuEl?.getBoundingClientRect(), event.clientX, event.clientY);
    if (inZone) {
      clearHideTimer();
      return;
    }
    scheduleHide();
  };

  const handleMenuEnter = () => {
    clearHideTimer();
  };

  const handleMenuLeave = () => {
    hideMenu();
  };

  const handleAddToChat = () => {
    const menu = hoverMenu.value;
    if (!menu) return;
    store.addChatContext({ text: menu.text, label: menu.label, category: menu.category });
    hideMenu();
  };

  const handleKeydown = (event: KeyboardEvent) => {
    if (event.key === 'Escape') hideMenu();
  };

  /** 容器所在根节点：微前端下是 shadow root，独立页是 document */
  let eventRoot: Document | ShadowRoot = document;

  onMounted(() => {
    eventRoot = (containerRef.value?.getRootNode() as Document | ShadowRoot) || document;
    eventRoot.addEventListener('mouseover', handleMouseover);
    eventRoot.addEventListener('mousemove', handleMousemove, { passive: true });
    eventRoot.addEventListener('keydown', handleKeydown);
    /** 指针移出面板后 shadow root 不再有 mousemove，靠这条 mouseleave 收尾；移进菜单会被菜单自己取消 */
    containerRef.value?.addEventListener('mouseleave', scheduleHide);
    containerRef.value?.addEventListener('scroll', hideMenu, { passive: true });
  });

  onBeforeUnmount(() => {
    clearHideTimer();
    eventRoot.removeEventListener('mouseover', handleMouseover);
    eventRoot.removeEventListener('mousemove', handleMousemove);
    eventRoot.removeEventListener('keydown', handleKeydown);
    containerRef.value?.removeEventListener('mouseleave', scheduleHide);
    containerRef.value?.removeEventListener('scroll', hideMenu);
  });

  return {
    hoverMenu,
    handleAddToChat,
    handleMenuEnter,
    handleMenuLeave,
  };
}
