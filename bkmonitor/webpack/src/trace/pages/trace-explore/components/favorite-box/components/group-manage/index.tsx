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
import { type PropType, type UnwrapRef, defineComponent, shallowRef, Teleport } from 'vue';

import { useI18n } from 'vue-i18n';

import RenderFavoriteTable from './components/render-favorite-table/index';
import RenderGroupList from './components/render-group-list';

import './index.scss';

export default defineComponent({
  name: 'RenderGroupList',
  props: {
    isShow: {
      type: Boolean as PropType<boolean>,
    },
    type: {
      type: String,
    },
  },
  emits: ['close'],
  setup(_, context) {
    const { t } = useI18n();

    const currentGroupId = shallowRef<null | number | string>('all');

    const handleGroupChange = (data: UnwrapRef<typeof currentGroupId>) => {
      currentGroupId.value = data;
    };

    const handleClose = () => {
      context.emit('close', false);
    };

    return () => (
      <div>
        <Teleport to='body'>
          <div class='bk-monitor-favorite-box-manage'>
            <div class='manage-title'>
              <i
                class='icon-monitor icon-back-left close-btn'
                onClick={handleClose}
              />
              {t('收藏管理')}
            </div>
            <div class='layout-container'>
              <div class='layout-group-list'>
                <RenderGroupList onChange={handleGroupChange} />
              </div>
              <div class='layout-favorite-table'>
                <RenderFavoriteTable groupId={currentGroupId.value} />
              </div>
            </div>
          </div>
        </Teleport>
      </div>
    );
  },
});
