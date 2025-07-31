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
import { defineComponent, reactive, shallowRef } from 'vue';

import { Button, Form, Input } from 'bkui-vue';
import { createFavoriteGroup } from 'monitor-api/modules/model';
import { useI18n } from 'vue-i18n';

import { useAppStore } from '../../../../../store/modules/app';
import useFavoriteType from '../hooks/use-favorite-type';
import useGroupList from '../hooks/use-group-list';
import { validatorGroupName } from '../utils';

import './create-group-extends.scss';

export default defineComponent({
  emits: ['success'],
  setup(props, context) {
    const favoriteType = useFavoriteType();
    const { t } = useI18n();
    const store = useAppStore();
    const { run: refreshGroupList } = useGroupList(favoriteType.value);

    const rules = {
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
      ],
    };

    const formRef = shallowRef<InstanceType<typeof Form>>();
    const isShowCreate = shallowRef(false);
    const isSubmiting = shallowRef(false);

    const formData = reactive({
      name: '',
    });

    const handleShowCreate = () => {
      isShowCreate.value = true;
    };

    const handleCancel = () => {
      isShowCreate.value = false;
    };

    const handleSubmit = async () => {
      try {
        isSubmiting.value = true;
        await formRef.value.validate();
        await createFavoriteGroup({
          bk_biz_id: store.bizId,
          type: favoriteType.value,
          ...formData,
        });
        refreshGroupList();
        isShowCreate.value = false;
        context.emit('success', formData.name);
      } finally {
        isSubmiting.value = false;
      }
    };

    return () => {
      return !isShowCreate.value ? (
        <div
          class='favorite-box-create-group-extend'
          onClick={handleShowCreate}
        >
          <i class='icon-monitor icon-jia' />
          <span style='margin-left: 4px;'>{t('新建分组')}</span>
        </div>
      ) : (
        <div class='favorite-box-create-group-extend-form'>
          <Form
            ref={formRef}
            form-type='vertical'
            model={formData}
            rules={rules}
          >
            <Form.FormItem
              error-display-type='tooltips'
              property='name'
              required
            >
              <Input
                v-model={formData.name}
                maxcharacter={30}
                clearable
                show-word-limit
              />
            </Form.FormItem>
          </Form>
          <Button
            loading={isSubmiting.value}
            theme='primary'
            text
            onClick={handleSubmit}
          >
            <i class='icon-monitor icon-mc-check-small' />
          </Button>
          <Button
            text
            onClick={handleCancel}
          >
            <i class='icon-monitor icon-mc-close' />
          </Button>
        </div>
      );
    };
  },
});
