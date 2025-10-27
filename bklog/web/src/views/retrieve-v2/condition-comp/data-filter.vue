<template>
  <div class="filter-bar">
    <div class="filter-item">
      <div class="type-switcher bk-button-group">
        <bk-button
          @click="handleSelectShowType('log')"
          :class="{ 'is-selected': showType === 'log' }"
        >
          {{ $t('日志') }}
        </bk-button>
        <bk-button
          @click="handleSelectShowType('code')"
          :class="{ 'is-selected': showType === 'code' }"
        >
          {{ $t('代码') }}
        </bk-button>
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
        @blur="blurFilterLog"
      ></bk-input>
      <span>{{ $t('label-高亮').replace('label-', '') }}</span>
      <bk-tag-input
        v-model="highlightList"
        allow-create
        has-delete-icon
        ref="tagInput"
        :max-data="5"
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
        <span>，</span>
        <span>{{ $t('后') }}</span>
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
      <div style="margin-left: 6px">
        <bk-button @click="handleScrollToCurrentRow">{{ $t('定位到当前行') }}</bk-button>
      </div>
    </div>
  </div>
</template>

<script>
  import {  contextHighlightColor } from '../../../common/util';
  export default {
    props: {
      isScreenFull: Boolean,
    },
    data() {
      return {
        filterType: 'include',
        filterKey: '',
        catchFilterKey: '',
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
        highlightList: [],
        colorHighlightList: [],
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
    computed: {
      catchColorIndexList() {
        return this.colorHighlightList.map(item => item.colorIndex);
      },
    },
    methods: {
      handleScrollToCurrentRow() {
        this.$emit('fix-current-row');
      },
      filterLog() {
        this.catchFilterKey = this.filterKey;
        this.$emit('handle-filter', 'filterKey', this.filterKey);
      },
      blurFilterLog() {
        if (!this.catchFilterKey && !this.filterKey) return;
        this.filterLog();
      },
      changeLightList() {
        // 找出未显示的颜色
        const colorIndex = contextHighlightColor.findIndex((item, index) => !this.catchColorIndexList.includes(index));
        const catchCloneColorList = structuredClone(this.colorHighlightList);
        // 给高亮颜色重新赋值
        this.colorHighlightList = this.highlightList.map(item => {
          const notChangeItem = catchCloneColorList.find(cItem => cItem.heightKey === item);
          if (notChangeItem) return notChangeItem;
          return {
            heightKey: item,
            colorIndex,
            color: contextHighlightColor[colorIndex],
          };
        });
        // 更新input输入框的颜色
        this.$nextTick(() => {
          this.initTagInputColor();
        });
        this.$emit('handle-filter', 'highlightList', this.colorHighlightList);
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
        if (!this.highlightList.includes(trimPasteValue) && this.highlightList.length < 5) {
          this.highlightList.push(trimPasteValue);
          this.changeLightList();
        }
        return [];
      },
      /** 更新taginput组件中的颜色 */
      initTagInputColor() {
        const childEl = this.$refs.tagInput.$el.querySelectorAll('.key-node');
        childEl.forEach(child => {
          const tag = child.querySelectorAll('.tag')[0];
          const colorObj = this.colorHighlightList.find(item => item.heightKey === tag.innerText);
          [child, tag].forEach(item => {
            Object.assign(item.style, {
              backgroundColor: colorObj.color.light,
            });
          });
        });
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
