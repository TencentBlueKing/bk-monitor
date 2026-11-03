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

import { defineComponent, h, type App, type Component, type Directive } from 'vue';
import tippy, { type Instance as TippyInstance } from 'tippy.js';
import {
  Affix,
  Alert,
  BackTop,
  Badge,
  Breadcrumb,
  BreadcrumbItem,
  Button,
  Card,
  Cascader,
  Checkbox,
  CheckboxGroup,
  Col,
  Collapse,
  CollapsePanel,
  ColorPicker,
  DatePicker,
  Dialog,
  Divider,
  Drawer,
  Dropdown,
  Empty,
  Form,
  FormItem,
  Icon,
  Image,
  ImageViewer,
  Input,
  Link,
  Loading,
  Menu,
  MenuGroup,
  MenuItem,
  MessagePlugin,
  NotifyPlugin,
  Option,
  OptionGroup,
  Pagination,
  Popconfirm,
  Popup,
  Progress,
  Radio,
  RadioButton,
  RadioGroup,
  Rate,
  Row,
  Select,
  Slider,
  Statistic,
  Steps,
  Swiper,
  Switch,
  TabPanel,
  Table,
  Tabs,
  Tag,
  TagInput,
  TimePicker,
  Timeline,
  Transfer,
  Tree,
  Upload,
} from 'tdesign-vue-next';
import { bkLoadingDirective } from './loading';
import type { LegacyFormInstance } from '@/shared/types/legacy-form';

export type Form = LegacyFormInstance;
export type From = LegacyFormInstance;
export interface Popover {
  show(delay?: number): void;
  hide(delay?: number): void;
  destroy(): void;
  setContent(content: string | Element): void;
}

type RegisterHost = {
  component: (name: string, component: Component) => void;
  directive: (name: string, directive: Directive) => void;
};

function legacyControl(component: Component, ...names: string[]) {
  const source = component as Component & { install?: (host: RegisterHost) => void };
  const install = (host: RegisterHost) => {
    for (const name of names) host.component(name, source);
  };
  return new Proxy(source, {
    get(target, key, receiver) {
      if (key === 'install') return install;
      return Reflect.get(target, key, receiver);
    },
  });
}

function passthrough(name: string) {
  return legacyControl(
    defineComponent({
      name,
      setup(_, { attrs, slots }) {
        return () => h('div', attrs, slots.default?.());
      },
    }),
    name,
  );
}

function legacyDirective(directive: Directive, ...names: string[]) {
  return Object.assign(directive, {
    install(host: RegisterHost) {
      for (const name of names) host.directive(name, directive);
    },
  });
}

type TippyHost = HTMLElement & { _bkTippy?: TippyInstance };

function tooltipContent(value: unknown) {
  if (value == null || value === false) return '';
  if (typeof value === 'string' || typeof value === 'number') return String(value);
  if (typeof value === 'object' && 'content' in value) return String((value as { content?: unknown }).content ?? '');
  return '';
}

function tooltipPlacement(binding: { modifiers: Record<string, boolean>; value: unknown }) {
  if (binding.modifiers.top) return 'top' as const;
  if (binding.modifiers.bottom) return 'bottom' as const;
  if (binding.modifiers.left) return 'left' as const;
  if (binding.modifiers.right) return 'right' as const;
  const placement = typeof binding.value === 'object' && binding.value && 'placement' in binding.value
    ? (binding.value as { placement?: string }).placement
    : undefined;
  if (placement === 'bottom' || placement === 'left' || placement === 'right' || placement === 'top') return placement;
  return 'top' as const;
}

const tooltipDirective: Directive = {
  mounted(el, binding) {
    const content = tooltipContent(binding.value);
    if (!content) return;
    const host = el as TippyHost;
    const options = typeof binding.value === 'object' && binding.value ? (binding.value as { allowHtml?: boolean; delay?: number }) : {};
    host._bkTippy = tippy(host, {
      content,
      allowHTML: Boolean(options.allowHtml),
      placement: tooltipPlacement(binding),
      delay: options.delay ?? 0,
      zIndex: 9999,
    });
  },
  updated(el, binding) {
    const host = el as TippyHost;
    const content = tooltipContent(binding.value);
    if (!host._bkTippy) {
      if (content) {
        const options = typeof binding.value === 'object' && binding.value ? (binding.value as { allowHtml?: boolean; delay?: number }) : {};
        host._bkTippy = tippy(host, {
          content,
          allowHTML: Boolean(options.allowHtml),
          placement: tooltipPlacement(binding),
          delay: options.delay ?? 0,
          zIndex: 9999,
        });
      }
      return;
    }
    host._bkTippy.setContent(content);
    if (!content) host._bkTippy.disable();
    else host._bkTippy.enable();
  },
  unmounted(el) {
    (el as TippyHost)._bkTippy?.destroy();
  },
};

const overflowDefaults: { delay?: number | [number, number] } = {};

const overflowDirective: Directive = {
  mounted(el, binding) {
    const host = el as TippyHost;
    const show = () => {
      if (host.scrollWidth <= host.clientWidth && host.scrollHeight <= host.clientHeight) return;
      const content = tooltipContent(binding.value) || host.textContent || '';
      if (!content) return;
      host._bkTippy?.destroy();
      host._bkTippy = tippy(host, { content, placement: 'top', delay: overflowDefaults.delay ?? 0, zIndex: 9999 });
    };
    host.addEventListener('mouseenter', show);
  },
  unmounted(el) {
    (el as TippyHost)._bkTippy?.destroy();
  },
};

const clickoutsideDirective: Directive = {
  mounted(el, binding) {
    const host = el as HTMLElement & { _bkClickoutside?: (event: MouseEvent) => void };
    host._bkClickoutside = event => {
      if (event.target instanceof Node && !host.contains(event.target)) {
        const handler = binding.value;
        if (typeof handler === 'function') handler(event);
      }
    };
    document.addEventListener('mousedown', host._bkClickoutside);
  },
  unmounted(el) {
    const host = el as HTMLElement & { _bkClickoutside?: (event: MouseEvent) => void };
    if (host._bkClickoutside) document.removeEventListener('mousedown', host._bkClickoutside);
  },
};

type FeedbackTheme = 'info' | 'success' | 'warning' | 'error';

function feedbackTheme(theme: unknown): FeedbackTheme {
  if (theme === 'success' || theme === 'warning' || theme === 'error') return theme;
  return 'info';
}

function feedbackOptions(options: string | Record<string, unknown>) {
  const config = typeof options === 'string' ? { message: options } : options || {};
  return {
    theme: feedbackTheme(config.theme),
    content: (config.message ?? config.content ?? '') as string,
    title: config.title as string | undefined,
    duration: typeof config.delay === 'number' ? config.delay : 3000,
    zIndex: typeof config.zIndex === 'number' ? config.zIndex : 5000,
  };
}

export function bkMessage(options: string | Record<string, unknown> = {}) {
  const config = feedbackOptions(options);
  return MessagePlugin[config.theme]({ content: config.content, duration: config.duration, zIndex: config.zIndex });
}

export function bkNotify(options: string | Record<string, unknown> = {}) {
  const config = feedbackOptions(options);
  return NotifyPlugin[config.theme]({
    title: config.title,
    content: config.content,
    duration: config.duration,
    zIndex: config.zIndex,
  });
}

export const locale = {
  use(_next: unknown) {},
  i18n(_translator: (key: string, values?: unknown) => string) {},
};
export const lang = { enUS: {}, zhCN: {} };

export const bkAffix = legacyControl(Affix, 'bk-affix', 'BkAffix');
export const bkAlert = legacyControl(Alert, 'bk-alert', 'BkAlert');
export const bkAnimateNumber = legacyControl(Statistic, 'bk-animate-number', 'BkAnimateNumber');
export const bkBackTop = legacyControl(BackTop, 'bk-back-top', 'BkBackTop');
export const bkBadge = legacyControl(Badge, 'bk-badge', 'BkBadge');
export const bkBigTree = legacyControl(Tree, 'bk-big-tree', 'BkBigTree');
export const bkBreadcrumb = legacyControl(Breadcrumb, 'bk-breadcrumb', 'BkBreadcrumb');
export const bkBreadcrumbItem = legacyControl(BreadcrumbItem, 'bk-breadcrumb-item', 'BkBreadcrumbItem');
export const bkButton = legacyControl(Button, 'bk-button', 'BkButton');
export const bkCard = legacyControl(Card, 'bk-card', 'BkCard');
export const bkCascade = legacyControl(Cascader, 'bk-cascade', 'BkCascade');
export const bkCheckbox = legacyControl(Checkbox, 'bk-checkbox', 'BkCheckbox');
export const bkCheckboxGroup = legacyControl(CheckboxGroup, 'bk-checkbox-group', 'BkCheckboxGroup');
export const bkCol = legacyControl(Col, 'bk-col', 'BkCol');
export const bkCollapse = legacyControl(Collapse, 'bk-collapse', 'BkCollapse');
export const bkCollapseItem = legacyControl(CollapsePanel, 'bk-collapse-item', 'BkCollapseItem');
export const bkColorPicker = legacyControl(ColorPicker, 'bk-color-picker', 'BkColorPicker');
export const bkComposeFormItem = passthrough('bk-compose-form-item');
export const bkContainer = passthrough('bk-container');
export const bkDatePicker = legacyControl(DatePicker, 'bk-date-picker', 'BkDatePicker');
export const bkDialog = legacyControl(Dialog, 'bk-dialog', 'BkDialog');
export const bkDiff = passthrough('bk-diff');
export const bkDivider = legacyControl(Divider, 'bk-divider', 'BkDivider');
export const bkDropdownMenu = legacyControl(Dropdown, 'bk-dropdown-menu', 'BkDropdownMenu');
export const bkException = legacyControl(Empty, 'bk-exception', 'BkException');
export const bkFixedNavbar = legacyControl(Affix, 'bk-fixed-navbar', 'BkFixedNavbar');
export const bkForm = legacyControl(Form, 'bk-form', 'BkForm');
export const bkFormItem = legacyControl(FormItem, 'bk-form-item', 'BkFormItem');
export const bkIcon = legacyControl(Icon, 'bk-icon', 'BkIcon');
export const bkImage = legacyControl(Image, 'bk-image', 'BkImage');
export const bkImageViewer = legacyControl(ImageViewer, 'bk-image-viewer', 'BkImageViewer');
export const bkInput = legacyControl(Input, 'bk-input', 'BkInput');
export const bkLink = legacyControl(Link, 'bk-link', 'BkLink');
export const bkNavigation = legacyControl(Menu, 'bk-navigation', 'BkNavigation');
export const bkNavigationMenu = legacyControl(Menu, 'bk-navigation-menu', 'BkNavigationMenu');
export const bkNavigationMenuGroup = legacyControl(MenuGroup, 'bk-navigation-menu-group', 'BkNavigationMenuGroup');
export const bkNavigationMenuItem = legacyControl(MenuItem, 'bk-navigation-menu-item', 'BkNavigationMenuItem');
export const bkOption = legacyControl(Option, 'bk-option', 'BkOption');
export const bkOptionGroup = legacyControl(OptionGroup, 'bk-option-group', 'BkOptionGroup');
export const bkPagination = legacyControl(Pagination, 'bk-pagination', 'BkPagination');
export const bkPopconfirm = legacyControl(Popconfirm, 'bk-popconfirm', 'BkPopconfirm');
export const bkPopover = legacyControl(Popup, 'bk-popover', 'BkPopover');
export const bkProcess = legacyControl(Progress, 'bk-process', 'BkProcess');
export const bkProgress = legacyControl(Progress, 'bk-progress', 'BkProgress');
export const bkRadio = legacyControl(Radio, 'bk-radio', 'BkRadio');
export const bkRadioButton = legacyControl(RadioButton, 'bk-radio-button', 'BkRadioButton');
export const bkRadioGroup = legacyControl(RadioGroup, 'bk-radio-group', 'BkRadioGroup');
export const bkRate = legacyControl(Rate, 'bk-rate', 'BkRate');
export const bkResizeLayout = passthrough('bk-resize-layout');
export const bkRoundProgress = legacyControl(Progress, 'bk-round-progress', 'BkRoundProgress');
export const bkRow = legacyControl(Row, 'bk-row', 'BkRow');
export const bkSearchSelect = legacyControl(Select, 'bk-search-select', 'BkSearchSelect');
export const bkSelect = legacyControl(Select, 'bk-select', 'BkSelect');
export const bkSideslider = legacyControl(Drawer, 'bk-sideslider', 'BkSideslider');
export const bkSlider = legacyControl(Slider, 'bk-slider', 'BkSlider');
export const bkSpin = legacyControl(Loading, 'bk-spin', 'BkSpin');
export const bkStar = legacyControl(Rate, 'bk-star', 'BkStar');
export const bkSteps = legacyControl(Steps, 'bk-steps', 'BkSteps');
export const bkSwiper = legacyControl(Swiper, 'bk-swiper', 'BkSwiper');
export const bkSwitcher = legacyControl(Switch, 'bk-switcher', 'BkSwitcher');
export const bkTab = legacyControl(Tabs, 'bk-tab', 'BkTab');
export const bkTable = legacyControl(Table, 'bk-table', 'BkTable');
export const bkTableColumn = passthrough('bk-table-column');
export const bkTableSettingContent = passthrough('bk-table-setting-content');
export const bkTabPanel = legacyControl(TabPanel, 'bk-tab-panel', 'BkTabPanel');
export const bkTag = legacyControl(Tag, 'bk-tag', 'BkTag');
export const bkTagInput = legacyControl(TagInput, 'bk-tag-input', 'BkTagInput');
export const bkTimePicker = legacyControl(TimePicker, 'bk-time-picker', 'BkTimePicker');
export const bkTimeline = legacyControl(Timeline, 'bk-timeline', 'BkTimeline');
export const bkTransfer = legacyControl(Transfer, 'bk-transfer', 'BkTransfer');
export const bkTransition = legacyControl(
  defineComponent({
    name: 'bk-transition',
    setup(_, { slots }) {
      return () => slots.default?.();
    },
  }),
  'bk-transition',
  'BkTransition',
);
export const bkTree = legacyControl(Tree, 'bk-tree', 'BkTree');
export const bkUpload = legacyControl(Upload, 'bk-upload', 'BkUpload');
export const bkVersionDetail = passthrough('bk-version-detail');
export const bkVirtualRender = passthrough('bk-virtual-render');
export const bkVirtualScroll = passthrough('bk-virtual-scroll');
export const bkZoomImage = legacyControl(ImageViewer, 'bk-zoom-image', 'BkZoomImage');

const loadingService = Object.assign(
  (options: { opacity?: number; title?: string } = {}) => {
    let root = document.getElementById('bklog-service-loading');
    if (!root) {
      root = document.createElement('div');
      root.id = 'bklog-service-loading';
      document.body.appendChild(root);
    }
    root.style.cssText = `position:fixed;inset:0;z-index:10000;display:flex;align-items:center;justify-content:center;background:rgba(255,255,255,${options.opacity ?? 0.9})`;
    root.textContent = options.title || '';
  },
  {
    hide() {
      document.getElementById('bklog-service-loading')?.remove();
    },
  },
);

const loadingDirective = legacyDirective(bkLoadingDirective, 'bkloading', 'bk-loading');
const registerLoading = loadingDirective.install.bind(loadingDirective);
export const bkLoading = Object.assign(loadingDirective, {
  install(host: RegisterHost & { prototype?: Record<string, unknown>; config?: { globalProperties?: Record<string, unknown> } }) {
    registerLoading(host);
    if (host.prototype) host.prototype.$bkLoading = loadingService;
    if (host.config?.globalProperties) host.config.globalProperties.$bkLoading = loadingService;
  },
});
export const bkTooltips = legacyDirective(tooltipDirective, 'bk-tooltips', 'bkTooltips');
export const bkOverflowTips = Object.assign(legacyDirective(overflowDirective, 'bk-overflow-tips', 'bkOverflowTips'), {
  setDefaultProps(props: { delay?: number | [number, number] }) {
    Object.assign(overflowDefaults, props);
  },
});
export const bkClickoutside = legacyDirective(clickoutsideDirective, 'bk-clickoutside', 'bkClickoutside');
