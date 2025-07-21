<script setup>
import { computed } from 'vue';

import { useRoute } from 'vue-router/composables';

const retrieveV2 = () => import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve-v2');
const retrieveV3 = () => import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve-v3');
const retrieve = () => import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve');
const route = useRoute();

const version = localStorage.getItem('retrieve_version') ?? 'v3';

const RetrieveComponent = computed(() => {
  if (route.name === 'retrieve') {
    if (version === 'v1') {
      return retrieve;
    }
  }

  if (route.query.version === 'v2') {
    return retrieveV2;
  }

  return retrieveV3;
});
</script>
<template>
  <component :is="RetrieveComponent"></component>
</template>
