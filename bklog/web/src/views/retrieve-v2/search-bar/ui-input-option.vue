<script setup>
  import { computed, ref } from 'vue';
  import useStore from '@/hooks/use-store';

  const store = useStore();
  const searchValue = ref('');
  const fieldList = computed(() => store.state.retrieve?.indexSetList ?? []);

</script>
<template>
  <div class="ui-query-options">
    <div class="option-content">
      <div class="field-list">
        <div class="ui-search-input">
          <bk-input
            :placeholder="$t('请输入关键字')"
            :left-icon="'bk-icon icon-search'"
            v-model="searchValue"
            behavior="simplicity"
            style="width: 100%"
          >
          </bk-input>
        </div>
        <div class="ui-search-result">
          <div v-for="item in fieldList" ></div>
        </div>
      </div>
      <div class="value-list"></div>
    </div>
    <div class="option-footer"></div>
  </div>
</template>
<style scoped>
  @import './ui-input-option.scss';
</style>
