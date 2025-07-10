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
import { defineComponent, type PropType, onMounted, shallowRef, onBeforeUnmount, computed } from 'vue';
import { useI18n } from 'vue-i18n';

import { Message } from 'bkui-vue';
import { createFavorite, updateFavorite, destroyFavorite } from 'monitor-api/modules/model';
import tippy, { type SingleTarget, type Instance } from 'tippy.js';

import EditFavorite from '../../../../components/edit-favorite';
import useFavoriteType from '../../../../hooks/use-favorite-type';
import useGroupList from '../../../../hooks/use-group-list';
import UpdateFavoriteGroupPopover from '../../../update-favorite-group-popover';
import ShareFavorite from './components/share-favorite';

import type { IFavoriteGroup } from '../../../../types';

import './index.scss';

export default defineComponent({
  name: 'RenderFavorite',
  props: {
    data: {
      type: Object as PropType<IFavoriteGroup['favorites'][number]>,
      required: true,
    },
  },
  emits: ['openBlank', 'selected'],
  setup(props, context) {
    const { t } = useI18n();
    const favoriteType = useFavoriteType();
    const { run: refreshGroupList } = useGroupList(favoriteType.value);

    const actionRef = shallowRef<Element>();
    const actionPanelRef = shallowRef<Element>();

    const isHover = shallowRef(false);
    const isEditFavoriteGroupHover = shallowRef(false);
    const isShowEditFavorite = shallowRef(false);
    const isShowShareFavorite = shallowRef(false);

    const isEditGroupEnable = computed(() => props.data.group_id !== null);

    let tippyInstance: Instance | undefined;

    const initActionPop = () => {
      tippyInstance = tippy(actionRef.value as SingleTarget, {
        content: actionPanelRef.value as any,
        trigger: 'click',
        placement: 'bottom-start',
        theme: 'light favorite-box-item-action-panel',
        arrow: false,
        interactive: true,
        zIndex: 99,
        appendTo: () => document.body,
        onShown() {
          isHover.value = true;
        },
        onHide() {
          isHover.value = false;
        },
      });
    };

    const handleClick = () => {
      context.emit('selected', props.data);
    };

    const handleShowShareFavorite = () => {
      isShowShareFavorite.value = true;
      tippyInstance.hide();
    };

    const handleCloseShareFavorite = () => {
      isShowShareFavorite.value = false;
    };

    const handleEditFavoriInfo = () => {
      isShowEditFavorite.value = true;
      tippyInstance.hide();
    };

    const handleCloseEditFavorite = () => {
      isShowEditFavorite.value = false;
    };

    const handleCloneFavorite = async () => {
      await createFavorite({
        ...props.data,
        type: favoriteType.value,
        name: `${props.data.name}${t('副本')}`,
      });
      refreshGroupList();
      Message({
        theme: 'success',
        message: t('操作成功'),
      });
    };

    const handleUpdateGroup = async (groupId: null | number) => {
      await updateFavorite(props.data.id, {
        ...props.data,
        type: favoriteType.value,
        group_id: groupId,
      });
      refreshGroupList();
      Message({
        theme: 'success',
        message: t('操作成功'),
      });
    };

    const handleOpenBlank = () => {
      context.emit('openBlank', props.data);
    };

    const handleDeleteFavorite = async () => {
      await destroyFavorite(props.data.id, {
        type: favoriteType.value,
      });
      refreshGroupList();
      Message({
        theme: 'success',
        message: t('操作成功'),
      });
    };

    onMounted(() => {
      initActionPop();
    });

    onBeforeUnmount(() => {
      if (tippyInstance) {
        tippyInstance.hide();
        tippyInstance.destroy();
      }
    });

    return () => (
      <div
        class={{
          'favorite-box-item': true,
          'is-hover': isHover.value,
        }}
        v-bk-tooltips={{
          content: () => {
            return (
              <div>
                <div>
                  <span>
                    {t('收藏名')}: {props.data.name}
                  </span>
                </div>
                <div>
                  <span>
                    {t('创建人')}:{' '}
                    {props.data.create_user ? <bk-user-display-name user-id={props.data.create_user} /> : '--'}
                  </span>
                </div>
                <div>
                  <span>
                    {t('最近更新人')}:{' '}
                    {props.data.update_user ? <bk-user-display-name user-id={props.data.update_user} /> : '--'}
                  </span>
                </div>
                <div>
                  <span>
                    {t('最近更新时间')}: {props.data.update_time}
                  </span>
                </div>
              </div>
            );
          },
          placement: 'right',
        }}
      >
        <div
          class='favorite-box-item-name'
          onClick={handleClick}
        >
          {props.data.name}
        </div>
        <div
          ref={actionRef}
          class='favorite-item-action'
        >
          <i class='icon-monitor icon-mc-more' />
        </div>
        <div
          ref={actionPanelRef}
          class='favorite-box-item-action-pancel'
        >
          <div
            class='action-item'
            onClick={handleShowShareFavorite}
          >
            {t('分享')}
          </div>
          <div
            class='action-item'
            onClick={handleEditFavoriInfo}
          >
            {t('编辑')}
          </div>
          <div
            class='action-item'
            onClick={handleCloneFavorite}
          >
            {t('克隆')}
          </div>
          <div
            class={{
              'action-item': true,
              'is-hover': isEditFavoriteGroupHover.value,
            }}
          >
            <UpdateFavoriteGroupPopover data={[props.data]} />
          </div>
          {isEditGroupEnable.value && (
            <div
              class='action-item'
              onClick={() => handleUpdateGroup(null)}
            >
              {t('从分组中移除')}
            </div>
          )}
          <div
            class='action-item'
            onClick={handleOpenBlank}
          >
            {t('新开标签页')}
          </div>
          <div
            class='action-remove'
            onClick={handleDeleteFavorite}
          >
            {t('删除')}
          </div>
        </div>
        <ShareFavorite
          data={props.data}
          isShow={isShowShareFavorite.value}
          onClose={handleCloseShareFavorite}
        />
        <EditFavorite
          data={props.data}
          isShow={isShowEditFavorite.value}
          onClose={handleCloseEditFavorite}
        />
      </div>
    );
  },
});
