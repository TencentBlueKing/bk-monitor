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
import { defineComponent, onBeforeUnmount, onMounted, shallowRef } from 'vue';

import { useStorage } from '@vueuse/core';
import { Button, Radio } from 'bkui-vue';
import tippy, { type Instance, type SingleTarget } from 'tippy.js';
import { useI18n } from 'vue-i18n';

import { FAVORITE_SORT_TYPE_KEY } from '../constants';
import useFavoriteType from '../hooks/use-favorite-type';
import useGroupList from '../hooks/use-group-list';

import './group-favorite-sort.scss';

export default defineComponent({
  setup() {
    let tippyInstance: Instance;

    const { t } = useI18n();
    const favoriteType = useFavoriteType();
    const { run: refreshGroupList } = useGroupList(favoriteType.value);
    const orderType = useStorage(FAVORITE_SORT_TYPE_KEY, 'asc');

    const rootRef = shallowRef<HTMLElement>();
    const panelRef = shallowRef<HTMLElement>();
    const orderTypeTemp = shallowRef('');

    const handleSubmit = () => {
      orderType.value = orderTypeTemp.value;
      tippyInstance.hide();
      refreshGroupList();
    };

    const handleCancel = () => {
      tippyInstance.hide();
    };

    onMounted(() => {
      tippyInstance = tippy(rootRef.value as SingleTarget, {
        content: panelRef.value as any,
        trigger: 'click',
        placement: 'bottom',
        theme: 'light favorite-box-favorite-sort-panel',
        interactive: true,
        hideOnClick: true,
        zIndex: 99,
        appendTo: () => document.body,
        onShow() {
          orderTypeTemp.value = orderType.value;
        },
      });
      onBeforeUnmount(() => {
        tippyInstance.hide();
        tippyInstance.destroy();
      });
    });
    return () => {
      return (
        <div v-bk-tooltips={t('收藏排序')}>
          <span
            ref={rootRef}
            class='icon-monitor icon-paixu1'
          />
          <div ref={panelRef}>
            <div style='font-size: 14px;'>{t('收藏排序')}</div>
            <Radio.Group v-model={orderTypeTemp.value}>
              <Radio label='asc'>{t('按名称 A - Z 排序')}</Radio>
              <Radio label='desc'>{t('按名称 Z - A 排序')}</Radio>
              <Radio label='update'>{t('按更新时间排序')}</Radio>
            </Radio.Group>
            <div class='footer'>
              <Button
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
    };
  },
});
