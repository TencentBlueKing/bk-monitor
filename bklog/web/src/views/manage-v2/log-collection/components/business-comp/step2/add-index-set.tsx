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

import { defineComponent, type PropType, ref, nextTick } from 'vue';

import useLocale from '@/hooks/use-locale';

import type { ListItemData } from '../../../type';

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

  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const inputRef = ref<any>();
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
        );
      }
      /** icon 模式 */
      return (
        <span class='icon-btns'>
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
    const renderAddIndexSet = (item: ListItemData) => (
      <div class={props.isFrom ? 'popover-add-index-set' : 'add-index-set-input-main'}>
        {props.isFrom && <div class='title'>{props.isAdd ? t('新建索引集') : t('重命名')}</div>}
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
            label={props.isFrom ? t('索引集名称') : ''}
            property='group_name'
            required
          >
            <bk-input
              ref={inputRef}
              placeholder={props.isFrom ? t('请输入') : t('请输入索引集名称')}
              // size={!props.isFrom && 'small'}
              value={item.label}
              clearable
              onInput={val => (item.label = val)}
            />
          </bk-form-item>
        </bk-form>
        {renderButtons()}
      </div>
    );

    return () => <div class='add-index-set-box'>{renderAddIndexSet(props.data)}</div>;
  },
});
