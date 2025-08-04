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
    :class="['item', { 'is-hover': isHoverStatus }]"
    @mouseenter="handleMouseEnter"
    @mouseleave="handleMouseLeave"
  >
    <div class="item-title">
      <span>{{ title }}</span>
      <i
        v-if="isHoverStatus"
        class="icon-monitor icon-mc-close"
        @click="handleClose"
      />
    </div>
    <div class="item-content">
      <slot>
        <bk-input
          v-if="['textarea', 'text'].includes(type)"
          :type="type"
          :value="value"
          :rows="rows"
          @input="handleUpdateValue"
        />
        <bk-checkbox-group
          v-else-if="type === 'checkbox'"
          class="item-content-checkbox"
          :value="value"
          @change="handleUpdateValue"
        >
          <bk-checkbox
            v-for="item in options"
            :key="item.id"
            :value="item.id"
          >
            {{ item.name }}
          </bk-checkbox>
        </bk-checkbox-group>
        <bk-select
          v-else-if="type === 'select'"
          ref="select"
          :value="value"
          :popover-options="{ boundary: 'window' }"
          :multiple="multiple"
          searchable
          :remote-method="handleSelectSearch"
          @change="handleSelectChange"
        >
          <bk-option
            v-for="item in sortOptions"
            :id="item.id"
            :key="item.id"
            :name="item.name"
          >
            {{ item.name }}
          </bk-option>
        </bk-select>
        <bk-cascade
          v-else-if="type === 'cascade'"
          ref="cascade"
          :value="value"
          :list="cascadeOptions"
          clearable
          :popover-options="{ boundary: 'window' }"
          check-any-level
          :scroll-width="cascaderScrollWidth"
          :multiple="multiple"
          filterable
          @toggle="handleCascadeToggle"
          @search="handleCascadeSearch"
          @change="handleCascadeChange"
        />
        <div v-else-if="type === 'condition'">
          <div
            v-for="(data, index) in conditionsData"
            :key="index"
            :class="['item-content-condition', { mb10: index < conditionsData.length - 1 }]"
          >
            <div class="condition-left">
              <!-- 条件 -->
              <bk-select
                v-model="data.condition"
                class="condition-select"
                :popover-options="{ boundary: 'window' }"
                @change="handleConditionChange"
              >
                <bk-option
                  v-for="item in conditions"
                  :id="item.id"
                  :key="item.id"
                  :name="item.name"
                >
                  {{ item.name }}
                </bk-option>
              </bk-select>
              <!-- 值 -->
              <bk-input
                v-model="data.value"
                class="condition-input"
                type="number"
                @change="handleConditionChange"
              />
            </div>
            <!-- 增/减 -->
            <div class="condition-right">
              <i
                class="icon-monitor icon-jia ml5"
                @click="handleAddCondition(index)"
              />
              <i
                :class="['icon-monitor icon-jian ml5', { disabled: iconDisabled }]"
                @click="handleDeleteCondition(index)"
              />
            </div>
          </div>
        </div>
      </slot>
    </div>
  </div>
</template>
<script lang="ts">
import { Component, Emit, Model, Prop, Ref, Vue, Watch } from 'vue-property-decorator';

import { sort } from 'monitor-common/utils/utils.js';

import type { FieldValue, IConditionValue, InputType, IOption } from '../performance-type';

@Component({ name: 'filter-panel-item' })
export default class PanelItem extends Vue {
  @Ref('cascade') readonly cascadeRef: any;
  @Ref('select') readonly selectRef: any;
  @Model('update-value', { type: [String, Number, Array] }) readonly value: FieldValue;
  @Prop({ default: 'title' }) readonly title: string;
  @Prop({ default: 'select', type: String }) readonly type: InputType;
  @Prop({ default: false }) readonly disabled: boolean;
  @Prop({ default: false }) readonly multiple: boolean;
  @Prop({ default: false }) readonly allowEmpt: boolean;
  @Prop({ default: () => [], type: Array }) readonly options: IOption[];
  @Prop({
    default: () => ({
      list: [],
      active: '',
    }),
  })
  readonly conditions: IOption[];

  hover = false;
  // 同一字段支持多个条件（eg：CPU使用率 > 80 且 CPU使用率 < 90）
  conditionsData: IConditionValue[] = [
    {
      condition: undefined,
      value: undefined,
    },
  ];

  // textarea最小高度
  minRows = 3;
  // textarea最大高度
  maxRows = 6;

  cascadeKeyWord = '';

  get cascadeOptions() {
    const temp = [...this.options];
    if (this.cascadeKeyWord && this.cascadeRef?.searchList?.length) {
      temp.unshift({ id: '__all__', name: this.$t('- 全部 -'), children: [] });
    }
    return temp;
  }

  // 排序options
  get sortOptions() {
    if (Array.isArray(this.options)) {
      this.options.forEach(item => {
        if (Array.isArray(item.children)) {
          item.children = sort(item.children, 'name');
        }
      });
      let temp = sort(this.options, 'name');
      // 处理空选项
      if (this.allowEmpt) {
        temp = [temp.find(set => set.id === '__empt__'), ...temp.filter(set => set.id !== '__empt__')].filter(
          item => !!item
        );
      }
      // 添加搜索全选选项
      this.multiple && temp.length && temp.unshift({ id: '__all__', name: this.$t('- 全部 -') });
      return temp;
    }
    return this.options;
  }

  // 当前textarea高度
  get rows() {
    if (this.type === 'textarea') {
      const valueLength = `${this.value}`.split('\n').length;
      return valueLength > this.minRows ? Math.min(valueLength, this.maxRows) : this.minRows;
    }
    return 1;
  }

  get isHoverStatus() {
    return this.hover && !this.disabled;
  }

  get iconDisabled() {
    return this.conditionsData.length === 1;
  }

  get cascaderScrollWidth() {
    /** 搜索并且展开的面板数只有一个时，面板宽度设置为320 */
    return this.cascadeKeyWord && this.cascadeRef?.popoverWidth === 1 ? 320 : 160;
  }

  @Watch('value', { immediate: true })
  handleValueChange(v) {
    if (this.type === 'condition') {
      v.length === 0
        ? (this.conditionsData = [
            {
              condition: undefined,
              value: undefined,
            },
          ])
        : (this.conditionsData = v);
    } else if (this.type === 'cascade') {
      this.$nextTick(() => {
        this.cascadeRef?.updateSelected();
      });
    }
  }

  // @Watch('options', { deep: true, immediate: true })
  // optionsChange() {
  //   this.localOptions = deepClone(this.options)
  // }

  @Emit('close')
  @Emit('update-value')
  handleClose() {
    return Array.isArray(this.value) ? [] : '';
  }

  handleMouseEnter() {
    this.hover = true;
  }

  handleMouseLeave() {
    this.hover = false;
  }

  @Emit('update-value')
  handleUpdateValue(v) {
    if (typeof v === 'string') {
      return v
        .trim()
        .split('\n')
        .map(item => item.trim())
        .filter(item => !!item)
        .join('\n');
    }
    return v;
  }

  // 添加条件
  handleAddCondition(index: number) {
    this.conditionsData.splice(index + 1, 0, {
      condition: undefined,
      value: undefined,
    });
  }

  // 删除条件
  handleDeleteCondition(index: number) {
    if (this.iconDisabled) return;
    this.conditionsData.splice(index, 1);
  }

  // 条件值变更事件
  @Emit('update-value')
  handleConditionChange() {
    return this.conditionsData;
  }

  // select搜索筛选
  handleSelectSearch(keyWord) {
    (this?.selectRef?.options || []).forEach(option => {
      option.unmatched = !option.name.includes(keyWord);
      if (option.id === '__all__') option.unmatched = false;
    });
  }
  /**
   * @description: 下拉选中全部操作
   * @param {*} list
   * @return {*}
   */
  handleSelectChange(list) {
    if (list.includes('__all__')) {
      list = (this?.selectRef?.options || [])
        .filter(item => item.id !== '__all__' && !item.unmatched)
        .map(item => item.id);
      this.$nextTick(() => {
        this.selectRef.setSelectedOptions();
        this.selectRef.close();
      });
    }
    this.handleUpdateValue(list);
  }
  /**
   * @description: 级联选择器搜索
   * @param {*} keyWord 搜索关键词
   * @return {*}
   */
  async handleCascadeSearch(keyWord: string) {
    this.cascadeKeyWord = keyWord;
    await this.$nextTick();
    if (keyWord) this.cascadeRef.filterableStatus = true;
    const { searchList } = this.cascadeRef;
    if (searchList.length) {
      searchList.unshift({ id: ['__all__'], disabled: false, isSelected: false, name: this.$t('- 全部 -') });
    }
    this.cascadeRef.searchList = searchList;
  }
  /**
   * @description: 级联值更新
   * @param {*} val 更新值
   * @return {*}
   */
  handleCascadeChange(val: any[]) {
    const allIndex = val.findIndex(item => item.includes('__all__'));
    if (allIndex >= 0) {
      val = [];

      for (const item of this.cascadeRef.searchList) {
        if (!item.id.includes('__all__')) {
          val.push(item.id);
        }
      }
      this.cascadeRef.searchContent = '';
      this.cascadeRef.filterableStatus = false;
      this.cascadeKeyWord = '';
    }
    this.handleUpdateValue(val);
  }
  handleCascadeToggle(val: boolean) {
    if (!val) this.cascadeKeyWord = '';
  }
}
</script>
<style lang="scss" scoped>
.item {
  padding: 0 8px 8px 12px;

  &.is-hover {
    background: #f5f6fa;
    border-radius: 2px;
  }

  &-title {
    display: flex;
    justify-content: space-between;
    font-size: 12px;

    span {
      line-height: 20px;
    }

    i {
      margin-right: -4px;
      font-size: 16px;
      font-weight: bold;
      color: #ff5656;
      cursor: pointer;
    }
  }

  &-content {
    margin-top: 6px;

    :deep(.bk-select) {
      background: #fff;
    }

    :deep(.bk-cascade) {
      background: #fff;
    }

    &-checkbox {
      display: flex;
      justify-content: space-between;

      :deep(.bk-checkbox-text) {
        font-size: 12px;
      }
    }

    &-condition {
      display: flex;
      justify-content: space-between;

      .condition-left {
        display: flex;
        flex: 1;
        justify-content: space-between;

        .condition-select {
          flex: 1;
          margin-right: 8px;
        }

        .condition-input {
          flex: 1;
        }
      }

      .condition-right {
        display: flex;
        flex-basis: 50px;
        align-items: center;
        font-size: 20px;
        color: #979ba5;

        i {
          cursor: pointer;

          &.disabled {
            color: #c4c6cc;
            cursor: not-allowed;
          }
        }
      }
    }
  }
}
</style>
