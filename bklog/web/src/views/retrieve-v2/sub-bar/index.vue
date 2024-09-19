<script setup>
  import { ref } from 'vue';

  import BizMenuSelect from '@/components/biz-menu';

  // import FieldSetting from './field-setting.vue';
  import ClusterSetting from '../setting-modal/index.vue';
  import RetrieveSetting from './retrieve-setting.vue';

  const isShowClusterSetting = ref(false);
</script>
<template>
  <div class="subbar-container">
    <div class="box-biz-select">
      <BizMenuSelect theme="light"></BizMenuSelect>
    </div>
    <div class="box-right-option">
      <ClusterSetting v-model="isShowClusterSetting"></ClusterSetting>
      <div class="more-setting">
        <RetrieveSetting :is-show-cluster-setting.sync="isShowClusterSetting"></RetrieveSetting>
      </div>
    </div>
  </div>
</template>
<style scoped>
  @import './index.scss';
</style>
