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

import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Input } from 'bk-magic-vue';

import $http from '../../../api';

import './ui-query.scss';

@Component
export default class UiQuery extends tsc<object> {
  @Prop({ type: Object, required: true }) activeFavorite: object;
  @Prop({ type: Boolean, required: true }) isFavoriteSearch: boolean;
  @Prop({ type: String, required: true }) keyword: string;

  searchFieldsList = []; // 表单展示字段
  cacheFieldsList = []; // 修改字段之前的缓存字段
  loading = false;
  isUpdateFavorite = false;
  favoriteKeyword = '';

  @Watch('activeFavorite', { immediate: true, deep: true })
  watchActiveFavorite(value) {
    this.isUpdateFavorite = true;
    this.favoriteKeyword = value?.params?.keyword || '*';
    const keyword = this.isFavoriteSearch ? this.favoriteKeyword : this.keyword;
    this.getSearchFieldsList(keyword, value?.params?.search_fields);
  }

  async getSearchFieldsList(keyword: string, fieldsList = []) {
    let newKeyword = keyword;
    if (!newKeyword) {
      newKeyword = '*';
    }
    this.loading = true;
    try {
      const res = await $http.request('favorite/getSearchFields', {
        data: { keyword: newKeyword },
      });
      this.searchFieldsList = res.data
        .filter(item => fieldsList.includes(item.name))
        .map(item => ({
          ...item,
          name: item.is_full_text_field
            ? `${window.mainComponent.$t('全文检索')}${item.repeat_count ? `(${item.repeat_count})` : ''}`
            : item.name,
          chName: item.name,
        }));
      this.cacheFieldsList = structuredClone(this.searchFieldsList); // 赋值缓存的展示字段
    } finally {
      this.loading = false;
    }
  }

  clearCondition() {
    for (const item of this.searchFieldsList) {
      item.value = '';
    }
    this.handleChangeValue();
  }

  handleChangeValue() {
    const cacheValueStr = this.cacheFieldsList.map(item => item.value).join(',');
    const searchValueStr = this.searchFieldsList.map(item => item.value).join(',');
    if (cacheValueStr === searchValueStr) {
      return;
    } // 鼠标失焦后判断每个值是否和缓存的一样 如果一样 则不请求
    this.cacheFieldsList = structuredClone(this.searchFieldsList); // 重新赋值缓存的展示字段
    const params = this.searchFieldsList
      .filter(item => Boolean(item.value))
      .map(item => ({
        value: item.value,
        pos: item.pos,
      }));
    $http
      .request('favorite/getGenerateQuery', {
        data: {
          keyword: this.isUpdateFavorite ? this.favoriteKeyword : this.keyword,
          params,
        },
      })
      .then(async res => {
        try {
          const { data } = await $http.request('favorite/checkKeywords', {
            data: { keyword: res.data },
          });
          this.$emit('updateKeyWords', res.data);
          this.$emit('isCanSearch', data.is_legal);
        } catch {
          this.$emit('isCanSearch', false);
        }
      })
      .catch(() => {
        this.$emit('isCanSearch', false);
      })
      .finally(() => {
        this.isUpdateFavorite = false;
      });
  }

  render() {
    return (
      <div
        class='ui-query-container'
        v-bkloading={{ isLoading: this.loading }}
      >
        {this.searchFieldsList.map(item => (
          <div
            key={item}
            class='query-item-box'
          >
            <div class='query-title'>
              <span>{item.name}</span>
              <span>{item.operator}</span>
            </div>
            <Input
              v-model={item.value}
              onBlur={this.handleChangeValue}
            />
          </div>
        ))}
      </div>
    );
  }
}
