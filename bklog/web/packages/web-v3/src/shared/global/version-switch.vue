<script setup lang="ts">import { asDictionary } from '@/shared/utils/typed-record';

  import useLocale from '@/shared/composables/use-locale';
  import { computed } from 'vue';

  const props = defineProps({
    version: {
      type: String,
      default: 'v2',
    },
    theme: {
      type: String,
      default: 'light',
    },
  });

  const { t } = useLocale();

  const textMap = asDictionary({
    v2: t('回到旧版'),
    v1: t('切换新版'),
  });
  const showText = computed(() => {
    return textMap[props.version];
  });

  const handleVersionChanged = () => {
    const nextVersion = props.version === 'v2' ? 'v1' : 'v2';
    localStorage.setItem('retrieve_version', nextVersion);
    window.location.reload();
  };
</script>
<template>
  <button
    type="button"
    :class="['bklog-version-switch', { 'is-dark': props.theme === 'dark' }]"
    @click="handleVersionChanged"
  >
    <span class="bklog-icon bklog-qiehuanbanben"></span>
    <span class="version-switch-text">{{ showText }}</span>
  </button>
</template>
<style lang="scss" scoped>
  .bklog-version-switch {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--bklog-space-4);
    height: 100%;
    padding: 0 var(--bklog-space-12);
    font-size: var(--bklog-font-body);
    line-height: var(--bklog-line-height-body);
    color: var(--bklog-brand-primary);
    white-space: nowrap;
    cursor: pointer;
    background: var(--td-bg-color-container);
    border: 0;
    transition: background-color 0.2s, color 0.2s, border-color 0.2s;

    .bklog-icon {
      font-size: 14px;
      line-height: 1;
    }

    &:focus-visible {
      outline: var(--bklog-border-width) solid var(--td-brand-color);
      outline-offset: var(--bklog-space-2);
    }

    &.is-dark {
      height: calc(var(--bklog-space-24) + var(--bklog-space-4));
      padding: 0 var(--bklog-space-12);
      color: var(--bklog-navigation-selector-text);
      background: var(--bklog-navigation-selector-surface);
      border-radius: calc(var(--bklog-space-12) + var(--bklog-space-2));

      &:hover {
        color: var(--bklog-text-inverse);
        background: color-mix(in srgb, var(--bklog-brand-primary) 32%, var(--bklog-navigation-selector-surface));
      }
    }
  }
</style>
