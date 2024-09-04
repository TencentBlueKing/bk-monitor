<script setup>
  import BizMenuSelect from '@/components/biz-menu';
  import FieldSetting from './field-setting.vue';
  import RetrieveSetting from './retrieve-setting.vue';
</script>
<template>
  <div class="subbar-container">
    <div class="box-biz-select"><BizMenuSelect theme="light"></BizMenuSelect></div>
    <div class="box-right-option">
      <FieldSetting></FieldSetting>
      <div class="more-setting">
        <RetrieveSetting></RetrieveSetting>
      </div>
    </div>
  </div>
</template>
<style scoped>
  @import './index.scss';
</style>
