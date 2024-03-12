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
import { computed, defineComponent, PropType, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Button, Input, Popover, Radio } from 'bkui-vue';
import { EnlargeLine, Transfer } from 'bkui-vue/lib/icon';

import { IFavList } from '../typings/favorite-list';

import './favorite-list.scss';

export default defineComponent({
  name: 'FavoriteList',
  props: {
    favoriteList: {
      type: Array as PropType<IFavList.favGroupList[]>,
      default: () => []
    }
  },
  emits: [],
  setup(props) {
    const { t } = useI18n();

    const popoverGroupRef = ref<InstanceType<typeof Popover>>();
    const popoverSortRef = ref<InstanceType<typeof Popover>>();
    const sortType = ref('asc');
    const groupSortList = [
      // 排序展示列表
      {
        name: t('按名称 A - Z 排序'),
        id: 'asc'
      },
      {
        name: t('按名称 Z - A 排序'),
        id: 'desc'
      },
      {
        name: t('按更新时间排序'),
        id: 'update'
      }
    ];

    const searchVal = ref('');
    const filterFavoriteList = ref([]);
    const favoriteCount = computed(() =>
      props.favoriteList.reduce((pre: number, cur) => ((pre += cur.favorites.length), pre), 0)
    );
    watch(
      () => props.favoriteList,
      () => handleSearchFavorite()
    );

    // const isNewSearch = computed(() => !searchVal.value);

    function handleSearchFavorite() {
      if (!searchVal.value) {
        filterFavoriteList.value = props.favoriteList;
      } else {
      }
    }

    const isShowManageDialog = ref(false);

    return {
      popoverSortRef,
      popoverGroupRef,
      searchVal,
      favoriteCount,
      filterFavoriteList,
      sortType,
      groupSortList,
      handleSearchFavorite,
      isShowManageDialog
    };
  },
  render() {
    return (
      <div class='favorite-list-component'>
        <div class='header-container'>
          <div class='search-title jsac'>
            <span class='title'>
              {this.$t('收藏查询')}
              <span class='favorite-number'>{this.favoriteCount}</span>
            </span>
            <span
              class='icon-monitor icon-mc-wholesale-editor'
              onClick={() => (this.isShowManageDialog = true)}
            ></span>
          </div>
          <div class='search-tools jsac'>
            <Input
              type='search'
              v-model={this.searchVal}
              onEnter={this.handleSearchFavorite}
              placeholder={this.$t('搜索收藏名')}
            ></Input>
            <div class='tools jsac'>
              <Popover
                ref='popoverGroupRef'
                trigger='click'
                theme='light'
                placement='bottom-start'
                ext-cls='new-group-popover'
              >
                {{
                  default: () => <span class='icon-monitor icon-jia'></span>,
                  content: () => (
                    <div class='operate-button'>
                      <Button text>{this.$t('确定')}</Button>
                      <span>{this.$t('取消')}</span>
                    </div>
                  )
                }}
              </Popover>
              <Popover
                ref='popoverSortRef'
                trigger='click'
                theme='light'
                placement='bottom-start'
                ext-cls='sort-group-popover'
              >
                {{
                  default: () => (
                    <div class='icon-box'>
                      <Transfer class='icon-monitor sort' />
                    </div>
                  ),
                  content: () => (
                    <div>
                      <span style={{ fontSize: '14px', marginTop: '8px' }}>{this.$t('收藏排序')}</span>
                      <Radio.Group
                        v-model={this.sortType}
                        class='sort-group-container'
                      >
                        {this.groupSortList.map(item => (
                          <Radio label={item.id}>{item.name}</Radio>
                        ))}
                      </Radio.Group>
                      <div class='operate-button'>
                        <Button theme='primary'>{this.$t('确定')}</Button>
                        <Button>{this.$t('取消')}</Button>
                      </div>
                    </div>
                  )
                }}
              </Popover>
            </div>
          </div>
        </div>
        <div class='new-search'>
          <EnlargeLine class='icon' />
          <span>{this.$t('新检索')}</span>
        </div>
        <div class='group-container'></div>
      </div>
    );
  }
});
