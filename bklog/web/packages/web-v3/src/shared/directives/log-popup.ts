/**
 * 项目自定义指令的弹出层。
 * TDesign 只有 Popup 组件，没有可以挂在已有节点上的指令。
 * v-log-tooltip、v-log-overflow-tips 用 Popup 补这个模板写法。
 */
import { h, render, type DirectiveBinding } from 'vue';
import { Popup } from 'tdesign-vue-next';
import 'tdesign-vue-next/es/popup/style/index.css';

type Host = HTMLElement & {
  _logPopupId?: string;
  _logPopupRoot?: HTMLElement;
  _logPopupVisible?: boolean;
  _logPopupEnter?: () => void;
  _logPopupLeave?: () => void;
};

let sequence = 0;

const placementMap: Record<string, string> = {
  top: 'top',
  bottom: 'bottom',
  left: 'left',
  right: 'right',
  'top-start': 'top-left',
  'top-end': 'top-right',
  'bottom-start': 'bottom-left',
  'bottom-end': 'bottom-right',
  'left-start': 'left-top',
  'left-end': 'left-bottom',
  'right-start': 'right-top',
  'right-end': 'right-bottom',
};

export function popupContent(value: unknown): string {
  if (value == null || value === false) return '';
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  if (typeof value === 'object') {
    const record = value as { content?: unknown; disabled?: boolean };
    if (record.disabled) return '';
    if ('content' in record && record.content != null && record.content !== false) return String(record.content);
  }
  return '';
}

export function popupPlacement(binding: DirectiveBinding): string {
  const modifiers = binding.modifiers || {};
  const fromModifier = Object.keys(placementMap).find(name => modifiers[name]);
  const record = typeof binding.value === 'object' && binding.value ? (binding.value as { placement?: string; placements?: string[] }) : {};
  const raw = fromModifier || record.placement || record.placements?.[0] || 'top';
  return placementMap[raw] || 'top';
}

function delayOf(value: unknown, fallback: number | [number, number] = 0) {
  if (typeof value === 'object' && value && 'delay' in value) {
    const delay = (value as { delay?: number | [number, number] }).delay;
    return delay ?? fallback;
  }
  return fallback;
}

export function paintPopup(
  el: Host,
  binding: DirectiveBinding,
  visible: boolean,
  content: string,
  defaultDelay: number | [number, number] = 0,
) {
  if (!el._logPopupId) {
    el._logPopupId = `log-popup-${++sequence}`;
    el.setAttribute('data-log-popup', el._logPopupId);
  }
  if (!el._logPopupRoot) {
    el._logPopupRoot = document.createElement('div');
    document.body.appendChild(el._logPopupRoot);
  }
  el._logPopupVisible = visible && !!content;
  const vnode = h(Popup, {
    visible: el._logPopupVisible,
    content,
    placement: popupPlacement(binding) as 'top',
    triggerElement: `[data-log-popup="${el._logPopupId}"]`,
    showArrow: true,
    delay: delayOf(binding.value, defaultDelay),
    zIndex: window.__bk_zIndex_manager?.nextZIndex?.(),
  });
  vnode.appContext = binding.instance?.$?.appContext ?? null;
  render(vnode, el._logPopupRoot);
}

export function bindHoverPopup(el: Host, binding: DirectiveBinding, overflowOnly = false) {
  const enter = () => {
    if (overflowOnly && el.scrollWidth <= el.clientWidth && el.scrollHeight <= el.clientHeight) return;
    const content = popupContent(binding.value) || (overflowOnly ? el.textContent || '' : '');
    paintPopup(el, binding, true, content, overflowOnly ? [400, 0] : 0);
  };
  const leave = () => paintPopup(el, binding, false, '');
  el._logPopupEnter = enter;
  el._logPopupLeave = leave;
  el.addEventListener('mouseenter', enter);
  el.addEventListener('mouseleave', leave);
}

export function refreshHoverPopup(el: Host, binding: DirectiveBinding, overflowOnly = false) {
  if (!el._logPopupVisible) return;
  const content = popupContent(binding.value) || (overflowOnly ? el.textContent || '' : '');
  paintPopup(el, binding, !!content, content, overflowOnly ? [400, 0] : 0);
}

export function unbindHoverPopup(el: Host) {
  if (el._logPopupEnter) el.removeEventListener('mouseenter', el._logPopupEnter);
  if (el._logPopupLeave) el.removeEventListener('mouseleave', el._logPopupLeave);
  if (el._logPopupRoot) {
    render(null, el._logPopupRoot);
    el._logPopupRoot.remove();
  }
  el.removeAttribute('data-log-popup');
}
