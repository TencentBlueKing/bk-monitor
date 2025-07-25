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

import { type PropType, computed, defineComponent, shallowRef, useTemplateRef, watch } from 'vue';

import { useStorage } from '@vueuse/core';
import { Checkbox, Input, Loading } from 'bkui-vue';
import _ from 'lodash';
import { useI18n } from 'vue-i18n';

import CreateGroupPopover from './components/create-group-popover';
import EditFavorite from './components/edit-favorite';
import GroupFavoriteSort from './components/group-favorite-sort';
import GroupManage from './components/group-manage/index';
import GroupTree from './components/group-tree/index';
import { VIEW_DATA_ID_KEY } from './constants';
import useEventFavoriteDataId from './hooks/use-event-favorite-data-id';
import useFavoriteType from './hooks/use-favorite-type';
import useGroupList from './hooks/use-group-list';

import type { IFavorite, IFavoriteGroup } from './types';

import './index.scss';

export type { IFavorite, IFavoriteGroup };

export { EditFavorite };

export default defineComponent({
  name: 'FavoriteBox',
  props: {
    type: {
      type: String as PropType<IFavorite>,
      required: true,
    },
    dataId: {
      type: String,
      default: '',
    },
    defaultFavoriteId: {
      type: Number,
      default: null,
    },
  },
  emits: ['openBlank', 'change', 'close'],
  setup(props, context) {
    const { t } = useI18n();
    const {
      loading: isGroupListLoading,
      data: groupList,
      wholeFavoriteList,
      allFavoriteList,
      run: refreshGroupList,
    } = useGroupList(props.type);
    const favoriteType = useFavoriteType();
    const eventFavoriteDataId = useEventFavoriteDataId();

    const viewDataId = useStorage(VIEW_DATA_ID_KEY, false);

    const groupTreeRef = useTemplateRef<any>('groupTreeRef');
    const favoritSelectedId = shallowRef<number>();
    const favoriteSearchKey = shallowRef('');
    const isShowGroupManage = shallowRef(false);
    const isAllExpaned = shallowRef(false);

    const isEventFilterDataId = computed(() => props.type === 'event');
    if (isEventFilterDataId.value) {
      eventFavoriteDataId.value = props.dataId;
    }

    watch(
      () => props.type,
      () => {
        favoriteType.value = props.type;
      },
      {
        immediate: true,
      }
    );

    watch(favoritSelectedId, () => {
      context.emit(
        'change',
        _.find(wholeFavoriteList.value, item => item.id === favoritSelectedId.value)
      );
    });

    watch(wholeFavoriteList, () => {
      if (props.defaultFavoriteId) {
        favoritSelectedId.value = props.defaultFavoriteId;
      }
    });

    const handleShowGroupManage = () => {
      isShowGroupManage.value = true;
    };

    const handleGroupManageClose = () => {
      isShowGroupManage.value = false;
    };

    const handleExpandAll = (value: boolean) => {
      groupTreeRef.value?.expandAll(value);
      isAllExpaned.value = value;
    };

    const handleFavoriteOpenBlank = (favoriteData: IFavoriteGroup['favorites'][number]) => {
      context.emit('openBlank', favoriteData, props.type);
    };

    const handleClose = () => {
      context.emit('close');
    };

    context.expose({
      refreshGroupList,
      getGroupList: () => groupList.value,
      // 不经过过滤条件
      getWholeFavoriteList: () => wholeFavoriteList.value,
      // 经过过滤
      getFavoriteList: () => allFavoriteList.value,
    });

    return () => (
      <div class='bk-monitor-favorite-box'>
        <div class='header-wrapper'>
          <span
            class='icon-monitor icon-gongneng-shouqi'
            onClick={handleClose}
          />
          <div style='margin-left: 8px'>{t('收藏夹')}</div>
          <div class='number-tag'>{groupList.value.length}</div>
          <div class='extend-action'>
            <span
              class='icon-monitor icon-shezhi1'
              v-bk-tooltips={t('收藏管理')}
              onClick={handleShowGroupManage}
            />
          </div>
        </div>
        <div class='favorite-wrapper'>
          <div class='favorite-search'>
            <Input
              v-model={favoriteSearchKey.value}
              placeholder={t('搜索收藏名')}
            />
          </div>
          <div class='favorite-action'>
            {isEventFilterDataId.value && <Checkbox v-model={viewDataId.value}>{t('仅查看当前数据 ID')}</Checkbox>}
            <CreateGroupPopover style='margin-left: auto'>
              <i class='icon-monitor icon-xinjianwenjianjia' />
            </CreateGroupPopover>
            {isAllExpaned.value ? (
              <span
                style='margin-left: 12px'
                class='icon-monitor icon-zhankai-2'
                v-bk-tooltips={t('全部收起')}
                onClick={() => handleExpandAll(false)}
              />
            ) : (
              <span
                style='margin-left: 12px'
                class='icon-monitor icon-shouqi3'
                v-bk-tooltips={t('全部展开')}
                onClick={() => handleExpandAll(true)}
              />
            )}
            <GroupFavoriteSort style='margin-left: 12px' />
          </div>
        </div>
        <Loading
          style='height: calc(100% - 117px)'
          loading={isGroupListLoading.value}
        >
          <GroupTree
            ref='groupTreeRef'
            v-model={favoritSelectedId.value}
            favoriteSearch={favoriteSearchKey.value}
            type={props.type}
            onOpenBlank={handleFavoriteOpenBlank}
          />
          {isShowGroupManage.value && (
            <GroupManage
              type={props.type}
              onClose={handleGroupManageClose}
            />
          )}
        </Loading>
      </div>
    );
  },
});
