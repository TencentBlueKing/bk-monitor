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

import { defineComponent, ref } from 'vue';
import useLocale from '@/hooks/use-locale';
import './index.scss';

export default defineComponent({
  name: 'SecondConfirm',
  setup(_, { emit, expose }) {
    const { t } = useLocale();

    const secondConfirmRef = ref(null);
    const confirmLoading = ref(false);
    const typeList = ref([
      {
        icon: 'log-refresh',
        title: t('同步更新模板'),
        describe: t('影响其他使用模板的索引集'),
        isActive: true,
      },
      {
        icon: 'jiebang',
        title: t('与模板解除绑定'),
        describe: t('相关配置落地自定义'),
        isActive: false,
      },
    ]);
    let currentIndex = 0;

    const handleChooseItem = (rowIndex: number) => {
      currentIndex = rowIndex;
      typeList.value.forEach((item, index) => {
        if (index === rowIndex) {
          item.isActive = true;
        } else {
          item.isActive = false;
        }
      });
    };

    const handleConfirm = () => {
      confirmLoading.value = true;
      emit('confirm', currentIndex === 0 ? 'sync' : 'unbind');
    };

    const handleCancel = () => {
      confirmLoading.value = false;
      emit('cancel');
    };

    expose({
      getRef: () => secondConfirmRef.value,
      close: handleCancel,
    });

    return () => (
      <div style='display:none'>
        <div
          class='second-confirm-main'
          ref={secondConfirmRef}
        >
          <div class='title-main'>{t('当前使用了聚类模板')}</div>
          <div class='tip-main'>{t('如需保存当前配置，需要处理聚类模板')}:</div>
          {typeList.value.map((item, index) => (
            <div
              class={{ 'type-item': true, 'is-active': item.isActive }}
              on-click={() => handleChooseItem(index)}
            >
              <div class='icon-main'>
                <log-icon type={item.icon} />
              </div>
              <div class='content-main'>
                <div class='content-title'>{item.title}</div>
                <div class='describe'>{item.describe}</div>
              </div>
              <div class='check-icon'>
                <log-icon type='correct' />
              </div>
            </div>
          ))}
          <div class='operate-btns'>
            <bk-button
              theme='primary'
              size='small'
              loading={confirmLoading.value}
              on-click={handleConfirm}
            >
              {t('确定')}
            </bk-button>
            <bk-button
              size='small'
              on-click={handleCancel}
            >
              {t('取消')}
            </bk-button>
          </div>
        </div>
      </div>
    );
  },
});
