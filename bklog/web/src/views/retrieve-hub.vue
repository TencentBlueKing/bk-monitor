<script setup>
  import { computed } from 'vue';

  import { useRoute } from 'vue-router/composables';

  const retrieveV2 = () => import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve-v2');
  const retrieve = () => import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve');
  const route = useRoute();

  const version = localStorage.getItem('retrieve_version') ?? 'v2';

  const RetrieveComponent = computed(() => {
    if (route.name === 'retrieve') {
      if (version === 'v1') {
        return retrieve;
      }
    }

    return retrieveV2;
  });
</script>
<template>
  <component :is="RetrieveComponent"></component>
</template>
