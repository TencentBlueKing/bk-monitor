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
  <div class="strategy-dimension-input">
    <component
      :is="item.component"
      v-for="(item, index) in alarmConditionList"
      v-show="item.show"
      :key="item.type + '-' + item.compKey"
      :ref="'component-' + index"
      :display-key="setInputDisplayKey"
      unique
      v-bind="item"
      @remove="handleItemRemove(item, index)"
      @set-hide="handleSetHide(item, index)"
      @item-select="data => handleItemSelect(data, item, index)"
      @set-add="item.addEvent && handleSetAdd($event, item, index)"
    />
    <bk-popover class="help-tips">
      <i
        v-if="alarmDimensionList.length"
        class="icon-monitor icon-mc-help-fill"
      />
      <div slot="content">
        <div class="help-text">
          {{ $t('没找到相关的维度？') }}
          <span
            class="help-icon"
            @click="handleGotoLink(paramsMap[monitorType])"
          >
            {{ $t('查看文档') }}
            <i class="icon-monitor icon-mc-wailian" />
          </span>
        </div>
      </div>
    </bk-popover>
    <!-- <span class="input-blank"></span> -->
  </div>
</template>
<script>
import { deepClone, getCookie, random } from 'monitor-common/utils/utils';

import documentLinkMixin from '../../../../mixins//documentLinkMixin';
import SetAdd from './set-add';
import SetInput from './set-input';

export default {
  name: 'StrategyDimensionInput',
  components: {
    SetInput,
    SetAdd,
  },
  mixins: [documentLinkMixin],
  props: {
    monitorType: {
      type: String,
      required: false,
    },
    dimensionList: {
      type: Array,
      default() {
        return [];
      },
    },
    dimensions: {
      type: Array,
      default() {
        return [];
      },
    },
    metricField: {
      type: [String, Number],
      required: true,
    },
    typeId: {
      type: [String, Number],
      required: true,
    },
    dataTypeLabel: {
      type: String,
      required: true,
    },
    dataSourceLabel: {
      type: String,
      required: true,
    },
  },
  data() {
    return {
      alarmConditionList: [],
      defaultDimensionList: [],
      setInputDisplayKey: 'name',
      paramsMap: {
        bk_monitor_time_series: 'fromMonitor', // 监控采集
        bk_log_search_time_series: 'formLogPlatform', // 日志采集
        bk_data_time_series: 'fromDataSource', // 数据平台
        custom_time_series: 'fromCustomRreporting', // 自定义指标
      },
    };
  },
  computed: {
    isReadOnly() {
      return false;
      //   return this.typeId === 'uptimecheck' && this.metricField !== 'task_duration'
      //     && !(this.dataTypeLabel === 'event' && this.dataSourceLabel === 'custom')
    },
    alarmDimensionList() {
      return this.alarmConditionList
        .filter(item => item.type !== 'add')
        .map(item => ({
          ...item.value,
        }));
    },
  },
  watch: {
    dimensionList: {
      handler() {
        const arr = deepClone(this.dimensionList).map(item => ({
          ...item,
          show: !this.dimensions.includes(item.id),
        }));
        this.defaultDimensionList = arr;
      },
      immediate: true,
    },
  },
  created() {
    // 处理setInput组件国际化
    this.setInputDisplayKey = getCookie() === 'en' ? 'id' : 'name';
    this.dimensions.forEach(demension => {
      if (demension) {
        const item = this.getDefaultKey();
        item.value.id = demension;
        const value = this.dimensionList.find(set => set.id === demension);
        item.value.name = value ? value.name : demension;
        this.alarmConditionList.push(item);
      }
    });
    if (!this.isReadOnly) {
      const item = this.getDefaultAdd();
      item.show = true;
      this.alarmConditionList.push(item);
    }
    this.$emit('dimension-select', this.alarmDimensionList, 'created');
  },
  methods: {
    getDefaultKey() {
      const key = random(10);
      return {
        list: this.defaultDimensionList,
        value: {
          id: '',
          name: '',
        },
        component: 'set-input',
        show: true,
        type: 'key',
        'is-key': true,
        compKey: key,
        readonly: this.isReadOnly,
      };
    },
    getDefaultAdd() {
      const key = Date.now();
      return {
        component: 'set-add',
        show: true,
        addEvent: true,
        type: 'add',
        compKey: key,
        addDesc: this.$t('（选择数据汇聚的维度）'),
        addType:
          this.alarmConditionList.length > 0 && this.alarmConditionList.some(item => item.type !== 'add')
            ? 'common'
            : 'character',
      };
    },
    handleSetAdd(e, item, index) {
      e.preventDefault();
      item.show = false;
      this.alarmConditionList.splice(index, 0, this.getDefaultKey());
      this.$nextTick().then(() => {
        const ref = this.$refs[`component-${index}`][0];
        ref.getInput().focus();
        ref.handleSetClick();
        const len = this.alarmConditionList.length;
        this.alarmConditionList[len - 1].addType = len > 1 ? 'common' : 'character';
      });
    },
    handleItemSelect(data, item) {
      if (item.value.id !== data.id || item.value.name !== data.name) {
        item.value = { ...data };
        this.alarmConditionList[this.alarmConditionList.length - 1].show = true;
        this.$emit('dimension-select', this.alarmDimensionList);
      }
    },
    handleSetHide(item) {
      item.show = false;
      const len = this.alarmConditionList.length;
      this.alarmConditionList[this.alarmConditionList.length - 1].show = true;
      this.alarmConditionList[len - 1].addType =
        len > 1 && this.alarmConditionList.filter(item => item.show).some(item => item.type !== 'add')
          ? 'common'
          : 'character';
    },
    handleItemRemove(item, index) {
      this.alarmConditionList.splice(index, 1);
      const len = this.alarmConditionList.length;
      this.alarmConditionList[len - 1].show = true;
      this.alarmConditionList[len - 1].addType =
        len > 1 && this.alarmConditionList.filter(item => item.show).some(item => item.type !== 'add')
          ? 'common'
          : 'character';
      this.$emit('dimension-delete', { ...item.value }, this.alarmDimensionList);
    },
    getValue() {
      const data = [];
      this.alarmConditionList.forEach(item => {
        const { type } = item;
        if (type === 'key' && `${item.value.id}`.length) {
          data.push(item.value.id);
        }
      });
      return data;
    },
  },
};
</script>
<style lang="scss" scoped>
.strategy-dimension-input {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  width: 100%;
  font-size: 12px;
  color: #63656e;

  .input-blank {
    box-sizing: border-box;
    flex: 1;
    height: 32px;
    margin-top: 2px;
    margin-right: 2px;
    background: #fafbfd;
    border: 1px solid #f0f1f5;
    border-radius: 2px;
  }

  .icon-mc-help-fill {
    font-size: 16px;
    color: #c4c6cc;

    &:hover {
      color: #3a84ff;
    }
  }
}

.help-tips {
  margin-left: 10px;
}

.help-text {
  display: flex;
  align-items: center;

  .help-icon {
    display: flex;
    align-items: center;
    line-height: 16px;
    color: #3a84ff;
    cursor: pointer;

    .icon-mc-wailian {
      font-size: 24px;
    }
  }
}
</style>
