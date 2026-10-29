import type { VNode } from 'vue';
import type { ButtonProps, DialogOptions, DialogInstance } from 'tdesign-vue-next';

export interface InfoInstance {
  id: string;
  name: string;
  close(): void;
  value?: boolean;
  loading?: boolean;
  buttonLoading?: boolean;
  $el?: Element;
}
type InfoCallback = (instance: InfoInstance) => unknown;
export interface InfoOptions {
  title?: string | VNode;
  header?: string | VNode;
  subHeader?: string | VNode;
  subTitle?: string | VNode;
  width?: number | string;
  type?: string;
  theme?: ButtonProps['theme'];
  showFooter?: boolean;
  closeIcon?: boolean;
  maskClose?: boolean;
  escClose?: boolean;
  okText?: string;
  cancelText?: string;
  zIndex?: number;
  extCls?: string;
  container?: Element | { $el: Element };
  icon?: string;
  confirmLoading?: boolean;
  confirmFn?: InfoCallback;
  cancelFn?: InfoCallback;
  closeFn?: InfoCallback;
  onClose?: InfoCallback;
  afterLeaveFn?: InfoCallback;
  stateChangeFn?: (visible: boolean) => void;
}
type InfoHandle = DialogInstance & { $el?: Element };
type OpenDialog = (props: DialogOptions, source: InfoOptions) => InfoHandle;

// Source contract: bk-magic-vue/lib/info-box.js Info(), Info.close() and handlers.
export function createInfoService(openDialog: OpenDialog, translate: (text: string) => string) {
  const instances = new Map<string, { instance: InfoInstance; close(callback?: InfoCallback): void }>();
  let sequence = 0;
  const info = (input: string | InfoOptions = {}) => {
    const options = typeof input === 'string' ? { title: input } : input;
    const id = `bkInfoBox${sequence++}`;
    let visible = true;
    let handle: InfoHandle;
    const instance: InfoInstance = { id, name: 'bk-info-box', close: () => close(options.onClose) };
    const close = (callback?: InfoCallback) => {
      if (!visible) return;
      visible = false;
      handle.hide();
      instances.delete(id);
      options.stateChangeFn?.(false);
      callback?.(instance);
    };
    Object.defineProperty(instance, 'value', {
      get: () => visible,
      set: value => (value ? handle.show() : close(options.onClose)),
    });
    Object.defineProperty(instance, 'buttonLoading', {
      get: () => instance.loading,
      set: value => {
        instance.loading = value;
        handle.setConfirmLoading(value);
      },
    });
    const asNode = (value: string | VNode | undefined): string | (() => VNode) | undefined => (typeof value === 'string' || value == null ? value : () => value);
    const width = options.width || 400;
    const container = options.container && ('$el' in options.container ? options.container.$el : options.container);
    const dialogOptions: DialogOptions = {
      width: typeof width === 'number' && width <= 100 ? `${width}%` : width,
      header: asNode(options.header ?? options.title) || false,
      body: asNode(options.subHeader ?? options.subTitle),
      theme:
        options.type === 'error'
          ? 'danger'
          : options.type === 'warning' || options.type === 'danger' || options.type === 'success'
            ? options.type
            : 'default',
      footer: options.showFooter !== false,
      closeBtn: options.closeIcon !== false,
      closeOnOverlayClick: options.maskClose === undefined ? true : options.maskClose,
      closeOnEscKeydown: options.escClose === undefined ? true : options.escClose,
      confirmBtn: { content: options.okText ?? translate('确定'), theme: options.theme || 'primary' },
      cancelBtn: options.cancelText ?? translate('取消'),
      zIndex: options.zIndex,
      dialogClassName: options.extCls,
      attach: container ? () => container : undefined,
      onConfirm: async () => {
        handle.update({ closeBtn: false });
        if (options.confirmLoading) instance.buttonLoading = true;
        try {
          const result = await options.confirmFn?.(instance);
          // V2 retains the dialog for false/0/null/empty; undefined means success.
          if (result === undefined || result) close();
          return result;
        } finally {
          handle.update({ closeBtn: options.closeIcon !== false });
          if (options.confirmLoading) instance.buttonLoading = false;
        }
      },
      onClose: context => {
        const callback = context.trigger === 'cancel' ? options.cancelFn : options.closeFn || options.cancelFn;
        callback?.(instance);
        close(options.onClose);
      },
      onClosed: () => {
        options.afterLeaveFn?.(instance);
        handle.destroy();
      },
    };
    handle = openDialog(dialogOptions, options);
    instance.$el = handle.$el;
    instances.set(id, { instance, close });
    options.stateChangeFn?.(true);
    return instance;
  };
  info.close = (id: string, callback?: InfoCallback) => instances.get(id)?.close(callback);
  return info;
}
