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
  <div
    v-show="fieldData.length || panelName"
    class="filter-tag"
  >
    <span
      v-en-style="'flex: 0 0 105px'"
      class="filter-tag-title"
      >{{ $t('筛选条件') }}</span
    >
    <div class="filter-tag-content">
      <span
        v-for="(item, index) in fieldData"
        :key="index"
        class="tag"
      >
        <span>{{ item.name }}</span>
        <span class="ml5 mr5 tag-value">{{ item.display }}</span>
        <span>{{ `( ${item.count} )` }}</span>
        <i
          class="icon-monitor icon-mc-close"
          @click="handleDelete(item)"
        />
      </span>
      <span
        v-if="panelName"
        class="tag"
      >
        <span class="ml5 mr5 tag-value">{{ panelName }}</span>
        <span>{{ `( ${panelData.length} )` }}</span>
        <i
          class="icon-monitor icon-mc-close"
          @click="handleDeletePanel"
        />
      </span>
      <bk-button
        v-if="fieldData.length || panelName"
        text
        class="btn"
        @click="handleClear"
      >
        {{ $t('清空筛选条件') }}
      </bk-button>
    </div>
  </div>
</template>
<script lang="ts">
import { Component, Emit, Inject, Vue } from 'vue-property-decorator';

import { typeTools } from 'monitor-common/utils/utils.js';

import type { IConditionValue, IOption, ITag } from '../performance-type';
import type TableStore from '../table-store';

@Component({ name: 'filter-tag' })
export default class FilterTag extends Vue {
  @Inject('tableInstance') private readonly tableInstance: TableStore;

  // 筛选面板Map
  private panelKeyMap = {
    unresolveData: window.i18n.t('告警中的主机'),
    cpuData: `${window.i18n.t('CPU使用率超80%')}`,
    menmoryData: `${window.i18n.t('应用内存使用率超80%')}`,
    diskData: `${window.i18n.t('磁盘空间使用率超80%')}`,
  };

  // 当前筛选面板name
  private get panelName() {
    const { panelKey } = this.tableInstance;
    return panelKey ? this.panelKeyMap[panelKey] : '';
  }

  private get panelData() {
    const { panelKey } = this.tableInstance;
    return this.tableInstance[panelKey] || [];
  }

  private get fieldData() {
    const data: ITag[] = [];
    const fieldData = this.tableInstance.fieldData.reduce((pre, next) => {
      // 为空不展示
      if ((Array.isArray(next.value) && next.value.length === 0) || typeTools.isNull(next.value)) return pre;

      if (next.type === 'condition') {
        // 使用率类型
        (next.value as IConditionValue[]).forEach(item => {
          const range = item as IConditionValue;
          if (typeTools.isNull(range.value)) return;
          // 这里value类型为对象，原始类型为数组, originValue保存的是当前tag下对应的原始值类型
          pre.push({
            id: next.id,
            name: next.name,
            display: `${range.condition}${range.value}%`,
            value: range,
            count: 0,
            conditions: next.conditions,
            originValue: [range],
          });
        });
      } else if (next.type === 'select') {
        // 下拉框类型
        // 区分单选和多选
        const data = Array.isArray(next.value)
          ? (next.value as (number | string)[]).reduce<IOption[]>((pre, value) => {
              const data = next.options.find(item => item.id === value);
              if (data) {
                pre.push(data);
              }
              return pre;
            }, [])
          : next.options.filter(item => item.id === next.value).slice(0, 1);
        data.length &&
          pre.push({
            id: next.id,
            name: next.name,
            display: data.map(item => item.name).join(','),
            value: data,
            count: 0,
            dynamic: next.dynamic ?? false,
            originValue: data.map(item => item.id),
          });
      } else if (next.type === 'checkbox') {
        // 复选框类型
        (next.value as number[]).forEach(item => {
          const data = next.options.find(data => data.id === item);
          data &&
            pre.push({
              id: next.id,
              name: next.name,
              display: data.name,
              value: data,
              count: 0,
              originValue: [data.id],
            });
        });
      } else if (next.type === 'cascade') {
        // 级联类型(多选)
        const data = (next.value as string[][]).reduce<string[]>((pre, value) => {
          pre.push(
            value
              .map(v => {
                return this.tableInstance.topoNameMap[v];
              })
              .join(' / ')
          );
          return pre;
        }, []);

        data.length &&
          pre.push({
            id: next.id,
            name: next.name,
            display: data.join(','),
            value: next.value,
            count: 0,
            originValue: next.value,
          });
      } else if (next.type === 'textarea') {
        // 富文本类型
        const tmpValue = (next.value as string)
          .replace(/\n|,/g, '|')
          .replace(/\s+/g, '')
          .split('|')
          .filter(item => !!item);
        pre.push({
          id: next.id,
          name: next.name,
          display: this.$t('{num} 个', { num: tmpValue.length }) as string,
          value: next.value,
          count: 0,
          originValue: next.value,
        });
      } else {
        pre.push({
          id: next.id,
          name: next.name,
          display: next.value as string,
          value: next.value,
          count: 0,
          originValue: next.value,
        });
      }
      return pre;
    }, data);
    // 计算统计信息
    const { allData = [] } = this.tableInstance;
    allData.forEach(item => {
      fieldData.forEach(field => {
        const { originValue } = field;
        this.tableInstance.isMatchedCondition(item, {
          ...field,
          value: originValue,
        } as any) && (field.count += 1);
      });
    });
    return fieldData;
  }
  // 删除筛选面板
  @Emit('filter-change')
  private handleDeletePanel() {
    this.tableInstance.panelKey = '';
    this.handleSearchUpdate(undefined, '');
  }

  // 删除筛选条件
  @Emit('filter-change')
  private handleDelete(item: ITag) {
    const field = this.tableInstance.fieldData.find(data => data.id === item.id);
    if (!field) return;

    switch (field.type) {
      case 'condition': {
        const fieldValues = field.value as IConditionValue[];
        const value = item.value as IConditionValue;
        const index = fieldValues.findIndex(data => data === value);
        if (index > -1) {
          fieldValues.splice(index, 1);
        }
        break;
      }
      case 'checkbox': {
        const fieldValues = field.value as number[];
        const value = item.value as IOption;
        const index = fieldValues.findIndex(data => data === value.id);
        if (index > -1) {
          fieldValues.splice(index, 1);
        }
        break;
      }
      default: {
        Array.isArray(field.value) ? (field.value = []) : (field.value = '');
      }
    }
    this.updateCondition();
  }
  // 更新条件（URL复制问题）
  private updateCondition() {
    const search = this.tableInstance.fieldData.reduce((pre, next) => {
      const isEmpty = Array.isArray(next.value) ? next.value.length === 0 : typeTools.isNull(next.value);
      if (!isEmpty) {
        pre.push({
          id: next.id,
          value: next.value,
        });
      }
      return pre;
    }, []);
    this.handleSearchUpdate(search);
  }

  @Emit('filter-change')
  private handleClear() {
    this.tableInstance.panelKey = '';
    this.tableInstance.fieldData.forEach(item => {
      item.value = Array.isArray(item.value) ? [] : '';
    });
    this.handleSearchUpdate([], '');
  }

  @Emit('filter-update')
  private handleSearchUpdate(search?, panelKey?) {
    return {
      search,
      panelKey,
    };
  }
}
</script>
<style lang="scss" scoped>
.filter-tag {
  display: flex;
  padding: 16px 20px 8px 20px;
  border: 1px solid #dcdee5;
  border-bottom: 0;

  &-title {
    flex: 0 0 56px;
    line-height: 24px;
  }

  &-content {
    display: flex;
    flex-wrap: wrap;

    .tag {
      display: flex;
      align-items: center;
      justify-content: center;
      height: 24px;
      padding: 0 5px;
      margin: 0 0 8px 8px;
      cursor: pointer;
      background: #f0f1f5;
      border-radius: 2px;

      span {
        line-height: 1;
      }

      i {
        font-size: 16px;
      }

      .tag-value {
        max-width: 500px;
        overflow: hidden;
        color: #1e1d2d;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      &:hover {
        background: #e1ecff;

        i {
          color: #3a83ff;
        }
      }
    }

    .btn {
      margin-left: 16px;
      font-size: 12px;
    }
  }
}
</style>
