/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { FormSpacePages, resolveSelectedSpaces } from 'monitor-common/utils/space-selection';

import type { ISpaceItem } from 'monitor-common/typings';

interface Props {
  clearable?: boolean;
  disabled?: boolean;
  extraOptions?: { id: number; name: string }[];
  showIdentifier?: boolean;
  value: number | string;
  onChange?: (value: number | string) => void;
}

/** Keep the scalar, clearable field contract used by configuration forms. */
@Component
export default class FormSpaceSelect extends tsc<Props> {
  @Prop({ type: [Number, String] }) value: Props['value'];
  @Prop({ type: Boolean }) disabled: boolean;
  @Prop({ type: Boolean, default: true }) clearable: boolean;
  @Prop({ type: Boolean, default: true }) showIdentifier: boolean;
  @Prop({ type: Array, default: () => [] }) extraOptions: Props['extraOptions'];
  pages = new FormSpacePages();
  selected: ISpaceItem | null = null;

  @Watch('value', { immediate: true })
  async resolveValue() {
    const value = this.value;
    this.selected = null;
    if (value == null || value === '' || Number(value) === 0) return;
    const rows = await resolveSelectedSpaces([value], [...this.pages.items, ...this.$store.getters.bizList]).catch(
      () => []
    );
    if (value === this.value) this.selected = rows[0] ?? null;
  }

  render() {
    const visible =
      this.selected && !this.pages.items.some(item => item.id === this.selected.id)
        ? [this.selected, ...this.pages.items]
        : this.pages.items;
    const options = [
      ...this.extraOptions,
      ...visible.map(item => ({
        id: item.id,
        name: this.showIdentifier
          ? `${item.text} (${item.space_type_id === 'bkcc' ? `#${item.id}` : item.space_id || item.space_code})`
          : item.text,
      })),
    ];
    if (this.value !== '' && this.value != null && !options.some(option => option.id === Number(this.value))) {
      options.unshift({ id: Number(this.value), name: String(this.value) });
    }
    return (
      <bk-select
        clearable={this.clearable}
        disabled={this.disabled}
        remote-method={(query: string) => this.pages.search(query)}
        scroll-loading={{ isLoading: this.pages.loading }}
        search-placeholder={this.$t('请输入 关键字')}
        value={this.value === '' ? '' : Number(this.value)}
        enable-scroll-load
        searchable
        onChange={value => {
          this.$emit('input', value);
          this.$emit('change', value);
        }}
        onScroll-end={() => this.pages.hasMore && this.pages.fetchPage()}
        onToggle={open => {
          this.$emit('toggle', open);
          if (open) void this.pages.search();
          else this.pages.reset();
        }}
      >
        {options.map(option => (
          <bk-option
            id={option.id}
            key={option.id}
            name={option.name}
          />
        ))}
        {(this.pages.failed || (this.pages.hasMore && this.pages.items.length < 10)) && (
          <bk-button
            slot='extension'
            text
            onClick={() => this.pages.retryOrNext()}
          >
            {this.$t(this.pages.failed ? '重试' : '加载更多')}
          </bk-button>
        )}
      </bk-select>
    );
  }
}
