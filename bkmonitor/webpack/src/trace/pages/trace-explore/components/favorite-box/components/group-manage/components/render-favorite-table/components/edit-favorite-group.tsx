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
import { type PropType, computed, defineComponent, reactive, shallowRef } from 'vue';

import { Message, Select, Tag } from 'bkui-vue';
import _ from 'lodash';
import { updateFavorite } from 'monitor-api/modules/model';
import { useI18n } from 'vue-i18n';

import CreateGroupExtends from '../../../../../components/create-group-extends';
import useFavoriteType from '../../../../../hooks/use-favorite-type';
import useGroupList from '../../../../../hooks/use-group-list';

import type { IFavoriteGroup } from '../../../../../types';

import './edit-favorite-group.scss';

export default defineComponent({
  props: {
    data: {
      type: Object as PropType<IFavoriteGroup['favorites'][number]>,
    },
  },
  emits: ['success'],
  setup(props, context) {
    const { t } = useI18n();
    const favoriteType = useFavoriteType();
    const { editableGroupList: groupList, run: refreshGroupList } = useGroupList(favoriteType.value);

    const groupSelectRef = shallowRef<InstanceType<typeof Select>>();
    const isEditing = shallowRef(false);
    const newGroupName = shallowRef('');
    const formData = reactive({
      group_id: -1,
    });

    const renderGroupName = computed(() => {
      const group = groupList.value.find(item => item.id === props.data.group_id);
      return group ? group.name : t('未分组');
    });

    const handleEditStart = (event: Event) => {
      event.stopImmediatePropagation();
      event.stopPropagation();
      isEditing.value = true;
      formData.group_id = props.data.group_id;
      setTimeout(() => {
        groupSelectRef.value.showPopover();
      }, 100);
    };

    const handleCreateGroupSuccess = (groupName: string) => {
      newGroupName.value = groupName;
    };

    const handleSubmit = async () => {
      if (formData.group_id === props.data.group_id) {
        isEditing.value = false;
        return;
      }
      await updateFavorite(props.data.id, {
        type: favoriteType.value,
        name: props.data.name,
        group_id: _.isNumber(formData.group_id) ? formData.group_id : null,
      });
      refreshGroupList();
      context.emit('success');
      Message({
        theme: 'success',
        message: t('编辑成功'),
      });
    };

    return () => (
      <div class='favorite-box-edit-favorite-group'>
        {!isEditing.value && (
          <div class='value-wrapper'>
            <div class='value-text'>{renderGroupName.value}</div>
            <div
              class='edit-flag'
              onClick={handleEditStart}
            >
              <i class='icon-monitor icon-bianji' />
            </div>
          </div>
        )}
        {isEditing.value && (
          <Select
            ref={groupSelectRef}
            v-model={formData.group_id}
            v-slots={{
              extension: () => <CreateGroupExtends onSuccess={handleCreateGroupSuccess} />,
            }}
            onBlur={handleSubmit}
          >
            {groupList.value.map(groupItem => (
              <Select.Option
                id={groupItem.id}
                key={groupItem.id}
                name={groupItem.id === 0 ? `${groupItem.name}(${t('仅个人可见')})` : groupItem.name}
              >
                {groupItem.name}
                {groupItem.id === 0 && <span style='color: rgb(151, 155, 165);'>（{t('仅个人可见')}）</span>}
                {groupItem.name === newGroupName.value && (
                  <Tag
                    style='margin-left: 4px'
                    size='small'
                    theme='warning'
                    type='filled'
                  >
                    new
                  </Tag>
                )}
              </Select.Option>
            ))}
          </Select>
        )}
      </div>
    );
  },
});
