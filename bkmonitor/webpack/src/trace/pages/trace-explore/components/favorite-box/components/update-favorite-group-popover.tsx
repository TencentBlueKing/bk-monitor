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
import { type PropType, computed, defineComponent, nextTick, onBeforeUnmount, onMounted, shallowRef, watch } from 'vue';

import { Message, Tag } from 'bkui-vue';
import _ from 'lodash';
import { bulkUpdateFavorite } from 'monitor-api/modules/model';
import tippy, { type SingleTarget } from 'tippy.js';
import { useI18n } from 'vue-i18n';

import { GROUP_ID_PERSONAL } from '../constants';
import useFavoriteType from '../hooks/use-favorite-type';
import useGroupList from '../hooks/use-group-list';
import CreateGroupExtend from './create-group-extends';
import { useAppStore } from '@store/modules/app';

import type { IFavoriteGroup } from '../types';

import './update-favorite-group-popover.scss';

export default defineComponent({
  props: {
    data: {
      type: Object as PropType<IFavoriteGroup['favorites']>,
    },
  },
  emits: ['show', 'hide'],
  setup(props, context) {
    const { t } = useI18n();
    const store = useAppStore();
    const favoriteType = useFavoriteType();
    const { editableGroupList: groupList, run: refreshGroupList } = useGroupList(favoriteType.value);

    const rootRef = shallowRef<HTMLElement>();
    const groupPanelRef = shallowRef<HTMLElement>();
    const newGroupName = shallowRef('');

    const currentGroupIdList = computed(() => {
      if (props.data.length < 1) {
        return [];
      }
      return _.uniq(props.data.map(item => item.group_id));
    });

    watch(groupList, () => {
      nextTick(() => {
        groupPanelRef.value.querySelector('.is-new-group')?.scrollIntoView();
      });
    });

    const handleUpdateGroup = async (groupId: null | number) => {
      await bulkUpdateFavorite({
        type: favoriteType.value,
        configs: props.data.map(item => ({
          id: item.id,
          name: item.name,
          group_id: groupId,
        })),
      });
      refreshGroupList();
      Message({
        theme: 'success',
        message: t('操作成功'),
      });
    };

    const handleCreateGroupSuccess = (groupName: string) => {
      newGroupName.value = groupName;
    };

    onMounted(() => {
      const tippyInstance = tippy(rootRef.value as SingleTarget, {
        content: groupPanelRef.value as any,
        trigger: 'mouseenter',
        placement: 'right-start',
        theme: 'light favorite-box-update-favorite-group-panel',
        arrow: false,
        interactive: true,
        offset: [0, 12],
        interactiveBorder: 30,
        hideOnClick: false,
        appendTo: 'parent',
        popperOptions: {
          modifiers: [
            {
              name: 'computeStyles',
              options: {
                adaptive: false, // 禁用自适应定位
              },
            },
            {
              name: 'flip',
              enabled: false, // 禁用自动翻转
            },
          ],
        },
        getReferenceClientRect: () => {
          console.log('rootRef.value.getBoundingClientRect() = ', rootRef.value.getBoundingClientRect());
          return rootRef.value.getBoundingClientRect();
        },
        onShown() {
          context.emit('show');
          newGroupName.value = '';
        },
        onHide() {
          context.emit('hide');
        },
      });

      onBeforeUnmount(() => {
        tippyInstance.hide();
        tippyInstance.destroy();
      });
    });

    return () => (
      <div class='favorite-box-update-favorite-group-popover'>
        <div
          ref={rootRef}
          style='display: flex; align-items: center;'
        >
          {t('移动至分组')}
          <i
            style='margin-left: auto'
            class='icon-monitor icon-arrow-right'
          />
        </div>
        <div ref={groupPanelRef}>
          <div class='group-wrapper'>
            {groupList.value.map(groupItem => {
              const isSingleGroup = currentGroupIdList.value.length === 1;
              if (isSingleGroup) {
                // 不是自己创建的不能移动到个人收藏分组
                if (groupItem.id === GROUP_ID_PERSONAL && props.data[0].create_user !== store.userName) {
                  return null;
                }
                // 分组没变
                if (groupItem.id === props.data[0].group_id) {
                  return null;
                }
              }

              const isNew = newGroupName.value === groupItem.name;

              return (
                <div
                  key={groupItem.id}
                  class={{
                    'group-item': true,
                    'is-new-group': isNew,
                  }}
                  onClick={() => handleUpdateGroup(groupItem.id)}
                >
                  {groupItem.name}
                  {groupItem.id === GROUP_ID_PERSONAL && (
                    <span style='color: rgb(151, 155, 165);'>（{t('仅个人可见')}）</span>
                  )}
                  {isNew && (
                    <Tag
                      style='margin-left: 4px'
                      size='small'
                      theme='warning'
                      type='filled'
                    >
                      new
                    </Tag>
                  )}
                </div>
              );
            })}
          </div>
          <div class='create-group'>
            <CreateGroupExtend onSuccess={handleCreateGroupSuccess} />
          </div>
        </div>
      </div>
    );
  },
});
