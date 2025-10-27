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

import { defineComponent, PropType, ref } from 'vue';
import useLocale from '@/hooks/use-locale';
import { bkMessage } from 'bk-magic-vue';
import $http from '@/api';
import { type TemplateItem } from '../../../index';
import './index.scss';

export default defineComponent({
  name: 'DeleteTemplate',
  props: {
    data: {
      type: Object as PropType<TemplateItem>,
      default: () => ({}),
    },
  },
  setup(props, { emit }) {
    const { t } = useLocale();

    const confirmLoading = ref(false);

    const handleConfirm = () => {
      confirmLoading.value = true;
      $http
        .request('logClustering/deleteTemplate', {
          params: {
            regex_template_id: props.data.id,
          },
        })
        .then(res => {
          if (res.code === 0) {
            bkMessage({
              theme: 'success',
              message: t('操作成功'),
            });
            emit('success');
          }
        })
        .catch(err => {
          console.error(err);
        })
        .finally(() => {
          confirmLoading.value = false;
        });
    };

    const handleCancel = () => {
      emit('cancel');
    };

    return () => (
      <div class='delete-template-main'>
        <div class='title-main'>{t('确认删除该模板？')}</div>
        <div class='name-display'>
          <span class='title'>{t('模板名称')}</span>：<span>{props.data.template_name}</span>
        </div>
        <div>
          <i18n
            style='color:#4D4F56'
            path='删除后，使用该模板的 {0} 个 {1} 将与模板 {2}，相关配置转成 {3}'
          >
            <span style='color:#3A84FF;font-weight:700'>{props.data.related_index_set_list.length}</span>
            <span style='font-weight:700'>{t('索引集')}</span>
            <span style='font-weight:700'>{t('解绑')}</span>
            <span style='font-weight:700'>{t('自定义')}</span>
          </i18n>
        </div>
        <div class='operate-btns'>
          <bk-button
            theme='primary'
            class='confirm-btn'
            size='small'
            loading={confirmLoading.value}
            on-click={handleConfirm}
          >
            {t('删除')}
          </bk-button>
          <bk-button
            size='small'
            class='cancel-btn'
            on-click={handleCancel}
          >
            {t('取消')}
          </bk-button>
        </div>
      </div>
    );
  },
});
