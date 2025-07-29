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
import { computed, defineComponent, shallowRef, watch } from 'vue';

import { Exception } from 'bkui-vue';
import _ from 'lodash';
import { useI18n } from 'vue-i18n';

import useGroupList from '../../hooks/use-group-list';
import RenderFavorite from './components/render-favorite/index';
import RenderGroupInfo from './components/render-group-info';

import type { IFavoriteGroup } from '../../types';

import './index.scss';

export default defineComponent({
  name: 'GroupTree',
  props: {
    type: String,
    favoriteSearch: String,
    modelValue: Number,
  },
  emits: ['change', 'update:modelValue', 'openBlank'],
  setup(props, context) {
    const { data: groupList, allFavoriteList } = useGroupList(props.type);
    const { t } = useI18n();

    const activeFavoriteId = shallowRef(0);
    const renderGroupList = shallowRef([...groupList.value]);

    const expandGroupMap = shallowRef<Record<number, boolean>>({
      0: true,
    });

    const activeFavorite = computed(() => {
      if (!activeFavoriteId.value) {
        return undefined;
      }
      return _.find(allFavoriteList.value, item => item.id === activeFavoriteId.value);
    });

    const calcRenderGroupList = _.throttle(() => {
      const keyWord = props.favoriteSearch.toLocaleLowerCase().trim();
      if (!keyWord) {
        renderGroupList.value = [...groupList.value];
        return;
      }
      renderGroupList.value = groupList.value.reduce((result, groupItem) => {
        const favoriteList = _.filter(
          groupItem.favorites,
          favoriteItem => favoriteItem.name.toLocaleLowerCase().indexOf(keyWord) > -1
        );
        if (favoriteList.length > 0) {
          result.push({
            ...groupItem,
            favorites: favoriteList,
          });
        }

        return result;
      }, []);
    }, 300);

    watch(
      () => props.modelValue,
      () => {
        activeFavoriteId.value = props.modelValue;
      },
      {
        immediate: true,
      }
    );

    watch(
      () => [groupList.value, props.favoriteSearch],
      () => {
        calcRenderGroupList();
      },
      {
        immediate: true,
      }
    );

    const triggerChange = () => {
      context.emit('change', activeFavoriteId.value);
      context.emit('update:modelValue', activeFavoriteId.value);
    };

    const handleToogleGroupExpand = (expaned: boolean, groupId: number) => {
      const latestExpandGroupMap = { ...expandGroupMap.value };
      latestExpandGroupMap[groupId] = expaned;
      expandGroupMap.value = latestExpandGroupMap;
    };

    const handleSelectCreateGroup = () => {
      activeFavoriteId.value = undefined;
      triggerChange();
    };

    const handleFavoriteSelect = (favoriteData: IFavoriteGroup['favorites'][number]) => {
      activeFavoriteId.value = favoriteData.id;
      triggerChange();
    };
    const handleFavoriteOpenBlank = (favoriteData: IFavoriteGroup['favorites'][number]) => {
      context.emit('openBlank', favoriteData);
    };

    context.expose({
      expandAll(expanded: boolean) {
        if (expanded) {
          expandGroupMap.value = renderGroupList.value.reduce<Record<number, boolean>>((result, item) => {
            return Object.assign(result, {
              [item.id]: true,
            });
          }, {});
        } else {
          expandGroupMap.value = {};
        }
      },
    });

    return () => {
      const renderGroup = (groupData: IFavoriteGroup) => {
        const isFixedSelectedFavorite =
          !expandGroupMap.value[groupData.id] && activeFavorite.value && activeFavorite.value.group_id === groupData.id;

        return (
          <div
            key={groupData.name}
            class='favorite-group-item'
          >
            <RenderGroupInfo
              data={groupData}
              expanded={expandGroupMap.value[groupData.id]}
              fixedSelectedFavorite={isFixedSelectedFavorite}
              onToggleExpand={(value: boolean) => handleToogleGroupExpand(value, groupData.id)}
            />
            <div class='favorite-wrapper'>
              {expandGroupMap.value[groupData.id] &&
                groupData.favorites.map(favoriteItem => (
                  <div key={favoriteItem.id}>
                    <RenderFavorite
                      class={{
                        'is-active': activeFavoriteId.value === favoriteItem.id,
                      }}
                      data={favoriteItem}
                      onOpenBlank={handleFavoriteOpenBlank}
                      onSelected={() => handleFavoriteSelect(favoriteItem)}
                    />
                  </div>
                ))}
              {isFixedSelectedFavorite && (
                <RenderFavorite
                  class='is-active'
                  data={activeFavorite.value}
                  onOpenBlank={handleFavoriteOpenBlank}
                />
              )}
            </div>
          </div>
        );
      };
      return (
        <div class='favorite-group-tree'>
          <div
            style='margin-bottom: 2px;'
            class='favorite-group-split-line'
          />
          <div
            class={{
              'favorite-create': true,
              'is-active': !activeFavoriteId.value,
            }}
            onClick={handleSelectCreateGroup}
          >
            <i class='icon-monitor icon-xinjiansuo' />
            {t('新建检索')}
          </div>
          <div
            style='margin-top: 2px; margin-bottom: 8px;'
            class='favorite-group-split-line'
          />
          <div class='favorite-group-wrapper'>
            {renderGroupList.value.map(renderGroup)}
            {renderGroupList.value.length < 1 && (
              <Exception
                description={t('搜索为空')}
                scene='part'
                type='search-empty'
              />
            )}
          </div>
        </div>
      );
    };
  },
});
