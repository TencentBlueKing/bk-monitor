<script setup>
  import { computed } from 'vue';

  import { useRoute } from 'vue-router/composables';
  import useStore from '../hooks/use-store';

  const retrieveV2 = () => import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve-v2');
  const retrieve = () => import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve');
  const store = useStore();
  const route = useRoute();

  const version = sessionStorage.getItem('retrieve_version') ?? 'v2';
  // const version = computed(() => store.state.retrieve.activeVersion);

  const RetrieveComponent = computed(() => {
    if (route.name === 'retrieve') {
      if (version === 'v1') {
        return retrieve;
      }

      // const isDebug = window.FEATURE_TOGGLE.bklog_search_new === 'debug';
      // const isOn = window.FEATURE_TOGGLE.bklog_search_new === 'on';

      // if (isDebug) {
      //   const whiteList = (window.FEATURE_TOGGLE_WHITE_LIST?.bklog_search_new ?? []).map(id => `${id}`);
      //   const spaceWhiteList = window.SPACE_UID_WHITE_LIST?.bklog_search_new ?? [];

      //   const bkBizId = route.query.bizId;
      //   const spaceUid = route.query.spaceUid;
      //   if ((bkBizId && whiteList.includes(bkBizId)) || spaceWhiteList.includes(spaceUid)) {
      //     return retrieveV2;
      //   }
      // }

      // if (isOn) {
      //   return retrieveV2;
      // }

      // return retrieveV2;
    }

    return retrieveV2;
  });
</script>
<template>
  <component :is="RetrieveComponent"></component>
</template>
