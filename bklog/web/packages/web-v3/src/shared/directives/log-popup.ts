/**
 * 项目自定义指令的弹出层。
 * TDesign 只有 Popup 组件，没有可以挂在已有节点上的指令。
 * v-log-tooltip、v-log-overflow-tips 用 Popup 补这个模板写法。
 */
import { h, render, type DirectiveBinding } from 'vue';
import { Popup } from 'tdesign-vue-next';
import 'tdesign-vue-next/es/popup/style/index.css';

type Host = HTMLElement & {
  _logPopupBinding?: DirectiveBinding;
  _logPopupId?: string;
  _logPopupRoot?: HTMLElement;
  _logPopupTimer?: ReturnType<typeof setTimeout>;
  _logPopupEnter?: () => void;
  _logPopupLeave?: () => void;
};

let sequence = 0;
let activeHost: Host | undefined;

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

function closeActivePopup() {
  if (activeHost) closePopup(activeHost);
}

function closePopup(el: Host) {
  clearTimeout(el._logPopupTimer);
  delete el._logPopupTimer;
  if (el._logPopupRoot) {
    render(null, el._logPopupRoot);
    el._logPopupRoot.remove();
    delete el._logPopupRoot;
  }
  if (activeHost === el) {
    activeHost = undefined;
    el.ownerDocument.removeEventListener('scroll', closeActivePopup, true);
    el.ownerDocument.defaultView?.removeEventListener('blur', closeActivePopup);
  }
}

function paintPopup(el: Host, binding: DirectiveBinding, content: string) {
  if (!el._logPopupId) {
    el._logPopupId = `log-popup-${++sequence}`;
    el.setAttribute('data-log-popup', el._logPopupId);
  }
  if (!el._logPopupRoot) {
    el._logPopupRoot = el.ownerDocument.createElement('div');
    el.ownerDocument.body.appendChild(el._logPopupRoot);
  }
  const vnode = h(Popup, {
    visible: true,
    content,
    placement: popupPlacement(binding) as 'top',
    triggerElement: `[data-log-popup="${el._logPopupId}"]`,
    showArrow: true,
    overlayClassName: 'bklog-text-tooltip',
    delay: 0,
    zIndex: window.__bk_zIndex_manager?.nextZIndex?.(),
  });
  vnode.appContext = binding.instance?.$?.appContext ?? null;
  render(vnode, el._logPopupRoot);
}

export function bindHoverPopup(el: Host, binding: DirectiveBinding, overflowOnly = false) {
  el._logPopupBinding = binding;
  const enter = () => {
    if (activeHost) closePopup(activeHost);
    const binding = el._logPopupBinding;
    if (!binding || !hoverContent(el, binding, overflowOnly)) return;
    activeHost = el;
    el.ownerDocument.addEventListener('scroll', closeActivePopup, { capture: true, passive: true });
    el.ownerDocument.defaultView?.addEventListener('blur', closeActivePopup);
    const delay = delayOf(binding.value, overflowOnly ? 400 : 0);
    const show = () => {
      delete el._logPopupTimer;
      const current = el._logPopupBinding;
      if (!current || !el.isConnected) {
        closePopup(el);
        return;
      }
      const content = hoverContent(el, current, overflowOnly);
      if (content) paintPopup(el, current, content);
      else closePopup(el);
    };
    const wait = Array.isArray(delay) ? delay[0] : delay;
    if (wait > 0) el._logPopupTimer = setTimeout(show, wait);
    else show();
  };
  const leave = () => closePopup(el);
  el._logPopupEnter = enter;
  el._logPopupLeave = leave;
  el.addEventListener('mouseenter', enter);
  el.addEventListener('mouseleave', leave);
}

function hoverContent(el: Host, binding: DirectiveBinding, overflowOnly: boolean) {
  const options = binding.value as { disabled?: boolean; checkChildOverflow?: boolean } | null;
  if (options?.disabled) return '';
  if (overflowOnly && el.scrollWidth <= el.clientWidth && el.scrollHeight <= el.clientHeight) {
    const childOverflows = options?.checkChildOverflow && Array.from(el.children).some(
      child => child.scrollWidth > child.clientWidth || child.scrollHeight > child.clientHeight,
    );
    if (!childOverflows) return '';
  }
  return popupContent(binding.value) || (overflowOnly ? el.textContent || '' : '');
}

export function refreshHoverPopup(el: Host, binding: DirectiveBinding, overflowOnly = false) {
  el._logPopupBinding = binding;
  if (activeHost !== el) return;
  const content = hoverContent(el, binding, overflowOnly);
  if (!content) closePopup(el);
  else if (el._logPopupRoot) paintPopup(el, binding, content);
}

export function unbindHoverPopup(el: Host) {
  delete el._logPopupBinding;
  if (el._logPopupEnter) el.removeEventListener('mouseenter', el._logPopupEnter);
  if (el._logPopupLeave) el.removeEventListener('mouseleave', el._logPopupLeave);
  closePopup(el);
  el.removeAttribute('data-log-popup');
  delete el._logPopupId;
}
