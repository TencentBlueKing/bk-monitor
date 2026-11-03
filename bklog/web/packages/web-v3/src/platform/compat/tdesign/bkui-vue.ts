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

import tippy from 'tippy.js';
import { defineComponent, h, ref, Fragment, isVNode, type VNode, type Directive } from 'vue';
import {
  Button,
  Checkbox,
  Dialog,
  DialogPlugin,
  Empty,
  Form,
  FormItem,
  Input as TInput,
  Loading,
  MessagePlugin,
  Popconfirm,
  Popup,
  Select as TSelect,
  Option as TOption,
  OptionGroup as TOptionGroup,
  Tag as TTag,
  Tabs,
  TabPanel,
} from 'tdesign-vue-next';

export { Button, Checkbox, Dialog, Form, Loading };
export const Input = defineComponent({
  name: 'SdkInput',
  inheritAttrs: false,
  props: { prefix: String },
  setup(props, { attrs, slots, expose }) {
    const input = ref<{ focus(): void; blur(): void; inputRef?: HTMLInputElement }>();
    expose({
      focus: () => input.value?.focus(),
      blur: () => input.value?.blur(),
      get inputRef() {
        return input.value?.inputRef;
      },
    });
    return () =>
      h(
        TInput,
        { ...attrs, ref: input },
        {
          ...slots,
          prefixIcon: props.prefix ? () => h('span', props.prefix) : slots.prefixIcon,
        },
      );
  },
});
export const Exception = Empty;
export const PopConfirm = Popconfirm;
const popupPlacement = {
  'bottom-start': 'bottom-left',
  'bottom-end': 'bottom-right',
  'top-start': 'top-left',
  'top-end': 'top-right',
  'left-start': 'left-top',
  'left-end': 'left-bottom',
  'right-start': 'right-top',
  'right-end': 'right-bottom',
} as const;

export const Popover = defineComponent({
  name: 'SdkPopover',
  inheritAttrs: false,
  props: {
    arrow: { type: Boolean, default: false },
    extCls: { type: String, default: '' },
    isShow: { type: Boolean, default: false },
    offset: {
      type: Object as () => { mainAxis?: number; crossAxis?: number },
      default: () => ({}),
    },
    placement: { type: String, default: 'top' },
    trigger: { type: String, default: 'hover' },
    width: { type: [Number, String], default: undefined },
  },
  emits: ['clickoutside'],
  setup(props, { attrs, emit, slots }) {
    return () =>
      h(
        Popup,
        {
          ...attrs,
          overlayClassName: props.extCls,
          overlayInnerStyle:
            props.width === undefined || props.width === 'auto'
              ? undefined
              : { width: typeof props.width === 'number' ? `${props.width}px` : props.width },
          placement: popupPlacement[props.placement as keyof typeof popupPlacement] || props.placement,
          popperOptions: {
            modifiers: [
              {
                name: 'offset',
                options: {
                  offset: [props.offset.crossAxis || 0, props.offset.mainAxis || 0],
                },
              },
            ],
          },
          showArrow: props.arrow,
          trigger: props.trigger as 'hover',
          visible: props.isShow,
          onVisibleChange: (visible: boolean, context: { e?: Event; trigger?: string }) => {
            if (!visible && context.trigger === 'document') emit('clickoutside', { event: context.e });
          },
        },
        slots,
      );
  },
});
export const Tag = defineComponent({
  name: 'SdkTag',
  inheritAttrs: false,
  props: {
    closable: { type: [String, Boolean], default: false },
    disabled: { type: [String, Boolean], default: false },
  },
  emits: ['click', 'close'],
  setup(props, { attrs, emit, slots }) {
    return () =>
      h(
        TTag,
        {
          ...attrs,
          closable: props.closable === '' || props.closable === true,
          disabled: props.disabled === true,
          onClick: (context: { e: MouseEvent }) => emit('click', context),
          onClose: (context: { e: MouseEvent }) => emit('close', context),
        },
        slots,
      );
  },
});
/** Translate SDK child descriptors before TDesign inspects its slots. */
function sdkChildren(
  nodes: VNode[],
  source: object,
  target: object,
  props: (node: VNode) => Record<string, unknown>,
): VNode[] {
  return nodes.flatMap((node) => {
    if (Array.isArray(node)) return sdkChildren(node, source, target, props);
    if (!isVNode(node)) return [];
    if (node.type === Fragment && Array.isArray(node.children))
      return sdkChildren(node.children as VNode[], source, target, props);
    return node.type === source ? [h(target, props(node), node.children ?? undefined)] : [node];
  });
}
const SdkTabPanel = defineComponent({ name: 'SdkTabPanel', props: ['name', 'label'], setup: () => () => null });
export const Tab = Object.assign(
  defineComponent({
    name: 'SdkTab',
    inheritAttrs: false,
    props: { active: { type: [String, Number], default: undefined }, type: String },
    emits: ['update:active'],
    setup(props, { attrs, slots, emit }) {
      return () =>
        h(
          Tabs,
          {
            ...attrs,
            value: props.active,
            theme: props.type === 'unborder-card' ? 'normal' : 'card',
            onChange: (value) => emit('update:active', value),
          },
          {
            ...slots,
            default: () =>
              sdkChildren(slots.default?.() ?? [], SdkTabPanel, TabPanel, (node) => ({
                ...node.props,
                value: node.props?.name,
              })),
          },
        );
    },
  }),
  { TabPanel: SdkTabPanel },
);
const SdkOption = defineComponent({ name: 'SdkOption', props: ['id', 'name', 'disabled'], setup: () => () => null });
const SdkOptionGroup = defineComponent({ name: 'SdkOptionGroup', props: ['label'], setup: () => () => null });
function sdkOptions(nodes: VNode[], metadata: Map<unknown, Record<string, unknown>>): VNode[] {
  return nodes.flatMap((node) => {
    if (Array.isArray(node)) return sdkOptions(node, metadata);
    if (!isVNode(node)) return [];
    if (node.type === Fragment && Array.isArray(node.children)) return sdkOptions(node.children as VNode[], metadata);
    if (node.type === SdkOptionGroup) {
      const children = node.children as { default?: () => VNode[] } | null;
      return [h(TOptionGroup, { ...node.props }, { default: () => sdkOptions(children?.default?.() ?? [], metadata) })];
    }
    if (node.type === SdkOption) {
      metadata.set(node.props?.id, { ...node.props });
      return [
        h(TOption, { ...node.props, value: node.props?.id, label: node.props?.name }, node.children ?? undefined),
      ];
    }
    return [node];
  });
}
export const Select = Object.assign(
  defineComponent({
    name: 'SdkSelect',
    inheritAttrs: false,
    props: { popoverOptions: Object, popoverMinWidth: Number, prefix: String, filterOption: Function },
    setup(props, { attrs, slots, expose }) {
      const popupVisible = ref(false);
      const select = ref<{ $el?: HTMLElement }>();
      const datePickerPopup = ref(false);
      expose({
        hidePopover: () => {
          popupVisible.value = false;
        },
      });
      return () => {
        const metadata = new Map<unknown, Record<string, unknown>>();
        return h(
          TSelect,
          {
            ...attrs,
            ref: select,
            popupVisible: popupVisible.value,
            filter: props.filterOption
              ? (word, option) =>
                  props.filterOption?.(word, metadata.get('value' in option ? option.value : undefined) ?? option)
              : undefined,
            onPopupVisibleChange: (value) => {
              datePickerPopup.value = !!select.value?.$el?.closest('.__bk_date_picker__, .__bk-date-picker-popper__');
              popupVisible.value = value;
              if (typeof attrs.onToggle === 'function') attrs.onToggle(value);
            },
            popupProps: {
              zIndex: 10020,
              overlayClassName:
                [
                  datePickerPopup.value ? '__bk-date-picker-popper__' : '',
                  props.popoverOptions?.extCls ?? props.popoverOptions?.['ext-cls'],
                ]
                  .filter(Boolean)
                  .join(' ') || undefined,
              overlayInnerStyle: props.popoverMinWidth ? { minWidth: `${props.popoverMinWidth}px` } : undefined,
            },
          },
          {
            ...slots,
            prefixIcon: props.prefix ? () => h('span', props.prefix) : slots.prefixIcon,
            default: () => sdkOptions(slots.default?.() ?? [], metadata),
          },
        );
      };
    },
  }),
  { Option: SdkOption, Group: SdkOptionGroup },
);
export const BkFormItem = FormItem;
export const OverflowTitle = defineComponent({
  name: 'OverflowTitle',
  inheritAttrs: true,
  setup(_, { attrs, slots }) {
    return () => h('span', attrs, slots.default?.());
  },
});

type FeedbackTheme = 'info' | 'success' | 'warning' | 'error';
type FeedbackOptions =
  | string
  | { theme?: string; message?: unknown; content?: unknown; delay?: number; title?: string; subTitle?: string };

function themeOf(theme: unknown): FeedbackTheme {
  if (theme === 'success' || theme === 'warning' || theme === 'error') return theme;
  return 'info';
}

function contentOf(options: FeedbackOptions) {
  if (typeof options === 'string') return options;
  return String(options?.message ?? options?.content ?? options?.subTitle ?? '');
}

function notify(theme: FeedbackTheme, options: FeedbackOptions = {}) {
  const duration = typeof options === 'object' && typeof options.delay === 'number' ? options.delay : 3000;
  return MessagePlugin[theme]({ content: contentOf(options), duration });
}

export const Message = Object.assign(
  (options: FeedbackOptions = {}) => notify(themeOf(typeof options === 'object' ? options.theme : 'info'), options),
  {
    success: (options: FeedbackOptions = {}) => notify('success', options),
    warning: (options: FeedbackOptions = {}) => notify('warning', options),
    error: (options: FeedbackOptions = {}) => notify('error', options),
    info: (options: FeedbackOptions = {}) => notify('info', options),
  },
);

export function InfoBox(options: Exclude<FeedbackOptions, string> = {}) {
  return DialogPlugin.confirm({
    header: options.title || '',
    body: contentOf(options),
  });
}

export function $bkPopover(target: Element, options: { content?: string } = {}) {
  return tippy(target as Element, { content: options.content || '', placement: 'top' });
}

const clickoutsideDirective: Directive = {
  mounted(el, binding) {
    const host = el as HTMLElement & { _bkClickoutside?: (event: MouseEvent) => void };
    host._bkClickoutside = (event) => {
      if (event.target instanceof Node && !host.contains(event.target) && typeof binding.value === 'function')
        binding.value(event);
    };
    document.addEventListener('mousedown', host._bkClickoutside);
  },
  unmounted(el) {
    const host = el as HTMLElement & { _bkClickoutside?: (event: MouseEvent) => void };
    if (host._bkClickoutside) document.removeEventListener('mousedown', host._bkClickoutside);
  },
};

const tooltipDirective: Directive = {
  mounted(el, binding) {
    const content = typeof binding.value === 'string' ? binding.value : String(binding.value?.content ?? '');
    if (!content) return;
    (el as HTMLElement & { _bkTippy?: ReturnType<typeof tippy> })._bkTippy = tippy(el, { content, placement: 'top' });
  },
  unmounted(el) {
    (el as HTMLElement & { _bkTippy?: { destroy: () => void } })._bkTippy?.destroy();
  },
};

export const clickoutside = clickoutsideDirective;
export const bkTooltips = tooltipDirective;

export function provideGlobalConfig(_config?: { prefix?: string }) {}
