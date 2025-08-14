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
import { type PropType, defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import useFavoriteType from '../../../../../hooks/use-favorite-type';
import RenderFavoriteDataId from '../../../../favorite-info/render-favorite-data-id';
import RenderFavoriteQuery from '../../../../favorite-info/render-favorite-query';
import EditFavoriteGroup from './edit-favorite-group';
import EditFavoriteName from './edit-favorite-name';

import type { IFavoriteGroup } from '../../../../../types';

import './favorite-detail.scss';

export default defineComponent({
  props: {
    data: {
      type: Object as PropType<IFavoriteGroup['favorites'][number]>,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const favoriteType = useFavoriteType();

    return () => {
      return (
        <div class='favorite-box-group-manage-favorite-detail'>
          <div class='header'>{t('收藏详情')}</div>
          <div>
            <div class='form-item'>
              <div class='form-item-label'>{t('收藏名称:')}</div>
              <div class='form-item-content'>
                <EditFavoriteName data={props.data} />
              </div>
            </div>
            <div class='form-item'>
              <div class='form-item-label'>{t('所属组:')}</div>
              <div class='form-item-content'>
                <EditFavoriteGroup data={props.data} />
              </div>
            </div>
            {favoriteType.value === 'event' && (
              <div class='form-item'>
                <div class='form-item-label'>{t('数据ID:')}</div>
                <div class='form-item-content'>
                  <RenderFavoriteDataId data={props.data} />
                </div>
              </div>
            )}
            <div class='form-item'>
              <div class='form-item-label'>{t('查询语句:')}</div>
              <div class='form-item-content'>
                <RenderFavoriteQuery data={props.data} />
              </div>
            </div>
          </div>
        </div>
      );
    };
  },
});
