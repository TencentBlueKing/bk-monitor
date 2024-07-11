<template>
  <div class="filter-bar">
    <span>{{ $t('label-过滤内容').replace('label-', '') }}</span>
    <bk-select
      style="width: 100px"
      v-model="filterType"
      :clearable="false"
      @change="handleFilterType"
    >
      <bk-option
        v-for="(option, index) in filterTypeList"
        :id="option.id"
        :key="index"
        :name="option.name"
      >
      </bk-option>
    </bk-select>
    <bk-input
      :style="{ width: isScreenFull ? '500px' : '260px', margin: '0 10px' }"
      v-model="filterKey"
      :clearable="true"
      :placeholder="$t('输入关键字进行过滤')"
      :right-icon="'bk-icon icon-search'"
      @blur="filterLog"
      @clear="filterLog"
      @enter="filterLog"
    ></bk-input>
    <bk-checkbox
      style="margin-right: 4px"
      v-model="ignoreCase"
      :false-value="false"
      :true-value="true"
    >
    </bk-checkbox>
    <span>{{ $t('大小写敏感') }}</span>
    <div
      v-if="filterType === 'include'"
      style="margin-left: 6px"
      class="filter-bar"
    >
      <span>{{ $t('显示前') }}</span>
      <bk-input
        style="width: 74px; margin-right: 10px"
        v-model="interval.prev"
        :max="100"
        :min="0"
        :show-controls="false"
        placeholder="请输入"
        type="number"
      >
      </bk-input>
      <span style="margin-right: 20px">{{ $t('行') }}</span>
      <span>{{ $t('显示后') }}</span>
      <bk-input
        style="width: 74px; margin-right: 10px"
        v-model="interval.next"
        :max="100"
        :min="0"
        :show-controls="false"
        placeholder="请输入"
        type="number"
      >
      </bk-input>
      <span>{{ $t('行') }}</span>
    </div>
  </div>
</template>

<script>
  export default {
    props: {
      isScreenFull: Boolean,
    },
    data() {
      return {
        filterType: 'include',
        filterKey: '',
        ignoreCase: false,
        filterTypeList: [
          { id: 'include', name: this.$t('包含') },
          { id: 'uninclude', name: this.$t('不包含') },
        ],
        interval: {
          prev: 0,
          next: 0,
        },
      };
    },
    watch: {
      ignoreCase(val) {
        this.$emit('handle-filter', 'ignoreCase', val);
      },
      interval: {
        deep: true,
        handler(val) {
          this.$emit('handle-filter', 'interval', val);
        },
      },
    },
    methods: {
      filterLog() {
        this.$emit('handle-filter', 'filterKey', this.filterKey);
      },
      handleFilterType(val) {
        this.$emit('handle-filter', 'filterType', val);
      },
    },
  };
</script>

<style lang="scss" scoped>
  .filter-bar {
    display: flex;
    align-items: center;

    span {
      margin-right: 10px;
      color: #2d3542;
    }

    .hot-key {
      color: #979ba5;
    }
  }
</style>
