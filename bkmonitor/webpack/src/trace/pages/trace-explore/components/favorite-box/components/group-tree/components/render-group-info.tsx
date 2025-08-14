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
import { type PropType, computed, defineComponent, onBeforeUnmount, onMounted, shallowRef } from 'vue';
import { reactive } from 'vue';

import { Button, Form, Input, Message } from 'bkui-vue';
import _ from 'lodash';
import { destroyFavoriteGroup, updateFavoriteGroup } from 'monitor-api/modules/model';
import tippy, { type Instance, type SingleTarget } from 'tippy.js';
import { useI18n } from 'vue-i18n';

import { GROUP_ID_PERSONAL } from '../../../constants';
import useFavoriteType from '../../../hooks/use-favorite-type';
import useGroupList from '../../../hooks/use-group-list';
import { validatorGroupName } from '../../../utils';

import type { IFavoriteGroup } from '../../../types';

import './render-group-info.scss';

export default defineComponent({
  props: {
    data: {
      type: Object as PropType<IFavoriteGroup>,
      required: true,
    },
    expanded: Boolean,
    fixedSelectedFavorite: Boolean,
  },
  emits: ['toggleExpand'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const favoriteType = useFavoriteType();
    const { run: refreshGroupList, data: groupList } = useGroupList(favoriteType.value);

    const rootRef = shallowRef<HTMLDivElement>();
    const panelRef = shallowRef<HTMLDivElement>();
    const editFormRef = shallowRef<InstanceType<typeof Form>>();
    const groupNameEditPanelRef = shallowRef<HTMLDivElement>();
    const isHover = shallowRef(false);
    const isEditSubmiting = shallowRef(false);

    const editFormData = reactive({
      name: '',
    });

    const isPersonalGroup = computed(() => props.data.id === GROUP_ID_PERSONAL);
    const isEnableGroupAction = computed(() => props.data.editable);

    const editFormRules = {
      name: [
        {
          validator: validatorGroupName,
          trigger: 'change',
          message: t('输入中文、英文、数字、下划线类型的字符'),
        },
        {
          validator: (value: string) => ![t('个人收藏'), t('未分组')].includes(value.trim()),
          message: t('保留名称，不可使用'),
          trigger: 'change',
        },
        {
          validator: (value: string) => {
            const group = _.find(groupList.value, item => item.name === value);
            return !group || group.id === props.data.id;
          },
          message: t('注意: 名字冲突'),
          trigger: 'change',
        },
      ],
    };

    let tippyInstance: Instance;
    let editGroupInstance: Instance;

    const initActionPop = () => {
      if (!isEnableGroupAction.value) {
        return;
      }
      tippyInstance = tippy(rootRef.value as SingleTarget, {
        content: panelRef.value as any,
        trigger: 'click',
        placement: 'bottom-start',
        theme: 'light favorite-box-group-action-panel',
        arrow: false,
        interactive: true,
        hideOnClick: true,
        appendTo: () => document.body,
        onShown() {
          isHover.value = true;
        },
        onHide() {
          isHover.value = false;
        },
      });
    };

    const initEditGroupPop = () => {
      if (!isEnableGroupAction.value) {
        return;
      }
      isHover.value = true;
      editGroupInstance = tippy(rootRef.value as SingleTarget, {
        content: groupNameEditPanelRef.value as any,
        trigger: 'click',
        placement: 'bottom',
        theme: 'light favorite-box-group-edit-panel',
        interactive: true,
        appendTo: () => document.body,
        hideOnClick: true,
        zIndex: 99,
        onShow() {
          editFormData.name = props.data.name;
          editFormRef.value?.clearValidate();
        },
        onHide() {
          setTimeout(() => {
            editGroupInstance.destroy();
          });
          isHover.value = false;
        },
      });
      editGroupInstance.show();
    };

    const handleToggleExpand = () => {
      emit('toggleExpand', !props.expanded);
    };

    const handleShowEdit = () => {
      if (tippyInstance) {
        tippyInstance.hide();
      }
      initEditGroupPop();
    };

    const handleDestroyFavoriteGroup = async () => {
      await destroyFavoriteGroup(props.data.id, {
        type: favoriteType.value,
      });
      refreshGroupList();
      Message({
        theme: 'success',
        message: t('操作成功'),
      });
    };

    const handleUpdateFavoriteGroup = async () => {
      try {
        isEditSubmiting.value = true;
        await editFormRef.value.validate();
        await updateFavoriteGroup(props.data.id, {
          type: favoriteType.value,
          ...editFormData,
        });
        refreshGroupList();
        editGroupInstance.hide();
        Message({
          theme: 'success',
          message: t('操作成功'),
        });
      } finally {
        isEditSubmiting.value = false;
      }
    };

    const handleEditGroupCancel = () => {
      editGroupInstance.hide();
    };

    onMounted(() => {
      initActionPop();
    });

    onBeforeUnmount(() => {
      if (tippyInstance) {
        tippyInstance.hide();
        tippyInstance.destroy();
      }
      if (editGroupInstance) {
        editGroupInstance.hide();
        editGroupInstance.destroy();
      }
    });

    return () => {
      const groupIconClass = ['icon-monitor', 'expanded-flag'];
      if (props.fixedSelectedFavorite) {
        groupIconClass.push('icon-file-dot');
      } else {
        if (!props.expanded) {
          groupIconClass.push(isPersonalGroup.value ? 'icon-file-personal' : 'icon-mc-file-close');
        } else {
          groupIconClass.push('icon-mc-file-open');
        }
      }

      return (
        <>
          <div
            class={{
              'favorite-box-group-info': true,
              'is-hover': isHover.value,
              'is-editable-disable': !isEnableGroupAction.value,
            }}
          >
            <div
              class='wrapper'
              onClick={handleToggleExpand}
            >
              <i class={groupIconClass} />
              <div
                class='group-name'
                v-bk-tooltips={props.data.name}
              >
                {props.data.name}
              </div>
              <div class='group-favorite-count'>{props.data.favorites.length}</div>
            </div>
            {isEnableGroupAction.value && (
              <div
                ref={rootRef}
                class='group-action'
              >
                <i class='icon-monitor icon-mc-more' />
              </div>
            )}
          </div>
          {isEnableGroupAction.value && (
            <>
              <div ref={panelRef}>
                <div
                  class='action-item'
                  onClick={handleShowEdit}
                >
                  {t('编辑')}
                </div>
                <div
                  class='action-remove'
                  onClick={handleDestroyFavoriteGroup}
                >
                  {t('解散分组')}
                </div>
              </div>
              <div style='display: none'>
                <div ref={groupNameEditPanelRef}>
                  <Form
                    ref={editFormRef}
                    form-type='vertical'
                    model={editFormData}
                    rules={editFormRules}
                  >
                    <Form.FormItem
                      error-display-type='tooltips'
                      label={t('分组名称')}
                      property='name'
                      required={true}
                    >
                      <Input
                        v-model={editFormData.name}
                        maxcharacter={30}
                        clearable
                        showWordLimit
                      />
                    </Form.FormItem>
                  </Form>
                  <div style='margin-top: -8px;'>
                    <Button
                      loading={isEditSubmiting.value}
                      size='small'
                      theme='primary'
                      onClick={handleUpdateFavoriteGroup}
                    >
                      {t('确定')}
                    </Button>
                    <Button
                      style='margin-left: 8px'
                      size='small'
                      onClick={handleEditGroupCancel}
                    >
                      {t('取消')}
                    </Button>
                  </div>
                </div>
              </div>
            </>
          )}
        </>
      );
    };
  },
});
