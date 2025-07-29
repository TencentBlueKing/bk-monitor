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

import { type UnwrapRef, computed, defineComponent, shallowRef, watch } from 'vue';

import { Exception, Input, Loading } from 'bkui-vue';
import _ from 'lodash';
import { useI18n } from 'vue-i18n';

import { GROUP_ID_ALL, GROUP_ID_NOT, GROUP_ID_PERSONAL } from '../../../constants';
import useGroupList from '../../../hooks/use-group-list';
import CreateGroupPopover from '../../create-group-popover';

import './render-group-list.scss';

export default defineComponent({
  props: {
    type: String,
  },
  emits: ['change'],
  setup(props, context) {
    const { loading: isListLoading, data: groupList, allFavoriteList } = useGroupList(props.type);

    const { t } = useI18n();

    const activeGroupId = shallowRef<null | number | string>(GROUP_ID_ALL);
    const groupSearchKey = shallowRef('');

    const notGroupByFavoriteList = computed(
      () => _.find(groupList.value, item => item.id === GROUP_ID_NOT)?.favorites || []
    );

    const personGroupFavoriteList = computed(
      () => _.find(groupList.value, item => item.id === GROUP_ID_PERSONAL)?.favorites || []
    );

    const allCustomGroupList = computed(() => _.filter(groupList.value, item => Boolean(item.id)));

    const renderGroupList = shallowRef([...allCustomGroupList.value]);

    const calcRenderGroupList = _.throttle(() => {
      const keyWord = groupSearchKey.value.toLocaleLowerCase().trim();
      if (!keyWord) {
        renderGroupList.value = [...allCustomGroupList.value];
        return;
      }
      renderGroupList.value = _.filter(
        allCustomGroupList.value,
        item => item.name.toLocaleLowerCase().indexOf(keyWord) > -1
      );
    }, 300);

    const triggerChange = () => {
      context.emit('change', activeGroupId.value);
    };

    watch(
      groupList,
      () => {
        groupSearchKey.value = '';
        calcRenderGroupList();
        triggerChange();
      },
      {
        immediate: true,
      }
    );

    watch(groupSearchKey, () => {
      calcRenderGroupList();
    });

    const handleClick = (id: UnwrapRef<typeof activeGroupId>) => {
      activeGroupId.value = id;
      triggerChange();
    };

    return () => (
      <Loading loading={isListLoading.value}>
        <div class='favorite-box-group-manage-list'>
          <div
            class={{
              'group-item': true,
              'is-active': activeGroupId.value === GROUP_ID_ALL,
            }}
            onClick={() => handleClick(GROUP_ID_ALL)}
          >
            <i class='icon-monitor icon-all group-flag' />
            <div class='group-name'>{t('全部收藏')}</div>
            <div class='group-sub-count'>{allFavoriteList.value.length}</div>
          </div>
          <div
            class={{
              'group-item': true,
              'is-active': activeGroupId.value === GROUP_ID_NOT,
            }}
            onClick={() => handleClick(GROUP_ID_NOT)}
          >
            <i class='icon-monitor icon-mc-file-close group-flag' />
            <div class='group-name'>{t('未分组')}</div>
            <div class='group-sub-count'>{notGroupByFavoriteList.value.length}</div>
          </div>
          <div
            class={{
              'group-item': true,
              'is-active': activeGroupId.value === GROUP_ID_PERSONAL,
            }}
            onClick={() => handleClick(GROUP_ID_PERSONAL)}
          >
            <i class='icon-monitor icon-file-personal group-flag' />
            <div class='group-name'>{t('个人收藏')}</div>
            <div class='group-sub-count'>{personGroupFavoriteList.value.length}</div>
          </div>
          <div class='line' />
          <div class='group-filter'>
            <CreateGroupPopover>
              <div class='create-btn'>
                <i class='icon-monitor icon-a-1jiahao' />
              </div>
            </CreateGroupPopover>
            <Input
              v-model={groupSearchKey.value}
              placeholder={t('搜索分组名')}
            />
          </div>
          <div class='group-custom-wrapper'>
            {renderGroupList.value.map(groupItem => (
              <div
                key={groupItem.id}
                class={{
                  'group-item': true,
                  'is-active': activeGroupId.value === groupItem.id,
                }}
                onClick={() => handleClick(groupItem.id)}
              >
                <i class='icon-monitor icon-mc-file-close group-flag' />
                <div
                  class='group-name'
                  v-bk-tooltips={groupItem.name}
                >
                  {groupItem.name}
                </div>
                <div class='group-sub-count'>{groupItem.favorites.length}</div>
              </div>
            ))}
            {groupSearchKey.value && renderGroupList.value.length < 1 && (
              <Exception
                description={t('搜索为空')}
                scene='part'
                type='search-empty'
              />
            )}
          </div>
        </div>
      </Loading>
    );
  },
});
