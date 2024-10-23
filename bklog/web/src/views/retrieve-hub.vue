<script setup>
  import { computed } from 'vue';

  import { useRoute } from 'vue-router/composables';
  import useStore from '../hooks/use-store';

  const retrieveV2 = () => import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve-v2');
  const retrieve = () => import(/* webpackChunkName: 'logRetrieve' */ '@/views/retrieve');
  const store = useStore();
  const route = useRoute();

  const version = sessionStorage.getItem('retrieve_version') ?? 'v2';

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
