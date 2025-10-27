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

import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';
import SubBar from '../../retrieve-v2/sub-bar/index.vue';
import useRetrieveEvent from '@/hooks/use-retrieve-event';
import './index.scss';

export default defineComponent({
  name: 'V3Toolbar',
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  setup() {
    const isFavoriteShown = ref(RetrieveHelper.isFavoriteShown);
    const onFavoriteShowChange = (val: boolean) => {
      isFavoriteShown.value = val;
    };

    const { addEvent } = useRetrieveEvent();
    addEvent(RetrieveEvent.FAVORITE_SHOWN_CHANGE, onFavoriteShowChange);

    const handleCollectionShowChange = () => {
      isFavoriteShown.value = !isFavoriteShown.value;
      RetrieveHelper.setFavoriteShown(isFavoriteShown.value);
    };

    return () => (
      <div class='v3-bklog-toolbar'>
        {!window.__IS_MONITOR_COMPONENT__ && (
          <div
            class={`collection-box ${isFavoriteShown.value ? 'active' : ''}`}
            onClick={handleCollectionShowChange}
          >
            <span
              style={{ color: isFavoriteShown.value ? '#3A84FF' : '' }}
              class='bklog-icon bklog-shoucangjia'
            ></span>
          </div>
        )}

        <SubBar></SubBar>
      </div>
    );
  },
});
