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

import { computed, defineComponent, ref, reactive, watch, PropType } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import { useFavorite } from '../../hooks/use-favorite';
import { IFavoriteItem } from '../../types';
import { handleApiError } from '../../utils';

import './add-group.scss';

export default defineComponent({
  name: 'AddGroup',
  props: {
    rules: {
      type: Object as PropType<Record<string, any>>,
      default: () => ({}),
    },
    /** 是否以表单形式展示 */
    isFormType: {
      type: Boolean,
      default: false,
    },
    /** 是否为新增 */
    isCreate: {
      type: Boolean,
      default: true,
    },
    data: {
      type: Object as () => IFavoriteItem,
      default: () => ({}),
    },
  },
  emits: ['cancel', 'submit'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    /** 当前业务名 */
    const spaceUid = computed(() => store.state.spaceUid);
    const formData = reactive({ group_name: '' });
    const isShowAddGroup = ref(false);
    const checkInputFormRef = ref(null);
    // 使用自定义 hook 管理状态
    const { updateGroupName } = useFavorite();
    watch(
      () => props.isCreate,
      val => {
        if (!val) {
          formData.group_name = props.data.group_name || '';
        }
      },
      { immediate: true },
    );

    /** 创建分组 */
    const handleCreateGroup = () => {
      checkInputFormRef.value
        ?.validate()
        .then(async () => {
          if (!formData.group_name.trim()) return;
          const { group_id } = props.data;
          const params = props.isCreate
            ? { group_new_name: formData.group_name }
            : { group_new_name: formData.group_name, group_id };
          updateGroupName(params, spaceUid.value, props.isCreate, res => {
            isShowAddGroup.value = false;
            emit('submit', res.id, formData.group_name);
          });
        })
        .catch(err => {
          handleApiError(err, '创建分组失败');
        });
    };
    /** 取消按钮的handle */
    const handleCancel = () => {
      if (!props.isFormType) {
        isShowAddGroup.value = false;
      }
      formData.group_name = props.isCreate ? '' : props.data.group_name;
      checkInputFormRef.value?.clearError();
      emit('cancel', props.data);
    };
    const addRender = () => {
      if (!props.isFormType && !isShowAddGroup.value) {
        return (
          <div
            class='select-add-new-group'
            onClick={() => (isShowAddGroup.value = true)}
          >
            <div>
              <i class='bk-icon icon-plus-circle'></i> {t('新建分组')}
            </div>
          </div>
        );
      }
      return (
        <div class={props.isFormType ? 'add-new-from-input' : 'add-new-page-input'}>
          <bk-form
            ref={checkInputFormRef}
            style={{ width: '100%' }}
            form-type={props.isFormType ? 'vertical' : 'horizontal'}
            labelWidth={props.isFormType ? 80 : 0}
            {...{
              props: {
                model: formData,
                rules: props.rules,
              },
            }}
          >
            <bk-form-item
              class='add-new-group-item'
              label={props.isFormType ? t('分组名称') : ''}
              property='group_name'
              required
            >
              <bk-input
                class='add-new-group-input'
                placeholder={t('{n}, （长度30个字符）', { n: t('请输入组名') })}
                value={formData.group_name}
                clearable
                onInput={val => (formData.group_name = val)}
              ></bk-input>
            </bk-form-item>
          </bk-form>
          {props.isFormType ? (
            <div class='add-group-from-btns'>
              <bk-button
                size='small'
                theme='primary'
                onClick={handleCreateGroup}
              >
                {t('保存')}
              </bk-button>
              <bk-button
                class='ml8'
                size='small'
                onClick={handleCancel}
              >
                {t('取消')}
              </bk-button>
            </div>
          ) : (
            <div class='operate-button'>
              <span
                class='bk-icon icon-check-line submit-icon'
                onClick={handleCreateGroup}
              ></span>
              <span
                class='bk-icon icon-close-line-2 close-icon'
                onClick={handleCancel}
              ></span>
            </div>
          )}
        </div>
      );
    };
    return () => addRender();
  },
});
