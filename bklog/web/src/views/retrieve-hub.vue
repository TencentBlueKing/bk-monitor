<script setup>
  import { computed } from 'vue';

  import { useRoute } from 'vue-router/composables';

  const retrieveV2 = () => import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve-v2');
  const retrieve = () => import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve');
  const route = useRoute();

  const RetrieveComponent = computed(() => {
    if (route.name === 'retrieve') {
      const isDebug = window.FEATURE_TOGGLE.bklog_search_new === 'debug';
      const isOn = window.FEATURE_TOGGLE.bklog_search_new === 'on';

      if (isDebug) {
        const whiteList = (window.FEATURE_TOGGLE_WHITE_LIST.bklog_search_new ?? []).map(id => `${id}`);
        const bkBizId = route.query.bizId;
        if (bkBizId && whiteList.includes(bkBizId)) {
          return retrieveV2;
        }
      }
      return isOn ? retrieveV2 : retrieve;
    }
    return retrieve;
  });
</script>
<template>
  <component :is="RetrieveComponent"></component>
</template>
