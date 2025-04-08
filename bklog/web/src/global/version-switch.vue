<script setup lang="ts">
  import useLocale from '@/hooks/use-locale';
  import { computed } from 'vue';

  const props = defineProps({
    version: {
      type: String,
      default: 'v2',
    },
  });

  const { t } = useLocale();

  const textMap = {
    v2: t('回到旧版'),
    v1: t('切换新版'),
  };
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
  <div
    @click="handleVersionChanged"
    class="bklog-version-switch"
  >
    <span class="bklog-icon bklog-qiehuanbanben"></span>{{ showText }}
  </div>
</template>
<style lang="scss" scoped>
  .bklog-version-switch {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 90px;
    height: 100%;
    font-size: 12px;
    color: #3a84ff;
    cursor: pointer;
    background: #ffffff;

    span {
      margin-right: 6px;
      font-size: 16px;
    }
  }
</style>
