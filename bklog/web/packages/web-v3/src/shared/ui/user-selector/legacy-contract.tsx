import { computed, defineComponent, h, onBeforeUnmount, ref, type createVNode, type PropType, type StyleValue } from 'vue';
import UserSelector from '@blueking/bk-user-selector/vue3';
import { configureNativeSdkComponent } from '@/platform/compat/native-sdk-vue';
import { lookupLegacyUsernames } from '@/platform/sdk/user-selector/lookup';
import './legacy-contract.scss';

interface SelectorUser { id?: string; username?: string; display_name?: string; name?: string; avatar?: string; logo?: string }
configureNativeSdkComponent(UserSelector);

/** Preserve the existing username-array/JSONP contract on the official Vue3 selector. */
export default defineComponent({
  name: 'UsernameSelector',
  inheritAttrs: false,
  compatConfig: { MODE: 3 },
  props: {
    value: { type: Array as PropType<string[]>, default: undefined },
    modelValue: { type: Array as PropType<string[]>, default: undefined },
    api: { type: String, default: '' },
    multiple: { type: Boolean, default: true },
    disabled: Boolean,
    tagClearable: { type: Boolean, default: true },
    tagType: { type: String, default: 'tag' },
    fixedHeight: { type: Boolean, default: true },
    displayDomain: Boolean,
    placeholder: String,
    emptyText: String,
  },
  emits: ['input', 'change', 'update:modelValue', 'focus', 'blur', 'remove-selected'],
  setup(props, { attrs, emit, expose }) {
    const root = ref<HTMLElement | null>(null);
    let enterRequest: AbortController | undefined;
    onBeforeUnmount(() => enterRequest?.abort());
    const values = computed(() => [...(props.value ?? props.modelValue ?? [])]);
    let focused = false;
    const focus = () => {
      if (props.disabled || focused) return;
      focused = true;
      emit('focus');
    };
    const blur = () => {
      if (!focused) return;
      focused = false;
      emit('blur');
    };
    const focusout = (event: FocusEvent) => {
      if (event.relatedTarget instanceof Node && root.value?.contains(event.relatedTarget)) return;
      blur();
    };
    const input = () => props.disabled ? undefined : root.value?.querySelector<HTMLInputElement>('input:not([type="hidden"]):not([disabled])');
    expose({ focus: () => input()?.focus(), blur: () => input()?.blur() });
    const change = (value: string | string[]) => {
      if (props.disabled) return;
      const next = Array.isArray(value) ? [...value] : value ? [value] : [];
      if (next.length === values.value.length && next.every((item, index) => item === values.value[index])) return;
      const removed = values.value.filter(item => !next.includes(item));
      emit('update:modelValue', next);
      emit('input', next);
      emit('change', next);
      removed.forEach(username => emit('remove-selected', username));
    };
    const renderUser = (_render: typeof createVNode, user: SelectorUser) => {
      const username = user.username || user.id || '';
      const name = props.displayDomain ? username : username.replace(/@.*/, '');
      return h('span', { class: 'username-selector-label' }, [
        props.tagType === 'avatar' ? h('span', { class: 'username-selector-avatar',
          style: user.avatar || user.logo ? { backgroundImage: `url(${user.avatar || user.logo})` } : undefined }) : null,
        user.display_name ? `${name}(${user.display_name})` : name,
      ]);
    };
    const handleEnter = async (event: KeyboardEvent) => {
      const target = event.target as HTMLInputElement;
      if (props.disabled || event.key !== 'Enter' || event.isComposing || !props.multiple || !target.value?.trim()) return;
      event.preventDefault(); event.stopPropagation();
      enterRequest?.abort();
      const request = new AbortController(); enterRequest = request;
      try {
        const names = await lookupLegacyUsernames(props.api, [target.value.trim().replace(/\s*\(.*?\)\s*/, '')], request.signal);
        if (request.signal.aborted || enterRequest !== request || !names.length) return;
        change([...new Set([...values.value, ...names])]);
        target.value = '';
        target.dispatchEvent(new Event('input', { bubbles: true }));
      } catch {
        if (!request.signal.aborted) console.warn('[username-selector] lookup failed');
      }
    };
    return () => <div ref={root} class={['username-selector user-selector', attrs.class, {
      'is-fixed-height': props.fixedHeight, 'is-locked-tags': !props.tagClearable || props.tagType === 'avatar',
    }]} style={attrs.style as StyleValue} aria-disabled={props.disabled}
      {...{ onKeydownCapture: handleEnter, onFocusout: focusout, inert: props.disabled || undefined }}>
      <UserSelector {...attrs} class={undefined} style={undefined}
        apiBaseUrl={props.api} enableMultiTenantMode={false} tenantId=''
        multiple={props.multiple} modelValue={props.multiple ? values.value : values.value[0] || ''}
        disabled={props.disabled} placeholder={props.placeholder} emptyText={props.emptyText}
        renderTag={renderUser} renderListItem={renderUser}
        onUpdate:modelValue={change} onFocus={focus} onBlur={blur} />
    </div>;
  },
});
