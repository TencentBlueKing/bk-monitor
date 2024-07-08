<template>
  <div class="filter-bar">
    <div class="filter-item">
      <div class="type-switcher bk-button-group">
        <bk-button
          @click="handleSelectShowType('log')"
          :class="{ 'is-selected': showType === 'log' }"
          >{{ $t('日志') }}</bk-button>
        <bk-button
          @click="handleSelectShowType('code')"
          :class="{ 'is-selected': showType === 'code' }"
          >{{ $t('代码') }}</bk-button>
      </div>
      <span>{{ $t('label-过滤内容').replace('label-', '') }}</span>
      <bk-select
        v-model="filterType"
        style="width: 100px"
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
        v-model="filterKey"
        :style="{ width: isScreenFull ? '400px' : '260px', margin: '0 10px' }"
        :clearable="true"
        :right-icon="'bk-icon icon-search'"
        :placeholder="$t('输入关键字进行过滤')"
        @enter="filterLog"
        @clear="filterLog"
        @blur="filterLog"
      ></bk-input>
      <span>{{ $t('label-高亮').replace('label-', '') }}</span>
      <bk-tag-input
        v-model="heightLightList"
        allow-create
        has-delete-icon
        :style="{ width: isScreenFull ? '400px' : '260px', margin: '0 10px' }"
        :paste-fn="pasteFn"
        @change="changeLightList"
      >
      </bk-tag-input>
    </div>
    <div class="filter-item">
      <bk-checkbox
        v-model="ignoreCase"
        style="margin-right: 4px"
      >
      </bk-checkbox>
      <span>{{ $t('大小写敏感') }}</span>
      <div
        v-if="filterType === 'include'"
        class="filter-bar"
        style="margin-left: 6px"
      >
        <bk-checkbox
          v-model="intervalSwitcher"
          style="margin-right: 4px"
          @change="handleChangeIntervalShow"
        ></bk-checkbox>
        <span>{{ $t('显示前') }}</span>
        <bk-input
          v-model="interval.prev"
          style="width: 74px; margin-right: 10px"
          type="number"
          :show-controls="false"
          :max="100"
          :min="0"
          placeholder="请输入"
        >
        </bk-input>
        <span>{{ $t('行') }}</span>
        <span>{{ $t(', 后') }}</span>
        <bk-input
          v-model="interval.next"
          style="width: 74px; margin-right: 10px"
          type="number"
          :show-controls="false"
          :max="100"
          :min="0"
          placeholder="请输入"
        >
        </bk-input>
        <span>{{ $t('行') }}</span>
      </div>
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
        baseInterval: {
          prev: 0,
          next: 0,
        },
        /** 高亮list */
        heightLightList: [],
        /** 显示前-后行开关 */
        intervalSwitcher: true,
        /** 当前的展示类型 */
        showType: 'log',
      };
    },
    watch: {
      ignoreCase(val) {
        this.$emit('handle-filter', 'ignoreCase', val);
      },
      interval: {
        deep: true,
        handler(val) {
          this.$emit('handle-filter', 'interval', this.intervalSwitcher ? val : this.baseInterval);
        },
      },
    },
    methods: {
      filterLog() {
        this.$emit('handle-filter', 'filterKey', this.filterKey);
      },
      changeLightList() {
        this.$emit('handle-filter', 'heightLightList', this.heightLightList);
      },
      handleFilterType(val) {
        this.$emit('handle-filter', 'filterType', val);
      },
      handleSelectShowType(type) {
        this.showType = type;
        this.$emit('handle-filter', 'showType', type);
      },
      handleChangeIntervalShow(state) {
        this.$emit('handle-filter', 'interval', state ? this.interval : this.baseInterval);
      },
      // 粘贴过滤条件
      pasteFn(pasteValue) {
        const trimPasteValue = pasteValue.trim();
        if (!this.heightLightList.includes(trimPasteValue)) {
          this.heightLightList.push(trimPasteValue);
          this.changeLightList();
        }
        return [];
      },
    },
  };
</script>

<style lang="scss" scoped>
  .filter-bar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;

    span {
      margin-right: 10px;
      color: #2d3542;
    }

    .filter-item {
      display: flex;
      align-items: center;
      margin-bottom: 14px;

      .type-switcher {
        min-width: 126px;
        margin-right: 24px;
      }

      > span {
        display: block;
        min-width: 56px;
        text-align: right;
      }
    }

    .hot-key {
      color: #979ba5;
    }
  }
</style>
