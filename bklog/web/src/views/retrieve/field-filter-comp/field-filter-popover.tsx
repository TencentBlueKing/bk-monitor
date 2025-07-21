/*
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
 */

import { Component, Prop, Emit, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './field-filter-popover.scss';

@Component
export default class FieldAnalysis extends tsc<object> {
  @Prop({ default: false, type: Boolean }) value: boolean;

  polymerizableCache = null;
  fieldTypeCache = null;
  polymerizable = '0'; // 可聚合 0 不限 1 聚合 2 不可聚合
  fieldType = 'any';
  fieldTypeList = ['any', 'number', 'keyword', 'text', 'date', '__virtual__'];
  fieldTypeMap = {
    __virtual__: {
      icon: 'bklog-icon bklog-ext',
      name: window.mainComponent.$t('虚拟字段'),
    },
    any: {
      icon: 'bk-icon icon-check-line',
      name: window.mainComponent.$t('不限'),
    },
    date: {
      icon: 'bk-icon icon-clock',
      name: window.mainComponent.$t('时间'),
    },
    date_nanos: {
      icon: 'bk-icon icon-clock',
      name: window.mainComponent.$t('时间'),
    },
    keyword: {
      icon: 'bklog-icon bklog-string',
      name: window.mainComponent.$t('字符串'),
    },
    number: {
      icon: 'bklog-icon bklog-number',
      name: window.mainComponent.$t('数字'),
    },
    text: {
      icon: 'bklog-icon bklog-text',
      name: window.mainComponent.$t('文本'),
    },
  };

  get showFieldTypeList() {
    if (this.polymerizable === '1')
      return this.fieldTypeList.filter((item) => item !== 'date');
    return this.fieldTypeList;
  }

  @Watch('$route.params.indexId')
  watchRouteIndexID() {
    // 切换索引集重置状态
    this.polymerizable = '0';
    this.fieldType = 'any';
  }
  @Watch('value')
  watchValue(val: boolean) {
    if (val) {
      this.polymerizableCache = this.polymerizable;
      this.fieldTypeCache = this.fieldType;
    } else {
      this.polymerizable = this.polymerizableCache;
      this.fieldType = this.fieldTypeCache;
    }
  }

  @Emit('closePopover')
  emitClosePopover() {
    return;
  }
  @Emit('confirm')
  emitConfirm() {
    return {
      fieldType: this.fieldType,
      polymerizable: this.polymerizable,
    };
  }

  handleConfirm() {
    this.polymerizableCache = this.polymerizable;
    this.fieldTypeCache = this.fieldType;
    this.emitConfirm();
    this.emitClosePopover();
  }
  handleCancel() {
    this.emitClosePopover();
  }

  render() {
    return (
      <div class="filter-popover-content">
        <div class="title">{this.$t('是否可聚合')}</div>
        <bk-radio-group class="king-radio-group" v-model={this.polymerizable}>
          <bk-radio value="0">{this.$t('不限')}</bk-radio>
          <bk-radio value="1">{this.$t('是')}</bk-radio>
          <bk-radio value="2">{this.$t('否')}</bk-radio>
        </bk-radio-group>
        <div class="title">{this.$t('字段类型')}</div>
        <div class="bk-button-group">
          {this.showFieldTypeList.map((item) => (
            <bk-button
              class={this.fieldType === item ? 'is-selected' : ''}
              onClick={() => (this.fieldType = item)}
              size="small"
            >
              <div class="custom-button">
                <span
                  class={[
                    'field-filter-option-icon',
                    item === 'any' ? '' : this.fieldTypeMap[item].icon,
                  ]}
                ></span>
                <span class="bk-option-name">
                  {this.fieldTypeMap[item].name}
                </span>
              </div>
            </bk-button>
          ))}
        </div>
        <div class="button-container">
          <bk-button
            class="king-button mr10"
            onClick={() => this.handleConfirm()}
            size="small"
            theme="primary"
          >
            {this.$t('确定')}
          </bk-button>
          <bk-button
            class="king-button"
            onClick={() => this.handleCancel()}
            size="small"
          >
            {this.$t('取消')}
          </bk-button>
        </div>
      </div>
    );
  }
}
