<script setup lang="ts">
  import useStore from '@/hooks/use-store';
  import useLocale from '@/hooks/use-locale';
  // import useRoute from '@/hooks/use-route';
  // import useRouter from '@/hooks/use-router';
  import { computed } from 'vue';

  const props = defineProps({
    version: {
      type: String,
      default: 'v2',
    },
  });

  const store = useStore();
  const { t } = useLocale();

  // const route = useRoute();
  // const router = useRouter();

  const textMap = {
    v2: t('回到旧版'),
    v1: t('切换新版'),
  };
  const showText = computed(() => {
    return textMap[props.version];
  });

  const handleVersionChanged = () => {
    const nextVersion = props.version === 'v2' ? 'v1' : 'v2';
    // store.commit('retrieve/updateActiveVersion', nextVersion);
    // localStorage.setItem('retrieve_version', nextVersion);
    sessionStorage.setItem('retrieve_version', nextVersion);
    window.location.reload();
    // router.retrieve
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
    width: 108px;
    height: 32px;
    font-size: 14px;
    color: #63656e;
    cursor: pointer;
    background: #ffffff;
    border: 1px solid #c4c6cc;
    border-radius: 2px;

    span {
      margin-right: 6px;
    }
  }
</style>
