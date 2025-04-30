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
import {
  defineComponent,
  type PropType,
  shallowRef,
  watch,
  onMounted,
  onBeforeUnmount,
  computed,
  type UnwrapRef,
} from 'vue';
import { useI18n } from 'vue-i18n';

import { Table, TableColumn } from '@blueking/table';
import { Button, Input, Exception, Message, Checkbox } from 'bkui-vue';
import _ from 'lodash';
import { bulkDeleteFavorite } from 'monitor-api/modules/model';
import tippy, { type SingleTarget, type Instance } from 'tippy.js';

import { GROUP_ID_ALL } from '../../../../constants';
import useDebouncedRef from '../../../../hooks/use-debounced-ref';
import useFavoriteType from '../../../../hooks/use-favorite-type';
import useGroupList from '../../../../hooks/use-group-list';
import UpdateFavoriteGroupPopover from '../../../update-favorite-group-popover';
import EditFavoriteGroup from './components/edit-favorite-group';
import EditFavoriteName from './components/edit-favorite-name';
import FavoriteDetail from './components/favorite-detail';

import type { IFavoriteGroup } from '../../../../types';

import './index.scss';

export default defineComponent({
  name: 'RenderFavoriteTable',
  props: {
    groupId: {
      type: [String, Number, null] as PropType<any>,
      required: true,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const favoriteType = useFavoriteType();
    const { allFavoriteList, data: groupList, run: refreshGroupList } = useGroupList(favoriteType.value);

    let actionPopInstance: Instance;

    const batchTriggerRef = shallowRef<HTMLElement>();
    const batchPanelRef = shallowRef<HTMLElement>();
    const favoriteSerach = useDebouncedRef('');
    const selectFavoriteMap = shallowRef<Record<number, IFavoriteGroup['favorites'][number]>>({});
    const currentFavoriteDetail = shallowRef<IFavoriteGroup['favorites'][number]>();

    const selectFavoriteList = computed(() => Object.values(selectFavoriteMap.value));
    const favoriteList = computed(() => {
      if (props.groupId === GROUP_ID_ALL) {
        return allFavoriteList.value;
      }

      return _.find(groupList.value, item => item.id === props.groupId)?.favorites || [];
    });
    const renderFavoriteList = computed(() => {
      const keyWord = favoriteSerach.value.toLocaleLowerCase().trim();
      if (!keyWord) {
        return [...favoriteList.value];
      }
      return _.filter(favoriteList.value, item => item.name.toLocaleLowerCase().indexOf(keyWord) > -1);
    });

    watch(
      () => props.groupId,
      () => {
        favoriteSerach.value = '';
        selectFavoriteMap.value = {};
        currentFavoriteDetail.value = undefined;
      }
    );
    watch(
      selectFavoriteList,
      () => {
        setTimeout(() => {
          if (actionPopInstance) {
            selectFavoriteList.value.length > 0 ? actionPopInstance.enable() : actionPopInstance.disable();
          }
        });
      },
      {
        immediate: true,
      }
    );

    const rowClassCallback = (payload: UnwrapRef<typeof currentFavoriteDetail>) => {
      return currentFavoriteDetail.value && payload.id === currentFavoriteDetail.value.id ? 'is-active' : '';
    };

    const handleBatchDelete = async () => {
      await bulkDeleteFavorite({
        type: favoriteType.value,
        ids: selectFavoriteList.value.map(item => item.id),
      });
      refreshGroupList();
      Message({
        theme: 'success',
        message: t('操作成功'),
      });
    };

    const handleSelectAll = (checked: boolean) => {
      if (!checked) {
        selectFavoriteMap.value = {};
      } else {
        selectFavoriteMap.value = renderFavoriteList.value.reduce((result, item) => {
          return Object.assign(result, {
            [item.id]: item,
          });
        }, {});
      }
    };
    const handleSelectChange = (checked: boolean, data: IFavoriteGroup['favorites'][number]) => {
      const latestSelectFavoriteMap = { ...selectFavoriteMap.value };
      if (checked) {
        latestSelectFavoriteMap[data.id] = data;
      } else {
        delete latestSelectFavoriteMap[data.id];
      }
      selectFavoriteMap.value = latestSelectFavoriteMap;
    };

    const handleRowClick = (event: Event, payload: UnwrapRef<typeof currentFavoriteDetail>) => {
      currentFavoriteDetail.value = payload;
    };

    const handleEditGroupSucccess = () => {
      currentFavoriteDetail.value = undefined;
    };

    onMounted(() => {
      actionPopInstance = tippy(batchTriggerRef.value as SingleTarget, {
        content: batchPanelRef.value as any,
        trigger: 'mouseenter click',
        placement: 'bottom',
        theme: 'light favorite-box-favorite-manage-batch-action-panel',
        arrow: false,
        interactive: true,
        offset: [0, 4],
      });

      onBeforeUnmount(() => {
        actionPopInstance.hide();
        actionPopInstance.destroy();
      });
    });

    return () => (
      <div class='favorite-box-group-manage-favorite-table'>
        <div class='layout-left'>
          <div class='action-box'>
            <div ref={batchTriggerRef}>
              <Button disabled={selectFavoriteList.value.length < 1}>{t('批量操作')}</Button>
              <div ref={batchPanelRef}>
                <div class='action-item'>
                  <UpdateFavoriteGroupPopover data={selectFavoriteList.value} />
                </div>
                <div
                  class='action-item'
                  onClick={handleBatchDelete}
                >
                  {t('删除')}
                </div>
              </div>
            </div>
            <Input
              class='searach-input'
              v-model={favoriteSerach.value}
              placeholder={t('搜索收藏名')}
            />
          </div>
          <Table
            key={props.groupId}
            v-slots={{
              empty: () => {
                if (!favoriteSerach.value) {
                  return (
                    <Exception
                      description={t('没有数据')}
                      scene='part'
                      type='empty'
                    />
                  );
                }
                return (
                  <Exception
                    description={t('搜索为空')}
                    scene='part'
                    type='search-empty'
                  />
                );
              },
            }}
            rowConfig={{
              useKey: 'true',
              keyField: 'id',
            }}
            data={renderFavoriteList.value}
            row-class={rowClassCallback}
            auto-resize
            onRowClick={handleRowClick}
          >
            <TableColumn
              width={60}
              v-slots={{
                header: () => {
                  const value =
                    Object.keys(selectFavoriteMap.value).length === renderFavoriteList.value.length &&
                    renderFavoriteList.value.length > 0;
                  return (
                    <Checkbox
                      modelValue={value}
                      onChange={handleSelectAll}
                    />
                  );
                },
                default: ({ data }: { data: IFavoriteGroup['favorites'][number] }) => (
                  <Checkbox
                    modelValue={Boolean(selectFavoriteMap.value[data.id])}
                    onChange={(value: boolean) => handleSelectChange(value, data)}
                  />
                ),
              }}
              field='select'
            />
            <TableColumn
              width={240}
              v-slots={{
                default: ({ data }: { data: IFavoriteGroup['favorites'][number] }) => (
                  <EditFavoriteName
                    data={data}
                    theme='primary'
                  />
                ),
              }}
              field='name'
              title={t('收藏名称')}
            />
            <TableColumn
              width={320}
              v-slots={{
                default: ({ data }: { data: IFavoriteGroup['favorites'][number] }) => (
                  <EditFavoriteGroup
                    data={data}
                    onSuccess={handleEditGroupSucccess}
                  />
                ),
              }}
              field='group_id'
              title={t('所属分组')}
            />
            {favoriteType.value === 'event' && (
              <TableColumn
                width={240}
                v-slots={{
                  default: ({ data }: { data: IFavoriteGroup<'event'>['favorites'][number] }) => {
                    return data.config?.queryConfig?.result_table_id || '*';
                  },
                }}
                field='id'
                title={t('数据ID')}
              />
            )}

            <TableColumn
              width={120}
              field='update_user'
              title={t('变更人')}
            />
            <TableColumn
              field='update_time'
              minWidth={180}
              title={t('变更时间')}
            />
          </Table>
        </div>
        {currentFavoriteDetail.value && (
          <div class='layout-right'>
            <FavoriteDetail data={currentFavoriteDetail.value} />
          </div>
        )}
      </div>
    );
  },
});
