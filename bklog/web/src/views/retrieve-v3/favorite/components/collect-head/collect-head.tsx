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

import FavoriteManageDialog from '../../../../retrieve-v2/collect/favorite-manage-dialog.vue';

import './collect-head.scss';

export default defineComponent({
  name: 'CollectHead',
  props: {
    total: {
      type: Number,
      default: 0,
    },
  },
  emits: ['collapse'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const isShowManageDialog = ref(false);
    /** 收藏管理 */
    const handleFavoriteSettingClick = () => {
      isShowManageDialog.value = true;
    };
    /** 收起 */
    const handleCollapse = () => {
      emit('collapse');
    };
    /** 关闭收藏管理 */
    const closeShowManageDialog = () => {
      isShowManageDialog.value = false;
    };

    return () => (
      <div class='collect-head-box'>
        <span class='collect-head-box-left'>
          <span class='collect-head-box-left-title'>{t('收藏夹')}</span>
          <span class='collect-head-box-left-num'>{props.total}</span>
        </span>
        <span class='collect-head-box-right'>
          <span
            class='bklog-icon bklog-shezhi box-icon'
            onClick={handleFavoriteSettingClick}
          ></span>
          <span
            class='bklog-icon bklog-collapse box-icon'
            onClick={handleCollapse}
          ></span>
        </span>
        {/* 收藏管理弹框 */}
        <FavoriteManageDialog
          modelValue={isShowManageDialog.value}
          on-close={closeShowManageDialog}
        />
      </div>
    );
  },
});
