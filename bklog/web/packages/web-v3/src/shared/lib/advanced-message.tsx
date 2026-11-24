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

/**
 * bkui-vue Message 高级用法还原（V2 `bkMessage({ message: { code, overview, ... } })`）。
 *
 * 普通字符串消息仍走 TDesign MessagePlugin；仅当 message 为高级对象时走本实现，
 * 行为对齐 bkui-vue3 `packages/message`：
 * - 宽度 800px、无显式 delay 时默认展示 8000ms（普通消息 3000ms）；
 * - 顶部工具区固定顺序：助手 / 详情 / 图钉 / 关闭，支持 actions 合并与自定义；
 * - 详情支持 `json`（默认，格式化展示）与 `key-value` 两种格式，均可复制；
 * - 鼠标悬停暂停计时，Alt+P 切换图钉固定。
 */
import {
  createApp,
  defineComponent,
  isVNode,
  onMounted,
  onUnmounted,
  ref,
  type App,
  type PropType,
  type VNode,
} from 'vue';
import {
  ArrowDownIcon,
  ArrowUpIcon,
  ChatBubbleHelpFilledIcon,
  CheckCircleFilledIcon,
  CloseCircleFilledIcon,
  CloseIcon,
  CopyIcon,
  ErrorCircleFilledIcon,
  HelpCircleFilledIcon,
  PinFilledIcon,
  PinIcon,
} from 'tdesign-icons-vue-next';

import i18n from '@/platform/i18n/i18n';

import './advanced-message.scss';

export type AdvancedMessageTheme = 'primary' | 'info' | 'success' | 'warning' | 'error';

export interface AdvancedMessage {
  code?: number | string;
  overview?: string;
  suggestion?: string;
  details?: Array<Record<string, unknown> | boolean | number | string> | Record<string, unknown> | string;
  assistant?: string;
  type?: 'json' | 'key-value';
}

export interface AdvancedMessageAction {
  id: 'assistant' | 'close' | 'details' | 'fix' | string;
  text?: () => string | VNode | VNode[];
  icon?: () => VNode | VNode[] | string;
  onClick?: (event: MouseEvent, action: AdvancedMessageAction) => boolean | void;
  render?: () => VNode;
  disabled?: boolean;
  readonly?: boolean;
  classList?: string | string[];
}

export interface AdvancedMessageOptions {
  message: AdvancedMessage | VNode | string;
  theme?: AdvancedMessageTheme | string;
  /** bkui 兼容命名，毫秒；0 表示不自动关闭 */
  delay?: number;
  duration?: number;
  dismissable?: boolean;
  offsetY?: number;
  width?: number | string;
  actions?: AdvancedMessageAction[];
  onClose?: (id: string) => void;
  onDetail?: (shown: boolean, id: string) => void;
}

export function isAdvancedMessage(value: unknown): value is AdvancedMessage {
  if (!value || typeof value !== 'object' || isVNode(value as VNode) || Array.isArray(value)) {
    return false;
  }
  const target = value as Record<string, unknown>;
  return 'overview' in target || 'details' in target || 'suggestion' in target || 'code' in target;
}

const ADVANCED_WIDTH = 800;
const SINGLE_LINE_WIDTH = 560;
const ADVANCED_DELAY = 8000;
const SINGLE_LINE_DELAY = 3000;
const ACTION_ORDER = ['assistant', 'details', 'fix', 'close'];

let messageSeed = 0;
const activeContainers: HTMLElement[] = [];

function relayout(offsetY: number) {
  let top = offsetY;
  for (const container of activeContainers) {
    container.style.top = `${top}px`;
    top += container.offsetHeight + 10;
  }
}

function parseDetails(value: AdvancedMessage['details']) {
  if (typeof value === 'string') {
    try {
      return JSON.parse(value);
    } catch {
      return value;
    }
  }
  return value ?? {};
}

function stringifyDetails(value: AdvancedMessage['details']) {
  if (typeof value === 'string') return value;
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value ?? '');
  }
}

async function copyText(text: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.opacity = '0';
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand('copy');
  textarea.remove();
}

const AdvancedMessageToast = defineComponent({
  name: 'AdvancedMessageToast',
  props: {
    toastId: { type: String, required: true },
    message: { type: Object as PropType<AdvancedMessage>, required: true },
    theme: { type: String, default: 'primary' },
    delay: { type: Number, default: undefined },
    dismissable: { type: Boolean, default: true },
    width: { type: [Number, String], default: undefined },
    customActions: { type: Array as PropType<AdvancedMessageAction[]>, default: undefined },
    onClose: { type: Function as PropType<(id: string) => void>, default: undefined },
    onDetail: { type: Function as PropType<(shown: boolean, id: string) => void>, default: undefined },
    onDestroyed: { type: Function as PropType<() => void>, required: true },
  },
  setup(props) {
    const visible = ref(false);
    const isFixed = ref(false);
    const detailShown = ref(false);
    const copyStatus = ref<'success' | 'error' | ''>('');
    let timer: ReturnType<typeof setTimeout> | null = null;
    let copyTimer: ReturnType<typeof setTimeout> | null = null;

    const effectiveDelay = () => {
      if (typeof props.delay === 'number') return props.delay;
      return ADVANCED_DELAY;
    };

    const clearTimer = () => {
      if (timer) clearTimeout(timer);
      timer = null;
    };

    const close = () => {
      if (!visible.value) return;
      visible.value = false;
      clearTimer();
      props.onClose?.(props.toastId);
      // 与 bkui 一致：淡出后再销毁节点。
      setTimeout(() => props.onDestroyed(), 200);
    };

    const startTimer = () => {
      clearTimer();
      const delay = effectiveDelay();
      if (!delay || isFixed.value) return;
      timer = setTimeout(close, delay);
    };

    const toggleFix = () => {
      isFixed.value = !isFixed.value;
      if (isFixed.value) clearTimer();
      else startTimer();
    };

    const toggleDetails = () => {
      detailShown.value = !detailShown.value;
      props.onDetail?.(detailShown.value, props.toastId);
    };

    const showCopyStatus = (status: 'success' | 'error') => {
      copyStatus.value = status;
      if (copyTimer) clearTimeout(copyTimer);
      copyTimer = setTimeout(() => {
        copyStatus.value = '';
      }, 2000);
    };

    const copyDetails = async (text: string) => {
      try {
        await copyText(text);
        showCopyStatus('success');
      } catch {
        showCopyStatus('error');
      }
    };

    const handleKeydown = (event: KeyboardEvent) => {
      if (event.altKey && event.keyCode === 80) toggleFix();
    };

    onMounted(() => {
      visible.value = true;
      startTimer();
      document.addEventListener('keydown', handleKeydown);
    });

    onUnmounted(() => {
      clearTimer();
      if (copyTimer) clearTimeout(copyTimer);
      document.removeEventListener('keydown', handleKeydown);
    });

    const themeIcon = () => {
      const iconProps = { class: 'bk-message-icon-svg' };
      switch (props.theme) {
        case 'success':
          return <CheckCircleFilledIcon {...iconProps} />;
        case 'warning':
          return <ErrorCircleFilledIcon {...iconProps} />;
        case 'error':
          return <CloseCircleFilledIcon {...iconProps} />;
        default:
          return <HelpCircleFilledIcon {...iconProps} />;
      }
    };

    const defaultActions = (): Record<string, AdvancedMessageAction> => ({
      assistant: {
        id: 'assistant',
        icon: () => <ChatBubbleHelpFilledIcon />,
        text: () => i18n.t('bk.message.assistant'),
        onClick: () => {
          if (props.message.assistant) window.open(props.message.assistant, '_blank');
        },
      },
      details: {
        id: 'details',
        icon: () => (detailShown.value ? <ArrowUpIcon /> : <ArrowDownIcon />),
        text: () => i18n.t('bk.message.details'),
        onClick: () => toggleDetails(),
      },
      fix: {
        id: 'fix',
        classList: isFixed.value ? 'fixed' : '',
        icon: () => (isFixed.value ? <PinFilledIcon /> : <PinIcon />),
        onClick: () => toggleFix(),
      },
      close: {
        id: 'close',
        classList: 'normal-color',
        icon: () => (props.dismissable ? <CloseIcon class='bk-message-close' /> : <span />),
        onClick: () => close(),
      },
    });

    const actionList = () => {
      const defaults = defaultActions();
      if (!props.customActions?.length) {
        return ACTION_ORDER.map(id => defaults[id]);
      }
      const merged = props.customActions.map(action => {
        const id = String(action.id).toLocaleLowerCase();
        const fallback = defaults[id];
        const target: AdvancedMessageAction = { ...fallback, ...action, id };
        if (fallback && action.classList === undefined) target.classList = fallback.classList;
        if (typeof action.onClick === 'function' && fallback?.onClick) {
          const customClick = action.onClick;
          const defaultClick = fallback.onClick;
          target.onClick = (event: MouseEvent) => {
            const result = customClick(event, target);
            // 与 bkui 一致：自定义处理返回 false 时阻止默认行为。
            if (result !== false) defaultClick(event, target);
          };
        }
        return target;
      });
      const appended = ACTION_ORDER.filter(id => !merged.some(action => action.id === id)).map(id => defaults[id]);
      return [...merged, ...appended];
    };

    const renderActionContent = (action: AdvancedMessageAction) => {
      const icon = typeof action.icon === 'function' ? action.icon() : action.icon;
      const text = typeof action.text === 'function' ? action.text() : undefined;
      return (
        <>
          {icon}
          {typeof text === 'string' ? <span class='message-action-text'>{text}</span> : text}
        </>
      );
    };

    const renderDetails = () => {
      if (!detailShown.value) return null;
      const details = props.message.details;
      const isKeyValue = props.message.type === 'key-value';
      let body: VNode | VNode[];
      if (isKeyValue) {
        const target = parseDetails(details);
        const record: Record<string, unknown> =
          target && typeof target === 'object' ? (target as Record<string, unknown>) : { value: target };
        body = Object.keys(record).map(key => (
          <div
            class='message-row'
            key={key}
          >
            <label>{key}</label>
            <span
              class='copy-value'
              onClick={() => void copyDetails(String(record[key] ?? ''))}
            >
              {String(record[key] ?? '')}
            </span>
          </div>
        ));
      } else {
        const target = parseDetails(details);
        body = <pre class='message-json'>{typeof target === 'string' ? target : JSON.stringify(target, null, 2)}</pre>;
      }
      return (
        <div class='message-detail'>
          <div
            class='message-copy'
            onClick={() => void copyDetails(stringifyDetails(details))}
          >
            <CopyIcon />
          </div>
          {copyStatus.value && (
            <div class={['copy-status', copyStatus.value]}>
              {copyStatus.value === 'success' ? i18n.t('bk.message.copySuccess') : i18n.t('bk.message.copyFailed')}
            </div>
          )}
          <div class='message-tree'>{body}</div>
        </div>
      );
    };

    return () => {
      const width =
        props.width === undefined
          ? `${ADVANCED_WIDTH}px`
          : typeof props.width === 'number'
            ? `${props.width}px`
            : props.width;
      return (
        <div
          class={['bk-message', `bk-message-${props.theme === 'info' ? 'primary' : props.theme}`]}
          style={{ width, maxWidth: '100%', minWidth: '300px', display: visible.value ? undefined : 'none' }}
          onMouseenter={clearTimer}
          onMouseleave={startTimer}
        >
          <div class='bk-message-content multi'>
            <div class='overview'>
              <div class='left-content'>
                <div class='bk-message-icon'>{themeIcon()}</div>
                <div class='describe'>
                  {props.message.code ? `【${props.message.code}】` : ''}
                  {props.message.overview} {props.message.suggestion}
                </div>
              </div>
              <div class='tools'>
                {actionList().map(action => {
                  if (action.disabled) return null;
                  if (typeof action.render === 'function') return action.render();
                  const classList = Array.isArray(action.classList) ? action.classList.join(' ') : action.classList;
                  return (
                    <span
                      class={['tool', action.id, classList]}
                      onClick={(event: MouseEvent) => {
                        if (action.readonly || action.disabled) return;
                        action.onClick?.(event, action);
                      }}
                    >
                      {renderActionContent(action)}
                    </span>
                  );
                })}
              </div>
            </div>
            {renderDetails()}
          </div>
        </div>
      );
    };
  },
});

export function showAdvancedMessage(options: AdvancedMessageOptions) {
  messageSeed += 1;
  const toastId = `bklog-advanced-message-${messageSeed}`;
  const offsetY = options.offsetY ?? 30;
  const container = document.createElement('div');
  container.className = 'bklog-advanced-message-container';
  container.style.top = `${offsetY}px`;
  container.style.zIndex = `${(window as unknown as { __bk_zIndex_manager?: { nextMessageZIndex?: () => number } }).__bk_zIndex_manager?.nextMessageZIndex?.() ?? 9999}`;
  document.body.appendChild(container);
  activeContainers.push(container);
  relayout(offsetY);

  let app: App | null = null;
  const destroy = () => {
    app?.unmount();
    app = null;
    const index = activeContainers.indexOf(container);
    if (index >= 0) activeContainers.splice(index, 1);
    container.remove();
    relayout(offsetY);
  };

  const message = isAdvancedMessage(options.message) ? options.message : { overview: String(options.message ?? '') };
  app = createApp(AdvancedMessageToast, {
    toastId,
    message,
    theme: options.theme === 'info' || !options.theme ? 'primary' : options.theme,
    delay: options.delay ?? options.duration,
    dismissable: options.dismissable ?? true,
    width: options.width,
    customActions: options.actions,
    onClose: options.onClose,
    onDetail: options.onDetail,
    onDestroyed: destroy,
  });
  i18n.install(app);
  app.mount(container);
  requestAnimationFrame(() => relayout(offsetY));

  return {
    id: toastId,
    close: () => {
      // 通过销毁容器实现外部关闭；组件内部淡出仅用于自发关闭。
      destroy();
    },
  };
}

export { ADVANCED_DELAY, ADVANCED_WIDTH, SINGLE_LINE_DELAY, SINGLE_LINE_WIDTH };
