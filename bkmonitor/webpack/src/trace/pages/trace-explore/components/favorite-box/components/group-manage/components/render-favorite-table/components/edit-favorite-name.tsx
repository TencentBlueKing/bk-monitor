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
import { type PropType, defineComponent, reactive, shallowRef } from 'vue';

import { Button, Form, Input, Message } from 'bkui-vue';
import { updateFavorite } from 'monitor-api/modules/model';
import { useI18n } from 'vue-i18n';

import useFavoriteType from '../../../../../hooks/use-favorite-type';
import useGroupList from '../../../../../hooks/use-group-list';

import type { IFavoriteGroup } from '../../../../../types';

import './edit-favorite-name.scss';

export default defineComponent({
  props: {
    data: {
      type: Object as PropType<IFavoriteGroup['favorites'][number]>,
    },
    theme: {
      type: String as PropType<'primary'>,
      default: '',
    },
  },
  setup(props) {
    const { t } = useI18n();
    const favoriteType = useFavoriteType();
    const { run: refreshGroupList } = useGroupList(favoriteType.value);

    const formRef = shallowRef<InstanceType<typeof Form>>();
    const nameRef = shallowRef<typeof Input>();
    const isEditing = shallowRef(false);
    const formData = reactive({
      name: '',
    });

    const handleEditStart = (event: Event) => {
      event.stopPropagation();
      isEditing.value = true;
      formData.name = props.data.name;
      setTimeout(() => {
        nameRef.value.focus();
      });
    };

    const handleSubmit = async () => {
      if (formData.name === props.data.name) {
        isEditing.value = false;
        return;
      }
      await formRef.value.validate();
      await updateFavorite(props.data.id, {
        type: favoriteType.value,
        ...formData,
      });
      refreshGroupList();
      isEditing.value = false;
      Message({
        theme: 'success',
        message: t('编辑成功'),
      });
    };

    return () => (
      <div class='favorite-box-edit-favorite-name'>
        {!isEditing.value && (
          <div class='value-wrapper'>
            <div class='value-text'>
              <Button
                theme={props.theme}
                text
              >
                {props.data.name}
              </Button>
            </div>
            <div
              class='edit-flag'
              onClick={handleEditStart}
            >
              <i class='icon-monitor icon-bianji' />
            </div>
          </div>
        )}
        {isEditing.value && (
          <Form
            ref={formRef}
            form-type='vertical'
            model={formData}
          >
            <Form.FormItem
              error-display-type='tooltips'
              property='name'
              required
            >
              <Input
                ref={nameRef}
                v-model={formData.name}
                onBlur={handleSubmit}
              />
            </Form.FormItem>
          </Form>
        )}
      </div>
    );
  },
});
