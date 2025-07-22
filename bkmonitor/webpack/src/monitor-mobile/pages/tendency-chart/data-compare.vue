<!--
* Tencent is pleased to support the open source community by making
* 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
*
* Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
*
* 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
*
* License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
*
* ---------------------------------------------------
* Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
* documentation files (the "Software"), to deal in the Software without restriction, including without limitation
* the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
* to permit persons to whom the Software is furnished to do so, subject to the following conditions:
*
* The above copyright notice and this permission notice shall be included in all copies or substantial portions of
* the Software.
*
* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
* THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
* AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
* CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
* IN THE SOFTWARE.
-->
<template>
  <div class="table">
    <!-- 对比类型和维度 -->
    <div class="table-filter">
      <div
        class="table-filter-type"
        @click="handleShowPopup('compareType')"
      >
        {{ compareText }}
        <i class="icon-down" />
      </div>
      <div
        class="table-filter-dimension"
        v-show="compareType.value > 0"
        @click="handleShowPopup('compareData')"
      >
        {{ compareValue }}
        <i class="icon-down" />
      </div>
    </div>
    <!-- 表头 -->
    <van-row class="table-header">
      <van-col
        v-for="(config, index) in dataConfig"
        :key="index"
        :span="config.span"
      >
        {{ config.label }}
      </van-col>
    </van-row>
    <!-- 表格内容 -->
    <van-row
      v-for="(row, index) in data"
      class="table-body"
      :key="index"
    >
      <van-col
        v-for="(config, i) in dataConfig"
        :key="i"
        :span="config.span"
      >
        <span
          v-if="config.prop === 'name'"
          :style="{
            background: colors[index],
          }"
          class="compare-icon"
        />
        <span>{{ row[config.prop] | filterBigNum }}</span>
      </van-col>
    </van-row>
    <!-- select -->
    <bk-select
      v-model="currentCompare.value"
      :columns="columns"
      :show.sync="showPopup"
      @cancel="handleCancel"
      @confirm="handleConfirm"
    />
  </div>
</template>
<script lang="ts">
import { Component, Emit, Prop, Vue } from 'vue-property-decorator';

import { transfromNum } from 'monitor-common/utils/utils';
import { Col, DropdownItem, DropdownMenu, Picker, Popup, Row } from 'vant';

import BkSelect from '../../components/select/select.vue';
import type { ICompare, IConfig, IContent, IDropdownMenu, IOptions } from '../../types/tendency-chart';

@Component({
  name: 'data-compare',
  components: {
    [Row.name]: Row,
    [Col.name]: Col,
    [DropdownMenu.name]: DropdownMenu,
    [DropdownItem.name]: DropdownItem,
    [Popup.name]: Popup,
    [Picker.name]: Picker,
    BkSelect,
  },
  filters: {
    filterBigNum(v) {
      if (!v) return '--';
      return isNaN(v) ? v : transfromNum(v);
    },
  },
})
export default class Table extends Vue {
  // 对比数据
  @Prop({ default: () => [] }) private readonly data: IContent[];
  // 对比曲线颜色
  @Prop({ default: () => [] }) private readonly colors: string[];

  // 表格配置
  private dataConfig: IConfig[] = [];

  // 对比类型（时间对比、维度对比）
  private compareType: IDropdownMenu = {
    value: 1,
    options: [],
  };

  // 对比时间
  private compareData: IDropdownMenu = {
    value: 24,
    options: [],
  };

  // select组件是否显示
  private showPopup = false;

  // 当前select组件的数据类型
  private currentPopup = 'compareType';

  private currentCompare: ICompare = {
    type: '',
    value: 0,
  };

  created() {
    this.dataConfig = [
      {
        label: this.$tc('时间'),
        span: 7,
        prop: 'name',
      },
      {
        label: 'min',
        span: 3,
        prop: 'min',
      },
      {
        label: 'max',
        span: 3,
        prop: 'max',
      },
      {
        label: 'avg',
        span: 3,
        prop: 'avg',
      },
      {
        label: 'current',
        span: 4,
        prop: 'current',
      },
      {
        label: 'total',
        span: 4,
        prop: 'total',
      },
    ];
    this.compareType.options = [
      {
        text: this.$t('时间对比'),
        value: 1,
      },
      {
        text: this.$t('不对比'),
        value: 0,
      },
    ];
    this.compareData.options = [
      {
        text: this.$t('天前', { num: 1 }),
        value: 24,
      },
      {
        text: this.$t('天前', { num: 2 }),
        value: 24 * 2,
      },
      {
        text: this.$t('天前', { num: 3 }),
        value: 24 * 3,
      },
      {
        text: this.$t('天前', { num: 4 }),
        value: 24 * 4,
      },
      {
        text: this.$t('天前', { num: 5 }),
        value: 24 * 5,
      },
      {
        text: this.$t('天前', { num: 6 }),
        value: 24 * 6,
      },
      {
        text: this.$t('周前', { num: 1 }),
        value: 24 * 7,
      },
      {
        text: this.$t('周前', { num: 2 }),
        value: 24 * 7 * 2,
      },
      {
        text: this.$t('月前', { num: 1 }),
        value: 24 * 30,
      },
    ];
  }

  // 当前select组件的options数据
  get columns(): IOptions[] {
    return this.currentPopup === 'compareType' ? this.compareType.options : this.compareData.options;
  }

  // 对比方式文案
  get compareText() {
    const options = this.compareType.options.find(item => item.value === this.compareType.value);
    return options ? options.text : '';
  }

  // 对比值
  get compareValue() {
    const options = this.compareData.options.find(item => item.value === this.compareData.value);
    return options ? options.text : '';
  }

  handleShowPopup(v) {
    this.currentPopup = v;
    this.showPopup = true;
  }

  @Emit('change')
  handleConfirm(value: number) {
    if (this.currentPopup === 'compare') {
      this.compareType.value = value;
    } else if (this.currentPopup === 'compareType') {
      this.compareType.value = value;
    } else {
      this.compareData.value = value;
    }
    this.handleCancel();
    this.currentCompare = {
      type: this.currentPopup,
      value,
    };
    return this.currentCompare;
  }

  handleCancel() {
    this.showPopup = false;
  }
}
</script>
<style lang="scss">
.van-row {
  line-height: 3.125rem;
  border-bottom: 1px solid rgba(220, 222, 229, 0.6);

  .van-col:not(:first-child) {
    text-align: right;
  }
}

@mixin select-btn {
  padding: 0 0.75rem;
  color: #63656e;
  background: #f0f1f5;
  border-radius: 4px;
}

.table {
  padding: 0 1.5rem 0 1.5rem;
  padding-top: 1rem;
  font-size: 0.8rem;
  background: #fff;

  &-filter {
    display: flex;
    line-height: 2rem;

    &-type {
      display: flex;
      flex: 0 7.5rem;
      align-items: center;
      justify-content: space-between;
      margin-right: 0.625rem;

      @include select-btn;
    }

    &-dimension {
      display: flex;
      flex: 1;
      align-items: center;
      justify-content: space-between;

      @include select-btn;
    }

    .icon-down {
      display: inline-block;
      width: 0;
      height: 0;
      border-color: #979ba5 transparent transparent transparent;
      border-style: solid;
      border-width: 5px;
      transform: translateY(2px);
    }
  }

  &-header {
    &.van-row {
      font-weight: 500;
      color: #313238;
    }
  }

  &-body {
    &.van-row {
      font-weight: 400;
      color: #63656e;

      .van-col:first-child {
        display: flex;
        align-items: center;
      }
    }

    .compare-icon {
      display: inline-block;
      width: 1rem;
      height: 0.8rem;
      margin-right: 0.5rem;
    }
  }
}
</style>
