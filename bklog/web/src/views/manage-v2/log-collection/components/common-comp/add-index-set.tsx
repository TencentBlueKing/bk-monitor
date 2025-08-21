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

import { computed, defineComponent, PropType, onMounted, ref } from 'vue';

import useLocale from '@/hooks/use-locale';

import { ListItemData } from '../../type';

import './add-index-set.scss';

/** 日志采集 - 新建/修改索引集 */
export default defineComponent({
  name: 'AddIndexSet',
  props: {
    data: {
      type: Object as PropType<ListItemData>,
      default: () => ({}),
    },
    isFrom: {
      type: Boolean,
      default: true,
    },
    isAdd: { type: Boolean, default: false },
  },

  emits: ['submit', 'cancel'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const inputRef = ref<HTMLInputElement>();
    const editFormRef = ref();
    const editFormRules = {};
    const handleEditGroupSubmit = () => {
      editFormRef.value?.validate().then(() => {
        emit('submit');
      });
    };
    const handleEditGroupCancel = () => {
      emit('cancel');
    };
    // 新增/修改索引集名称
    const renderAddIndexSet = (item: ListItemData) => (
      <div class='popover-add-index-set'>
        <div class='title'>{props.isAdd ? t('新建索引集') : t('重命名')}</div>
        <bk-form
          ref={editFormRef}
          class='add-index-set-form'
          form-type='vertical'
          {...{
            props: {
              model: item,
              rules: editFormRules,
            },
          }}
        >
          <bk-form-item
            label={t('索引集名称')}
            property='group_name'
            required
          >
            <bk-input
              ref={inputRef}
              value={item.label}
              clearable
              onInput={val => (item.label = val)}
            />
          </bk-form-item>
        </bk-form>
        <div class='add-btns'>
          <bk-button
            class='mr8'
            size='small'
            theme='primary'
            onClick={handleEditGroupSubmit}
          >
            {t('确定')}
          </bk-button>
          <bk-button
            size='small'
            onClick={handleEditGroupCancel}
          >
            {t('取消')}
          </bk-button>
        </div>
      </div>
    );
    return () => <div class='add-index-set-box'>{props.isFrom && renderAddIndexSet(props.data)}</div>;
  },
});
