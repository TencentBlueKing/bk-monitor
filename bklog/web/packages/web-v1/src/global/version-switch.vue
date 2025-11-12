<script setup lang="ts">
  import useLocale from '@/hooks/use-locale';
import { sendIframeMessage } from '@/iframe.message';
  import { computed } from 'vue';

  const props = defineProps({
    version: {
      type: String,
      default: 'v2',
    },
  });

  const { t } = useLocale();

  const showText = computed(() => {
    return t('切换新版');
  });

  const handleVersionChanged = () => {
    sendIframeMessage({
      swtichVersion: true,
      query: {},
      params: {},
    });
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
