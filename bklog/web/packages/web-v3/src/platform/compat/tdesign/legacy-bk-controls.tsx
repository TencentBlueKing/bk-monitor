import {
  defineComponent,
  getCurrentInstance,
  h,
  ref,
  watch,
  type App,
  type VNode,
  type VNodeArrayChildren,
} from 'vue';
import {
  Alert,
  Button,
  Checkbox,
  CheckboxGroup,
  Collapse,
  CollapsePanel,
  DatePicker,
  Dialog,
  Drawer,
  Empty,
  Form,
  FormItem,
  Input,
  Pagination,
  Popconfirm,
  Popup,
  Radio,
  RadioGroup,
  Select,
  Slider,
  Steps,
  StepItem,
  Switch,
  TabPanel,
  Table,
  Tabs,
  TagInput,
  Textarea,
  TimePicker,
} from 'tdesign-vue-next';
import BkSearchSelect from '@/shared/ui/bk-search-select';
import { overlayRegistry } from '@/shared/global/overlay/overlay-registry.js';
import { Z_INDEX_LAYERS } from '@/shared/global/overlay/z-index-manager.js';

const mode3 = { compatConfig: { MODE: 3 } };

// bk-popover / tippy 的 *-center、*-start、*-end 不是 TDesign Popup 的 placement。
// 无法识别时 Popper 不计算位置，弹层会停在页面左上角。
const BK_POPOVER_PLACEMENT: Record<string, string> = {
  top: 'top',
  'top-start': 'top-left',
  'top-end': 'top-right',
  'top-left': 'top-left',
  'top-right': 'top-right',
  'top-center': 'top',
  bottom: 'bottom',
  'bottom-start': 'bottom-left',
  'bottom-end': 'bottom-right',
  'bottom-left': 'bottom-left',
  'bottom-right': 'bottom-right',
  'bottom-center': 'bottom',
  left: 'left',
  'left-start': 'left-top',
  'left-end': 'left-bottom',
  'left-top': 'left-top',
  'left-bottom': 'left-bottom',
  right: 'right',
  'right-start': 'right-top',
  'right-end': 'right-bottom',
  'right-top': 'right-top',
  'right-bottom': 'right-bottom',
  center: 'bottom',
};

function mapBkPopoverPlacement(placement: unknown) {
  const value = String(placement || 'top');
  return BK_POPOVER_PLACEMENT[value] || value;
}

function attr(props: Record<string, unknown> | null, ...keys: string[]) {
  if (!props) return undefined;
  for (const key of keys) {
    if (props[key] !== undefined) return props[key];
  }
  return undefined;
}

function flattenNodes(nodes: unknown): VNode[] {
  if (!nodes) return [];
  const list = Array.isArray(nodes) ? nodes : [nodes];
  const result: VNode[] = [];
  for (const node of list as VNode[]) {
    if (!node || typeof node !== 'object') continue;
    if (Array.isArray(node)) {
      result.push(...flattenNodes(node));
      continue;
    }
    const type = node.type as { name?: string } | symbol | string | undefined;
    if (typeof type === 'symbol' && Array.isArray(node.children)) {
      result.push(...flattenNodes(node.children));
      continue;
    }
    result.push(node);
  }
  return result;
}

function componentName(node: VNode) {
  const type = node.type as { name?: string } | string | undefined;
  if (typeof type === 'string') return type;
  return type && typeof type === 'object' ? type.name || '' : '';
}

function cellRenderer(node: VNode) {
  const children = node.children as { default?: (props: Record<string, unknown>) => unknown } | VNodeArrayChildren | null;
  const slot = children && !Array.isArray(children) ? children.default : undefined;
  if (typeof slot === 'function') {
    return (_h: unknown, context: { row: unknown; col: unknown; rowIndex: number }) =>
      slot({ row: context.row, column: context.col, $index: context.rowIndex, index: context.rowIndex });
  }
  const prop = attr(node.props, 'prop') as string | undefined;
  if (!prop) return undefined;
  return (_h: unknown, context: { row: Record<string, unknown> }) => {
    const value = prop.split('.').reduce<unknown>((current, key) => {
      if (current && typeof current === 'object') return (current as Record<string, unknown>)[key];
      return undefined;
    }, context.row);
    return value ?? '';
  };
}

const BkTableColumn = defineComponent({
  name: 'bk-table-column',
  ...mode3,
  setup() {
    return () => null;
  },
});

const BkTable = defineComponent({
  name: 'bk-table',
  ...mode3,
  inheritAttrs: false,
  props: {
    data: { type: Array, default: () => [] },
    pagination: { type: [Object, Boolean], default: undefined },
    limitList: { type: Array, default: undefined },
    size: { type: String, default: 'medium' },
    rowKey: { type: [String, Function], default: undefined },
    emptyText: { type: String, default: '' },
  },
  emits: ['page-change', 'page-limit-change', 'filter-change', 'row-click', 'sort-change', 'select', 'selection-change'],
  setup(props, { attrs, slots, emit, expose }) {
    const filterValue = ref<Record<string, unknown>>({});
    const table = ref<{ clearFilter?: () => void } | null>(null);
    expose({
      clearFilter() {
        filterValue.value = {};
        table.value?.clearFilter?.();
      },
    });
    return () => {
      const columns = flattenNodes(slots.default?.()).flatMap((node, index) => {
        if (!componentName(node).includes('table-column') && componentName(node) !== 'bk-table-column') return [];
        const propsOf = node.props || {};
        const type = attr(propsOf, 'type') as string | undefined;
        const key = String(attr(propsOf, 'columnKey', 'column-key', 'prop') || `col_${index}`);
        const label = attr(propsOf, 'label') as string | undefined;
        const width = attr(propsOf, 'width');
        const minWidth = attr(propsOf, 'minWidth', 'min-width');
        const filters = attr(propsOf, 'filters') as { text?: string; label?: string; value: unknown }[] | undefined;
        const multiple = attr(propsOf, 'filterMultiple', 'filter-multiple') !== false;
        const renderHeader = attr(propsOf, 'renderHeader') as ((...args: unknown[]) => unknown) | undefined;
        if (type === 'selection') {
          return [{ colKey: 'row-select', type: 'multiple', width: width || 50 }];
        }
        return [{
          colKey: key,
          title: renderHeader ? () => renderHeader(h, { column: { label } }) : label || '',
          width,
          minWidth,
          ellipsis: attr(propsOf, 'showOverflowTooltip', 'show-overflow-tooltip') !== undefined,
          className: attr(propsOf, 'className', 'class-name'),
          cell: cellRenderer(node),
          filter: filters
            ? {
                type: multiple ? 'multiple' : 'single',
                list: filters.map(item => ({ label: item.text ?? item.label ?? String(item.value), value: item.value })),
                showConfirmAndReset: true,
              }
            : undefined,
        }];
      });
      const pagination = props.pagination && typeof props.pagination === 'object'
        ? props.pagination as { current?: number; count?: number; limit?: number; limitList?: number[] }
        : undefined;
      return h(Table, {
        ...attrs,
        ref: table,
        data: props.data,
        columns,
        rowKey: props.rowKey || ((row: Record<string, unknown>) => String(
          row.repository_name || row.collector_config_id || row.template_id || row.id || row.cluster_id || JSON.stringify(row),
        )),
        size: props.size === 'mini' ? 'small' : props.size,
        hover: true,
        filterValue: filterValue.value,
        pagination: pagination
          ? {
              current: pagination.current || 1,
              pageSize: pagination.limit || 10,
              total: pagination.count || 0,
              pageSizeOptions: props.limitList || pagination.limitList || [10, 20, 50, 100],
            }
          : undefined,
        onPageChange: (pageInfo: { current: number; pageSize: number }) => {
          if (pagination && pageInfo.pageSize !== pagination.limit) emit('page-limit-change', pageInfo.pageSize);
          emit('page-change', pageInfo.current);
        },
        onFilterChange: (value: Record<string, unknown>) => {
          filterValue.value = value;
          const payload: Record<string, unknown[]> = {};
          for (const [key, item] of Object.entries(value)) {
            payload[key] = Array.isArray(item) ? item : item === undefined || item === null || item === '' ? [] : [item];
          }
          emit('filter-change', payload);
        },
        onRowClick: ({ row }: { row: unknown }) => emit('row-click', row),
        onSelectChange: (keys: unknown[]) => {
          emit('select', keys);
          emit('selection-change', keys);
        },
      }, { empty: slots.empty || (() => props.emptyText) });
    };
  },
});

function modelValue(props: { value?: unknown; modelValue?: unknown }) {
  return props.modelValue !== undefined ? props.modelValue : props.value;
}

const BkInput = defineComponent({
  name: 'bk-input',
  ...mode3,
  inheritAttrs: false,
  props: {
    value: { type: [String, Number], default: undefined },
    modelValue: { type: [String, Number], default: undefined },
    type: { type: String, default: 'text' },
    clearable: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
    readonly: { type: Boolean, default: false },
    placeholder: { type: String, default: '' },
    maxlength: { type: [String, Number], default: undefined },
    rightIcon: { type: String, default: '' },
    min: { type: [String, Number], default: undefined },
    max: { type: [String, Number], default: undefined },
  },
  emits: ['update:modelValue', 'input', 'change', 'enter', 'clear', 'blur', 'focus', 'right-icon-click'],
  setup(props, { attrs, slots, emit }) {
    const publish = (value: string | number) => {
      emit('update:modelValue', value);
      emit('input', value);
      emit('change', value);
    };
    return () => {
      const shared = {
        ...attrs,
        value: modelValue(props) ?? '',
        clearable: props.clearable,
        disabled: props.disabled,
        readonly: props.readonly,
        placeholder: props.placeholder,
        maxlength: props.maxlength,
        onChange: (value: string | number) => publish(value),
        onEnter: () => emit('enter', modelValue(props) ?? ''),
        onClear: () => {
          publish('');
          emit('clear');
        },
        onBlur: () => emit('blur'),
        onFocus: () => emit('focus'),
      };
      if (props.type === 'textarea') return h(Textarea, shared, slots);
      return h(Input, {
        ...shared,
        type: props.type === 'number' ? 'number' : 'text',
      }, {
        prefix: slots.prepend,
        suffix: () => [
          slots.append?.(),
          props.rightIcon
            ? h('i', { class: props.rightIcon, onClick: () => emit('right-icon-click') })
            : null,
        ],
      });
    };
  },
});

function optionNodes(nodes: VNode[]): { label: string; value: unknown }[] {
  return flattenNodes(nodes).flatMap(node => {
    const name = componentName(node);
    if (name.includes('option-group')) return optionNodes(flattenNodes(node.children));
    if (!name.includes('option')) return [];
    const props = node.props || {};
    const value = attr(props, 'id', 'value', 'key');
    const label = attr(props, 'name', 'label') ?? value;
    return [{ label: String(label ?? ''), value }];
  });
}

const BkOption = defineComponent({ name: 'bk-option', ...mode3, setup: () => () => null });
const BkOptionGroup = defineComponent({ name: 'bk-option-group', ...mode3, setup: () => () => null });

const BkSelect = defineComponent({
  name: 'bk-select',
  ...mode3,
  inheritAttrs: false,
  props: {
    value: { type: [String, Number, Array, Boolean], default: undefined },
    modelValue: { type: [String, Number, Array, Boolean], default: undefined },
    multiple: { type: Boolean, default: false },
    searchable: { type: Boolean, default: false },
    clearable: { type: Boolean, default: true },
    disabled: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
    placeholder: { type: String, default: '' },
    extPopoverCls: { type: String, default: '' },
  },
  emits: ['update:modelValue', 'change', 'input', 'toggle', 'clear', 'selected'],
  setup(props, { attrs, slots, emit }) {
    const publish = (value: unknown) => {
      emit('update:modelValue', value);
      emit('input', value);
      emit('change', value);
      emit('selected', value);
    };
    return () => h(Select, {
      ...attrs,
      value: modelValue(props),
      multiple: props.multiple,
      filterable: props.searchable,
      clearable: props.clearable,
      disabled: props.disabled,
      loading: props.loading,
      placeholder: props.placeholder,
      options: optionNodes(flattenNodes(slots.default?.())),
      popupProps: props.extPopoverCls ? { overlayClassName: props.extPopoverCls } : undefined,
      onChange: publish,
      onClear: () => emit('clear'),
      onPopupVisibleChange: (visible: boolean) => emit('toggle', visible),
    }, {
      panelBottomContent: slots.extension,
      empty: slots.empty,
    });
  },
});

const BkSteps = defineComponent({
  name: 'bk-steps',
  ...mode3,
  props: {
    curStep: { type: Number, default: 1 },
    steps: { type: Array, default: () => [] },
    controllable: { type: Boolean, default: false },
    beforeChange: { type: Function, default: undefined },
    extCls: { type: String, default: '' },
  },
  emits: ['update:curStep', 'change'],
  setup(props, { emit }) {
    return () => h(Steps, {
      class: props.extCls,
      current: props.curStep,
      readonly: !props.controllable,
      separator: 'line',
      onChange: async (current: string | number) => {
        const next = Number(current);
        const allowed = props.beforeChange ? await props.beforeChange(next) : true;
        if (allowed === false) return;
        emit('update:curStep', next);
        emit('change', next);
      },
    }, {
      default: () => (props.steps as { title?: string; icon?: number }[]).map(item => h(StepItem, {
        title: item.title,
        value: item.icon,
      })),
    });
  },
});

const BkForm = defineComponent({
  name: 'bk-form',
  ...mode3,
  inheritAttrs: false,
  props: {
    model: { type: Object, default: () => ({}) },
    rules: { type: Object, default: () => ({}) },
    labelWidth: { type: [String, Number], default: 100 },
  },
  setup(props, { attrs, slots, expose }) {
    const form = ref<{ validate: () => Promise<unknown>; clearValidate: () => void } | null>(null);
    expose({
      async validate(callback?: (valid: boolean) => unknown) {
        const result = await form.value?.validate();
        const valid = result === true;
        callback?.(valid);
        return valid ? true : Promise.reject(result);
      },
      clearError() {
        form.value?.clearValidate();
      },
    });
    return () => h(Form, {
      ...attrs,
      ref: form,
      data: props.model,
      rules: props.rules,
      labelWidth: props.labelWidth,
    }, slots);
  },
});

const BkFormItem = defineComponent({
  name: 'bk-form-item',
  ...mode3,
  inheritAttrs: false,
  props: {
    label: { type: String, default: '' },
    property: { type: String, default: '' },
    required: { type: Boolean, default: false },
  },
  setup(props, { attrs, slots }) {
    return () => h(FormItem, { ...attrs, label: props.label, name: props.property, requiredMark: props.required }, slots);
  },
});

function visibleProp(props: { value?: unknown; modelValue?: unknown; isShow?: boolean }) {
  if (props.isShow !== undefined) return props.isShow;
  return Boolean(modelValue(props));
}

const BkDialog = defineComponent({
  name: 'bk-dialog',
  ...mode3,
  inheritAttrs: false,
  props: {
    value: { type: Boolean, default: undefined },
    modelValue: { type: Boolean, default: undefined },
    isShow: { type: Boolean, default: undefined },
    title: { type: String, default: '' },
    width: { type: [String, Number], default: 480 },
    maskClose: { type: Boolean, default: true },
    fullscreen: { type: Boolean, default: false },
    showFooter: { type: Boolean, default: undefined },
    escClose: { type: Boolean, default: undefined },
    extCls: { type: String, default: '' },
    renderDirectives: { type: String, default: '' },
  },
  emits: ['update:modelValue', 'update:value', 'confirm', 'cancel', 'value-change', 'after-leave'],
  setup(props, { attrs, slots, emit }) {
    const close = (confirm: boolean) => {
      emit('update:modelValue', false);
      emit('update:value', false);
      emit('value-change', false);
      emit(confirm ? 'confirm' : 'cancel');
    };
    const dialogZIndex = ref(Z_INDEX_LAYERS.DIALOG);
    watch(
      () => visibleProp(props),
      (visible) => {
        if (visible) dialogZIndex.value = overlayRegistry.nextZIndex();
      },
      { immediate: true },
    );
    return () => {
      const fullscreen = props.fullscreen;
      const dialogClassName = [attrs.dialogClassName, props.extCls].filter(Boolean).join(' ');
      const footer = slots.footer
        ? undefined
        : props.showFooter === true
          ? undefined
          : false;
      return h(Dialog, {
        ...attrs,
        attach: attrs.attach ?? 'body',
        visible: visibleProp(props),
        header: slots.header ? undefined : (props.title || undefined),
        width: fullscreen ? '100%' : props.width,
        mode: fullscreen ? 'full-screen' : attrs.mode,
        closeOnOverlayClick: props.maskClose,
        closeOnEscKeydown: props.escClose !== false,
        // render-directives=if 不能映射成 destroyOnClose：TDesign 在 visible 一开始就是 true 时
        // 会走 Transition + v-show 的首次挂载，动画配置不含 fade 时弹层会停在 display:none。
        // 上下文/实时面板本身按 visible 条件渲染，关闭时内容仍会卸载。
        dialogClassName: dialogClassName || undefined,
        dialogStyle: fullscreen
          ? { width: '100%', height: '100%', maxWidth: '100%', maxHeight: '100%', ...(attrs.dialogStyle as object) }
          : attrs.dialogStyle,
        footer,
        zIndex: attrs.zIndex ?? dialogZIndex.value,
        onConfirm: () => close(true),
        onClose: () => close(false),
        onClosed: () => emit('after-leave'),
      }, { default: slots.default, header: slots.header, footer: slots.footer });
    };
  },
});

const RESIZE_LAYOUT_STYLE_ID = 'bklog-resize-layout-style';

function ensureResizeLayoutStyle() {
  if (typeof document === 'undefined' || document.getElementById(RESIZE_LAYOUT_STYLE_ID)) return;
  const style = document.createElement('style');
  style.id = RESIZE_LAYOUT_STYLE_ID;
  style.textContent = `
.bk-resize-layout{display:flex;width:100%;height:100%;min-height:0;overflow:hidden}
.bk-resize-layout.is-vertical{flex-direction:column}
.bk-resize-layout-main{flex:1 1 auto;min-width:0;min-height:0;overflow:hidden}
.bk-resize-layout-aside{position:relative;flex:none;min-width:0;min-height:0;overflow:hidden;background:#fff}
.bk-resize-layout-aside-content{width:100%;height:100%;min-height:0;overflow:auto}
.bk-resize-collapse{position:absolute;z-index: var(--bklog-z-local);background:#dcdee5}
.bk-resize-layout.is-bottom .bk-resize-collapse,.bk-resize-layout.is-top .bk-resize-collapse{left:0;right:0;height:4px;cursor:row-resize}
.bk-resize-layout.is-bottom .bk-resize-collapse{top:0}
.bk-resize-layout.is-top .bk-resize-collapse{bottom:0}
.bk-resize-layout.is-left .bk-resize-collapse,.bk-resize-layout.is-right .bk-resize-collapse{top:0;bottom:0;width:4px;cursor:col-resize}
.bk-resize-layout.is-left .bk-resize-collapse{right:0}
.bk-resize-layout.is-right .bk-resize-collapse{left:0}
`;
  document.head.appendChild(style);
}

/** bk-magic bk-resize-layout 的最小兼容：main/aside 插槽 + initial-divide 可跟随折叠更新 */
const BkResizeLayout = defineComponent({
  name: 'bk-resize-layout',
  ...mode3,
  inheritAttrs: false,
  props: {
    placement: { type: String, default: 'left' },
    initialDivide: { type: [Number, String], default: 240 },
    min: { type: Number, default: 3 },
    max: { type: Number, default: 0 },
    border: { type: Boolean, default: true },
  },
  setup(props, { attrs, slots }) {
    ensureResizeLayoutStyle();
    const size = ref(Number(props.initialDivide) || 0);
    watch(
      () => props.initialDivide,
      value => {
        const next = Number(value);
        if (!Number.isNaN(next)) size.value = next;
      },
    );

    const clamp = (value: number) => {
      const min = Number(props.min) || 0;
      const max = Number(props.max) || 0;
      let next = value;
      if (next < min) next = min;
      if (max && next > max) next = max;
      return next;
    };

    const onPointerDown = (event: PointerEvent) => {
      event.preventDefault();
      const vertical = props.placement === 'top' || props.placement === 'bottom';
      const start = vertical ? event.clientY : event.clientX;
      const startSize = size.value;
      const sign = props.placement === 'bottom' || props.placement === 'right' ? -1 : 1;
      const move = (ev: PointerEvent) => {
        const current = vertical ? ev.clientY : ev.clientX;
        size.value = clamp(startSize + sign * (current - start));
      };
      const up = () => {
        window.removeEventListener('pointermove', move);
        window.removeEventListener('pointerup', up);
      };
      window.addEventListener('pointermove', move);
      window.addEventListener('pointerup', up);
    };

    return () => {
      const vertical = props.placement === 'top' || props.placement === 'bottom';
      const asideFirst = props.placement === 'left' || props.placement === 'top';
      const asideStyle = vertical
        ? { height: `${size.value}px`, width: '100%' }
        : { width: `${size.value}px`, height: '100%' };
      const aside = h('div', { class: 'bk-resize-layout-aside', style: asideStyle }, [
        h('div', { class: 'bk-resize-collapse', onPointerdown: onPointerDown }),
        h('div', { class: 'bk-resize-layout-aside-content' }, slots.aside?.()),
      ]);
      const main = h('div', { class: 'bk-resize-layout-main' }, slots.main?.());
      return h('div', {
        ...attrs,
        class: [
          'bk-resize-layout',
          `is-${props.placement}`,
          vertical ? 'is-vertical' : 'is-horizontal',
          attrs.class,
        ],
      }, asideFirst ? [aside, main] : [main, aside]);
    };
  },
});

const BkSideslider = defineComponent({
  name: 'bk-sideslider',
  ...mode3,
  inheritAttrs: false,
  props: {
    isShow: { type: Boolean, default: false },
    title: { type: String, default: '' },
    width: { type: [String, Number], default: 640 },
    quickClose: { type: Boolean, default: true },
    transfer: { type: Boolean, default: true },
  },
  emits: ['update:isShow', 'animation-end', 'shown'],
  setup(props, { attrs, slots, emit }) {
    const close = () => {
      emit('update:isShow', false);
      emit('animation-end');
    };
    const drawerZIndex = ref(Z_INDEX_LAYERS.DRAWER);
    let drawerReady = false;
    watch(
      () => props.isShow,
      (visible) => {
        if (visible) drawerZIndex.value = overlayRegistry.nextZIndex();
        if (drawerReady && visible) emit('shown');
        drawerReady = true;
      },
      { immediate: true },
    );
    return () => {
      const attach = props.transfer === false ? attrs.attach : (attrs.attach ?? 'body');
      return h(Drawer, {
        ...attrs,
        attach,
        visible: props.isShow,
        header: props.title,
        size: typeof props.width === 'number' ? `${props.width}px` : props.width,
        closeOnOverlayClick: props.quickClose,
        footer: Boolean(slots.footer),
        zIndex: attrs.zIndex ?? drawerZIndex.value,
        onClose: close,
      }, {
        header: slots.header,
        body: () => props.isShow ? (slots.content || slots.default)?.() : null,
        footer: props.isShow ? slots.footer : undefined,
      });
    };
  },
});

const BkCollapse = defineComponent({
  name: 'bk-collapse',
  ...mode3,
  props: {
    value: { type: Array, default: () => [] },
    modelValue: { type: Array, default: undefined },
  },
  emits: ['update:modelValue', 'input', 'change'],
  setup(props, { slots, emit }) {
    return () => h(Collapse, {
      value: modelValue(props) || [],
      onChange: (value: unknown) => {
        emit('update:modelValue', value);
        emit('input', value);
        emit('change', value);
      },
    }, slots);
  },
});

const BkCollapseItem = defineComponent({
  name: 'bk-collapse-item',
  ...mode3,
  props: {
    name: { type: [String, Number], default: '' },
    title: { type: String, default: '' },
    hideArrow: { type: Boolean, default: false },
  },
  setup(props, { attrs, slots }) {
    return () => {
      // bk-magic：默认插槽是标题，content 插槽是面板内容。
      const header = slots.title || (slots.content ? slots.default : undefined);
      const body = slots.content || slots.default;
      return h(CollapsePanel, {
        ...attrs,
        value: props.name,
        header: header ? undefined : props.title,
        expandIcon: props.hideArrow ? false : undefined,
      }, {
        header,
        default: body,
      });
    };
  },
});

const BkButton = defineComponent({
  name: 'bk-button',
  ...mode3,
  inheritAttrs: false,
  props: {
    theme: { type: String, default: 'default' },
    disabled: { type: Boolean, default: false },
    loading: { type: Boolean, default: false },
    title: { type: String, default: '' },
  },
  emits: ['click'],
  setup(props, { attrs, slots, emit }) {
    return () => h(Button, {
      ...attrs,
      theme: props.theme === 'primary' ? 'primary' : props.theme === 'danger' || props.theme === 'warning' ? 'danger' : 'default',
      disabled: props.disabled,
      loading: props.loading,
      title: props.title,
      onClick: (event: MouseEvent) => emit('click', event),
    }, slots);
  },
});

const BkCheckbox = defineComponent({
  name: 'bk-checkbox',
  ...mode3,
  props: {
    value: { type: [Boolean, String, Number], default: undefined },
    modelValue: { type: [Boolean, String, Number], default: undefined },
    checked: { type: Boolean, default: undefined },
    disabled: { type: Boolean, default: false },
    trueValue: { type: [Boolean, String, Number], default: true },
    falseValue: { type: [Boolean, String, Number], default: false },
  },
  emits: ['update:modelValue', 'change', 'input'],
  setup(props, { attrs, slots, emit }) {
    const current = props.checked !== undefined ? props.checked : modelValue(props);
    return () => h(Checkbox, {
      ...attrs,
      checked: current === props.trueValue || current === true,
      disabled: props.disabled,
      onChange: (checked: boolean) => {
        const value = checked ? props.trueValue : props.falseValue;
        emit('update:modelValue', value);
        emit('input', value);
        emit('change', value);
      },
    }, slots);
  },
});

const BkSwitch = defineComponent({
  name: 'bk-switch',
  ...mode3,
  props: {
    value: { type: Boolean, default: undefined },
    modelValue: { type: Boolean, default: undefined },
    disabled: { type: Boolean, default: false },
  },
  emits: ['update:modelValue', 'change', 'input'],
  setup(props, { attrs, emit }) {
    return () => h(Switch, {
      ...attrs,
      value: Boolean(modelValue(props)),
      disabled: props.disabled,
      onChange: (value: boolean) => {
        emit('update:modelValue', value);
        emit('input', value);
        emit('change', value);
      },
    });
  },
});

const BkTagInput = defineComponent({
  name: 'bk-tag-input',
  ...mode3,
  props: {
    value: { type: Array, default: () => [] },
    modelValue: { type: Array, default: undefined },
    placeholder: { type: String, default: '' },
    disabled: { type: Boolean, default: false },
  },
  emits: ['update:modelValue', 'change', 'input', 'blur'],
  setup(props, { attrs, emit }) {
    return () => h(TagInput, {
      ...attrs,
      value: (modelValue(props) as string[]) || [],
      placeholder: props.placeholder,
      disabled: props.disabled,
      clearable: true,
      onChange: (value: string[]) => {
        emit('update:modelValue', value);
        emit('input', value);
        emit('change', value);
      },
      onBlur: () => emit('blur'),
    });
  },
});

const BkPopover = defineComponent({
  name: 'bk-popover',
  ...mode3,
  props: {
    content: { type: String, default: '' },
    placement: { type: String, default: 'top' },
    disabled: { type: Boolean, default: false },
  },
  setup(props, { attrs, slots }) {
    return () => {
      const distance = Number(attrs.distance ?? 8);
      const skidding = Number(attrs.offset ?? 0);
      const show = attrs.onShow || attrs['on-show'];
      const hide = attrs.onHide || attrs['on-hide'];
      const {
        distance: _distance,
        offset: _offset,
        theme,
        animation: _animation,
        onShow: _onShow,
        onHide: _onHide,
        'on-show': _onShowKebab,
        'on-hide': _onHideKebab,
        ...rest
      } = attrs;
      return h(Popup, {
        ...rest,
        content: props.content || slots.content,
        placement: mapBkPopoverPlacement(props.placement),
        disabled: props.disabled,
        showArrow: rest.showArrow ?? rest['show-arrow'] ?? true,
        overlayClassName: [theme, rest.overlayClassName].filter(Boolean).flat(),
        popperOptions: {
          ...(typeof rest.popperOptions === 'object' && rest.popperOptions ? rest.popperOptions : {}),
          modifiers: [
            { name: 'offset', options: { offset: [Number.isFinite(skidding) ? skidding : 0, Number.isFinite(distance) ? distance : 8] } },
          ],
        },
        onVisibleChange: (visible: boolean, context: unknown) => {
          if (visible) show?.(visible);
          else hide?.(visible);
          rest.onVisibleChange?.(visible, context);
        },
      }, { default: slots.default });
    };
  },
});

const BkAlert = defineComponent({
  name: 'bk-alert',
  ...mode3,
  props: {
    type: { type: String, default: 'info' },
    title: { type: String, default: '' },
    closable: { type: Boolean, default: false },
  },
  setup(props, { slots }) {
    const theme = props.type === 'error' ? 'error' : props.type === 'warning' ? 'warning' : props.type === 'success' ? 'success' : 'info';
    return () => h(Alert, { theme, title: props.title, close: props.closable }, slots);
  },
});

// bk-exception 的 scene 是插图尺寸（part / page），type 是插图类型。
// 不能把 scene 传给 TDesign Empty 的 description，否则无数据时会多出 "part" 文本。
const BK_EXCEPTION_TYPE: Record<string, 'empty' | 'fail' | 'maintenance' | 'network-error'> = {
  empty: 'empty',
  'search-empty': 'empty',
  login: 'empty',
  403: 'fail',
  404: 'fail',
  500: 'fail',
  503: 'maintenance',
  building: 'maintenance',
};

const BK_EXCEPTION_TEXT: Record<string, string> = {
  empty: '暂无数据',
  'search-empty': '搜索无结果',
  login: '请先登录',
  403: '无业务权限',
  404: '页面不存在',
  500: '服务异常',
  503: '服务异常',
  building: '建设中',
};

const BkException = defineComponent({
  name: 'bk-exception',
  inheritAttrs: false,
  ...mode3,
  props: {
    type: { type: String, default: 'empty' },
    scene: { type: String, default: '' },
  },
  setup(props, { attrs, slots }) {
    const instance = getCurrentInstance();
    const translate = (text: string) => {
      const t = instance?.proxy?.$t;
      return typeof t === 'function' ? t(text) : text;
    };
    return () => {
      const content = slots.default?.();
      const hasContent = Array.isArray(content) ? content.some(node => node != null && node !== '') : content != null;
      const scene = props.scene === 'page' ? 'page' : 'part';
      // 标题插槽有内容时，TDesign 不再回退到类型默认文案「暂无数据」。
      const title = hasContent
        ? h('div', { class: ['bk-exception-text', `${scene}-text`] }, content)
        : translate(BK_EXCEPTION_TEXT[props.type] || BK_EXCEPTION_TEXT.empty);
      return h(
        Empty,
        {
          ...attrs,
          class: ['bk-exception', `bk-exception-${scene}`, attrs.class],
          type: BK_EXCEPTION_TYPE[props.type] || 'empty',
          size: scene === 'page' ? 'large' : 'medium',
        },
        { title: () => title },
      );
    };
  },
});

const BkSlider = defineComponent({
  name: 'bk-slider',
  ...mode3,
  props: {
    value: { type: Number, default: undefined },
    modelValue: { type: Number, default: undefined },
    maxValue: { type: Number, default: 100 },
    minValue: { type: Number, default: 0 },
    step: { type: Number, default: 1 },
    disabled: { type: Boolean, default: false },
  },
  emits: ['update:modelValue', 'change', 'input'],
  setup(props, { attrs, slots, emit }) {
    return () =>
      h(
        'div',
        { ...attrs, style: [{ display: 'flex', alignItems: 'center', width: '100%' }, attrs.style] },
        [
          slots.start?.(),
          h(Slider, {
            value: Number(modelValue(props) ?? props.minValue),
            max: props.maxValue,
            min: props.minValue,
            step: props.step,
            disabled: props.disabled,
            style: { flex: 1 },
            onChange: (value: number | number[]) => {
              const next = Array.isArray(value) ? value[0] : value;
              emit('update:modelValue', next);
              emit('input', next);
              emit('change', next);
            },
          }),
          slots.end?.(),
        ],
      );
  },
});

const BkDropdownMenu = defineComponent({
  name: 'bk-dropdown-menu',
  ...mode3,
  props: {
    trigger: { type: String, default: 'hover' },
    align: { type: String, default: 'left' },
    disabled: { type: Boolean, default: false },
  },
  setup(props, { attrs, slots }) {
    const placement = props.align === 'right' ? 'bottom-right' : 'bottom-left';
    return () =>
      h(
        Popup,
        {
          ...attrs,
          trigger: props.trigger === 'click' ? 'click' : 'hover',
          placement,
          disabled: props.disabled,
          content: () => slots['dropdown-content']?.(),
        },
        { default: () => slots['dropdown-trigger']?.() || slots.default?.() },
      );
  },
});

const BkPopconfirm = defineComponent({
  name: 'bk-popconfirm',
  ...mode3,
  props: {
    title: { type: String, default: '' },
    content: { type: String, default: '' },
    confirmText: { type: String, default: '确定' },
    cancelText: { type: String, default: '取消' },
    placement: { type: String, default: 'top' },
    trigger: { type: String, default: 'click' },
  },
  emits: ['confirm', 'cancel'],
  setup(props, { attrs, slots, emit }) {
    return () =>
      h(
        Popconfirm,
        {
          ...attrs,
          content: props.title || props.content,
          confirmBtn: props.confirmText,
          cancelBtn: props.cancelText,
          placement: props.placement,
          trigger: props.trigger,
          onConfirm: () => emit('confirm'),
          onCancel: () => emit('cancel'),
        },
        slots,
      );
  },
});

const BkPagination = defineComponent({
  name: 'bk-pagination',
  ...mode3,
  props: {
    count: { type: Number, default: 0 },
    current: { type: Number, default: 1 },
    limit: { type: Number, default: 10 },
    limitList: { type: Array, default: () => [10, 20, 50, 100] },
    size: { type: String, default: 'small' },
    small: { type: Boolean, default: false },
  },
  emits: ['change', 'limit-change'],
  setup(props, { attrs, emit }) {
    return () =>
      h(Pagination, {
        ...attrs,
        total: props.count,
        current: props.current,
        pageSize: props.limit,
        pageSizeOptions: props.limitList as number[],
        size: props.small || props.size === 'small' ? 'small' : 'medium',
        onCurrentChange: (page: number) => emit('change', page),
        onPageSizeChange: (size: number) => emit('limit-change', size),
      });
  },
});

const BkDatePicker = defineComponent({
  name: 'bk-date-picker',
  ...mode3,
  props: {
    value: { type: [String, Number, Date, Array], default: undefined },
    modelValue: { type: [String, Number, Date, Array], default: undefined },
    type: { type: String, default: 'date' },
    placeholder: { type: String, default: '' },
    clearable: { type: Boolean, default: true },
    disabled: { type: Boolean, default: false },
  },
  emits: ['update:modelValue', 'change', 'input'],
  setup(props, { attrs, emit }) {
    return () =>
      h(DatePicker, {
        ...attrs,
        value: modelValue(props) as string,
        enableTimePicker: props.type === 'datetime',
        placeholder: props.placeholder,
        clearable: props.clearable,
        disabled: props.disabled,
        onChange: (value: unknown) => {
          emit('update:modelValue', value);
          emit('input', value);
          emit('change', value);
        },
      });
  },
});

const BkTimePicker = defineComponent({
  name: 'bk-time-picker',
  ...mode3,
  props: {
    value: { type: String, default: undefined },
    modelValue: { type: String, default: undefined },
    placeholder: { type: String, default: '' },
    clearable: { type: Boolean, default: true },
    disabled: { type: Boolean, default: false },
  },
  emits: ['update:modelValue', 'change', 'input'],
  setup(props, { attrs, emit }) {
    return () =>
      h(TimePicker, {
        ...attrs,
        value: (modelValue(props) as string) || '',
        placeholder: props.placeholder,
        clearable: props.clearable,
        disabled: props.disabled,
        onChange: (value: string) => {
          emit('update:modelValue', value);
          emit('input', value);
          emit('change', value);
        },
      });
  },
});

const BkTabPanel = defineComponent({
  name: 'bk-tab-panel',
  ...mode3,
  setup() {
    return () => null;
  },
});

const BkTab = defineComponent({
  name: 'bk-tab',
  ...mode3,
  props: {
    active: { type: [String, Number], default: undefined },
    type: { type: String, default: 'normal' },
  },
  emits: ['update:active', 'tab-change', 'tabChange'],
  setup(props, { attrs, slots, emit }) {
    return () => {
      const children = flattenNodes(slots.default?.());
      const panels = children.filter(node => componentName(node) === 'bk-tab-panel');
      const rest = children.filter(node => componentName(node) !== 'bk-tab-panel');
      return h('div', attrs, [
        h(
          Tabs,
          {
            value: props.active,
            theme: props.type === 'card' ? 'card' : 'normal',
            onChange: (value: string | number) => {
              emit('update:active', value);
              emit('tab-change', value);
              emit('tabChange', value);
            },
          },
          () =>
            panels.map(panel => {
              const value = attr(panel.props, 'name') as string | number;
              const labelText = attr(panel.props, 'label') as string;
              const panelSlots = panel.children as { label?: () => unknown; default?: () => unknown } | null;
              return h(
                TabPanel,
                { key: String(value), value, label: panelSlots?.label ? undefined : labelText },
                {
                  label: panelSlots?.label,
                  default: panelSlots?.default,
                },
              );
            }),
        ),
        ...rest,
      ]);
    };
  },
});

const passthrough = (name: string, component: unknown) => defineComponent({
  name,
  ...mode3,
  inheritAttrs: false,
  setup(_, { attrs, slots }) {
    return () => h(component as never, attrs, slots);
  },
});

export function installLegacyBkControls(app: App) {
  const controls: Record<string, unknown> = {
    'bk-table': BkTable,
    'bk-table-column': BkTableColumn,
    'bk-input': BkInput,
    'bk-select': BkSelect,
    'bk-option': BkOption,
    'bk-option-group': BkOptionGroup,
    'bk-steps': BkSteps,
    'bk-form': BkForm,
    'bk-form-item': BkFormItem,
    'bk-dialog': BkDialog,
    'bk-resize-layout': BkResizeLayout,
    'bk-sideslider': BkSideslider,
    'bk-collapse': BkCollapse,
    'bk-collapse-item': BkCollapseItem,
    'bk-button': BkButton,
    'bk-checkbox': BkCheckbox,
    'bk-checkbox-group': passthrough('bk-checkbox-group', CheckboxGroup),
    'bk-radio': passthrough('bk-radio', Radio),
    'bk-radio-group': passthrough('bk-radio-group', RadioGroup),
    'bk-switch': BkSwitch,
    'bk-switcher': BkSwitch,
    'bk-slider': BkSlider,
    'bk-dropdown-menu': BkDropdownMenu,
    'bk-popconfirm': BkPopconfirm,
    'bk-pagination': BkPagination,
    'bk-date-picker': BkDatePicker,
    'bk-time-picker': BkTimePicker,
    'bk-tab': BkTab,
    'bk-tab-panel': BkTabPanel,
    'bk-tag-input': BkTagInput,
    'bk-search-select': BkSearchSelect,
    'bk-popover': BkPopover,
    'bk-alert': BkAlert,
    'bk-exception': BkException,
  };
  for (const [name, component] of Object.entries(controls)) app.component(name, component);
}
