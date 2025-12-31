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

import { defineComponent, type PropType, ref, nextTick, computed, onMounted } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import { showMessage } from '../../../utils';
import $http from '@/api';

import type { IListItemData } from '../../../type';

import './add-index-set.scss';

/** 日志采集 - 新建/修改索引集 */
export default defineComponent({
  name: 'AddIndexSet',
  props: {
    data: {
      type: Object as PropType<IListItemData>,
      default: () => ({}),
    },
    isFrom: {
      type: Boolean,
      default: true,
    },
    isAdd: { type: Boolean, default: false },
  },

  emits: ['submit', 'cancel'],

  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();
    const inputRef = ref();
    const editFormRef = ref();
    const loading = ref(false);
    const editFormRules = {
      index_set_name: [
        {
          required: true,
          message: t('请输入索引集名称'),
          trigger: 'blur',
        },
        {
          min: 1,
          max: 50,
          message: t('索引集名称长度应在1-50个字符之间'),
          trigger: 'blur',
        },
      ],
    };
    const editData = ref<IListItemData>({
      index_set_name: '',
    });
    const spaceUid = computed(() => store.getters.spaceUid);

    onMounted(() => {
      editData.value = { ...props.data };
    });
    /**
     *
     * @param config
     */
    const handleRequest = async (config: { method: string; params?: any; data?: any; message: string }) => {
      loading.value = true;
      const res = await $http.request(config.method, {
        params: config.params,
        data: config.data,
      });

      if (res.result) {
        showMessage(config.message);
        emit('submit', editData.value);
        handleEditGroupCancel();
      }
      loading.value = false;
    };

    /**
     * 编辑索引集提交
     */
    const handleEditGroupSubmit = async () => {
      if (loading.value) {
        return;
      }
      try {
        await editFormRef.value?.validate();
        const { index_set_id, index_set_name } = editData.value;
        const method = props.isAdd ? 'collect/addIndexGroup' : 'collect/updateIndexGroup';
        const message = props.isAdd ? t('新增成功') : t('更新成功');
        const baseConfig = { message, method };
        const dataConfig = props.isAdd
          ? { data: { space_uid: spaceUid.value, index_set_name } }
          : { params: { index_set_id }, data: { index_set_name } };
        const config = { ...baseConfig, ...dataConfig };

        await handleRequest(config);
      } catch (error) {
        console.log('操作失败:', error);
      }
    };

    const handleEditGroupCancel = () => {
      if (loading.value) {
        return;
      }
      emit('cancel');
    };
    const autoFocus = () => {
      nextTick(() => {
        inputRef.value?.$refs.input?.focus?.();
      });
    };
    expose({ autoFocus });

    const renderButtons = () => {
      /** 按钮模式 */
      if (props.isFrom) {
        return (
          <div class='add-btns'>
            <bk-button
              class='mr8'
              size='small'
              theme='primary'
              loading={loading.value}
              on-Click={handleEditGroupSubmit}
            >
              {t('确定')}
            </bk-button>
            <bk-button
              size='small'
              loading={loading.value}
              on-Click={handleEditGroupCancel}
            >
              {t('取消')}
            </bk-button>
          </div>
        );
      }
      /** icon 模式 */
      return (
        <span
          class={{
            'icon-btns': true,
            disabled: loading.value,
          }}
        >
          <span
            class='bk-icon icon-check-line submit-icon'
            on-Click={handleEditGroupSubmit}
          />
          <span
            class='bk-icon icon-close-line-2 close-icon'
            on-Click={handleEditGroupCancel}
          />
        </span>
      );
    };

    // 新增/修改索引集名称
    const renderAddIndexSet = () => (
      <div class={props.isFrom ? 'popover-add-index-set' : 'add-index-set-input-main'}>
        {props.isFrom && <div class='title'>{props.isAdd ? t('新建索引集') : t('重命名')}</div>}
        <bk-form
          ref={editFormRef}
          class='add-index-set-form'
          form-type='vertical'
          {...{
            props: {
              model: editData.value,
              rules: editFormRules,
            },
          }}
        >
          <bk-form-item
            label={props.isFrom ? t('索引集名称') : ''}
            property='index_set_name'
            required
          >
            <bk-input
              ref={inputRef}
              maxlength={50}
              placeholder={props.isFrom ? t('请输入') : t('请输入索引集名称')}
              value={editData.value.index_set_name}
              clearable
              onInput={val => {
                editData.value.index_set_name = val;
              }}
            />
          </bk-form-item>
        </bk-form>
        {renderButtons()}
      </div>
    );

    return () => <div class='add-index-set-box'>{renderAddIndexSet()}</div>;
  },
});
