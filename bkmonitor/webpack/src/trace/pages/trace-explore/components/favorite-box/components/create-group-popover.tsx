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
import { defineComponent, onBeforeUnmount, onMounted, reactive, shallowRef } from 'vue';

import { Button, Form, Input } from 'bkui-vue';
import _ from 'lodash';
import { createFavoriteGroup } from 'monitor-api/modules/model';
import tippy, { type Instance, type SingleTarget } from 'tippy.js';
import { useI18n } from 'vue-i18n';

import { useAppStore } from '../../../../../store/modules/app';
import useFavoriteType from '../hooks/use-favorite-type';
import useGroupList from '../hooks/use-group-list';
import { validatorGroupName } from '../utils';

import './create-group-popover.scss';

export default defineComponent({
  setup(props, context) {
    const { t } = useI18n();
    const favoriteType = useFavoriteType();
    const store = useAppStore();
    const { run: refreshGroupList, data: groupList } = useGroupList(favoriteType.value);

    let tippyInstance: Instance;

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
        {
          validator: (value: string) => {
            return !_.find(groupList.value, item => item.name === value);
          },
          message: t('注意: 名字冲突'),
          trigger: 'change',
        },
      ],
    };

    const rootRef = shallowRef<HTMLElement>();
    const panelRef = shallowRef<HTMLElement>();
    const formRef = shallowRef<InstanceType<typeof Form>>();
    const isSubmiting = shallowRef(false);

    const formData = reactive({
      name: '',
    });

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
        tippyInstance.hide();
      } finally {
        isSubmiting.value = false;
      }
    };

    const handleCancel = () => {
      tippyInstance.hide();
    };

    onMounted(() => {
      tippyInstance = tippy(rootRef.value as SingleTarget, {
        content: panelRef.value as any,
        trigger: 'click',
        placement: 'bottom-start',
        theme: 'light favorite-group-create-panel',
        interactive: true,
        hideOnClick: true,
        zIndex: 99,
        onShow: () => {
          formData.name = '';
          formRef.value?.clearValidate();
        },
      });
      onBeforeUnmount(() => {
        tippyInstance.hide();
        tippyInstance.destroy();
      });
    });

    return () => (
      <div v-bk-tooltips={t('新建分组')}>
        <span ref={rootRef}>{context.slots?.default()}</span>
        <div ref={panelRef}>
          <Form
            ref={formRef}
            form-type='vertical'
            model={formData}
            rules={rules}
          >
            <Form.FormItem
              error-display-type='tooltips'
              label={t('分组名称')}
              property='name'
              required
            >
              <Input
                v-model={formData.name}
                maxcharacter={30}
                placeholder={t('请输入分组名')}
                clearable
                showWordLimit
              />
            </Form.FormItem>
          </Form>
          <div class='footer'>
            <Button
              loading={isSubmiting.value}
              size='small'
              theme='primary'
              onClick={handleSubmit}
            >
              {t('确定')}
            </Button>
            <Button
              size='small'
              onClick={handleCancel}
            >
              {t('取消')}
            </Button>
          </div>
        </div>
      </div>
    );
  },
});
