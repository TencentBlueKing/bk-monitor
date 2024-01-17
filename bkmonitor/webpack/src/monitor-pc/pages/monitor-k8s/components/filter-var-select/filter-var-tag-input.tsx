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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from '../../../../../monitor-common/utils/utils';

import './filter-var-tag-input.scss';

interface IListItem {
  id: string;
  name: string;
}

interface IProps {
  list?: IListItem[];
  multiple?: boolean;
  clearable?: boolean;
}

interface IEvents {
  onChange?: string | string[];
}

@Component
export default class FilterVarTagInput extends tsc<IProps, IEvents> {
  @Prop({ type: [String, Array], default: '' }) value: string | string[];
  @Prop({ default: () => [], type: Array }) list: IListItem[];
  @Prop({ default: false, type: Boolean }) multiple: boolean;
  @Prop({ default: true, type: Boolean }) clearable: boolean;

  localValue: string[] = [];

  created() {
    if (this.value) {
      this.localValue = Array.isArray(this.value) ? this.value : [this.value];
    }
  }

  // 粘贴条件时触发(tag-input)
  handlePaste(v) {
    if (this.multiple) {
      const SYMBOL = ';';
      /** 支持 空格 | 换行 | 逗号 | 分号 分割的字符串 */
      const valList = `${v}`.replace(/(\s+)|([,;])/g, SYMBOL)?.split(SYMBOL);
      const ret = [];
      valList.forEach(val => {
        !this.localValue.some(v => v === val) && val !== '' && this.localValue.push(val);
        if (!this.list?.some(item => item.id === val)) {
          ret.push({
            id: val,
            name: val
          });
        }
      });
      setTimeout(() => this.handleChange(this.localValue), 50);
      return ret;
    }
    this.localValue = [v];
    setTimeout(() => this.handleChange(this.localValue), 50);
    return [{ id: v, name: v }];
  }

  @Debounce(300)
  handleChange(v) {
    if (this.multiple) {
      this.$emit('change', v);
    } else {
      this.$emit('change', v?.[0] || '');
    }
  }

  render() {
    return (
      <span class='filter-var-tag-input'>
        <bk-tag-input
          v-model={this.localValue}
          list={this.list}
          trigger='focus'
          has-delete-icon={this.clearable}
          clearable={this.clearable}
          allow-create
          allow-auto-match
          max-data={this.multiple ? -1 : 1}
          placeholder={this.$t('输入')}
          paste-fn={this.handlePaste}
          on-change={this.handleChange}
        ></bk-tag-input>
      </span>
    );
  }
}
