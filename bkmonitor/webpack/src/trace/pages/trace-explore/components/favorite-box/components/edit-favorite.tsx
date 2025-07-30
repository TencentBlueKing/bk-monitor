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
import { type PropType, defineComponent, reactive, watch } from 'vue';
import { shallowRef } from 'vue';
import { computed } from 'vue';

import { Button, Dialog, Form, Input, Select, Tag } from 'bkui-vue';
import _ from 'lodash';
import { createFavorite, updateFavorite } from 'monitor-api/modules/model';
import { useI18n } from 'vue-i18n';

import { GROUP_ID_PERSONAL } from '../constants';
import useFavoriteType from '../hooks/use-favorite-type';
import useGroupList from '../hooks/use-group-list';
import CreateGroupExtends from './create-group-extends';
import RenderFavoriteDataId from './favorite-info/render-favorite-data-id';
import RenderFavoriteQuery from './favorite-info/render-favorite-query';

import type { IFavoriteGroup } from '../types';

export default defineComponent({
  name: 'EditFavorite',
  props: {
    data: {
      type: Object as PropType<IFavoriteGroup['favorites'][number] | null>,
      required: true,
    },
    isShow: {
      type: Boolean,
    },
    personal: {
      type: Boolean,
    },
    isCreate: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['close', 'success'],
  setup(props, context) {
    const { t } = useI18n();
    const favoriteType = useFavoriteType();
    const { editableGroupList: groupList, run: refreshGroupList, allFavoriteList } = useGroupList(favoriteType.value);

    const formRef = shallowRef<InstanceType<typeof Form>>();
    const isSubmiting = shallowRef(false);
    const newGroupName = shallowRef('');

    const formData = reactive({
      name: '',
      group_id: '',
    });

    const groupRenderList = computed(() => {
      return [
        ...groupList.value,
        {
          id: 'null',
          name: t('未分组'),
        },
      ];
    });

    watch(
      () => props.isShow,
      val => {
        if (val && props.data && !props.isCreate) {
          formData.name = props.data.name;
          formData.group_id = `${props.data.group_id}`;
          newGroupName.value = '';
        }
      },
      {
        immediate: true,
      }
    );

    const rules = {
      name: [
        {
          required: true,
          trigger: 'blur',
        },
        {
          validator: (value: string) =>
            /^[\u4e00-\u9fa5_a-zA-Z0-9`~!@#$%^&*()_\-+=<>?:"\s{}|,./;'\\[\]·~！@#￥%……&*（）——\-+={}|《》？：“”【】、；‘'，。、]+$/im.test(
              value.trim()
            ),
          message: t('收藏名包含了特殊符号'),
          trigger: 'blur',
        },
        {
          validator: (value: string) => {
            const favorite = _.find(allFavoriteList.value, item => item.name === value);
            return !favorite || favorite.id === props.data?.id;
          },
          message: t('注意: 名字冲突'),
          trigger: 'blur',
        },
        {
          validator: (value: string) => ![t('个人收藏'), t('未分组')].includes(value.trim()),
          message: t('保留名称，不可使用'),
          trigger: 'blur',
        },
      ],
    };

    const handleCreateGroupSuccess = (groupName: string) => {
      newGroupName.value = groupName;
    };

    const handleSubmitEdit = async () => {
      isSubmiting.value = true;
      try {
        await formRef.value.validate();
        if (props.isCreate) {
          await createFavorite({
            ...(props.data || {}),
            type: favoriteType.value,
            name: formData.name,
            group_id: formData.group_id === 'null' || formData.group_id === '' ? null : formData.group_id,
          });
        } else {
          await updateFavorite(props.data.id, {
            type: favoriteType.value,
            ...formData,
          });
        }
        refreshGroupList();
        context.emit('close');
      } finally {
        isSubmiting.value = false;
      }
    };

    const handleClose = () => {
      context.emit('close');
    };

    return () => (
      <Dialog
        v-slots={{
          footer: () => (
            <>
              <Button
                loading={isSubmiting.value}
                theme='primary'
                onClick={handleSubmitEdit}
              >
                {t('确定')}
              </Button>
              <Button
                style='margin-left: 8px'
                onClick={handleClose}
              >
                {t('取消')}
              </Button>
            </>
          ),
        }}
        is-show={props.isShow}
        title={t(props.isCreate ? '新增收藏' : '编辑收藏')}
        onClosed={handleClose}
      >
        <Form
          ref={formRef}
          form-type='vertical'
          model={formData}
          rules={rules}
        >
          <Form.FormItem
            label={t('收藏名')}
            property='name'
            required
          >
            <Input
              v-model={formData.name}
              maxcharacter={30}
              placeholder={t('填写收藏名（长度30个字符）')}
              show-word-limit
            />
          </Form.FormItem>
          <Form.FormItem
            label={t('所属分组')}
            property='group_id'
            required
          >
            <Select
              v-model={formData.group_id}
              v-slots={{
                extension: () => <CreateGroupExtends onSuccess={handleCreateGroupSuccess} />,
              }}
            >
              {groupRenderList.value.map(groupItem => (
                <Select.Option
                  id={`${groupItem.id}`}
                  key={groupItem.id}
                  name={groupItem.id === GROUP_ID_PERSONAL ? `${groupItem.name} (${t('仅个人可见')})` : groupItem.name}
                >
                  <span>{groupItem.name}</span>
                  {groupItem.id === GROUP_ID_PERSONAL && (
                    <span style='color: rgb(151, 155, 165);'>（{t('仅个人可见')}）</span>
                  )}
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
          </Form.FormItem>
          {favoriteType.value === 'event' && (
            <Form.FormItem label={t('数据ID')}>
              <RenderFavoriteDataId data={props.data} />
            </Form.FormItem>
          )}
          <Form.FormItem label={t('查询语句')}>
            <RenderFavoriteQuery data={props.data} />
          </Form.FormItem>
        </Form>
      </Dialog>
    );
  },
});
