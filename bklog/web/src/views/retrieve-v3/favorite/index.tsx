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

import { computed, defineComponent, onMounted, ref } from 'vue';

import { throttle } from 'lodash-es';

import RetrieveHelper, { RetrieveEvent } from '../../retrieve-helper';
import CollectMain from './collect-main';
import DragContainer from './components/drag-container/drag-container';
import useRetrieveEvent from '@/hooks/use-retrieve-event';

import './index.scss';

export default defineComponent({
  name: 'V3Collection',

  emits: ['width-change'],

  setup(_, { emit }) {
    const isShow = ref(RetrieveHelper.isFavoriteShown);
    const collectWidth = ref(240);

    // 使用节流优化性能
    const handleShownChange = throttle((val: boolean) => {
      isShow.value = val;
    }, 100);

    const { addEvent } = useRetrieveEvent();
    addEvent(RetrieveEvent.FAVORITE_SHOWN_CHANGE, handleShownChange);

    /**
     * 处理宽度变化
     */
    const handleWidthChange = (width: number) => {
      collectWidth.value = width;
      RetrieveHelper.setFavoriteWidth(width);
      emit('width-change', width);
    };

    /**
     * 处理显示状态变化
     */
    const handleUpdateIsShow = (val: boolean) => {
      RetrieveHelper.setFavoriteShown(val);
      /** 2025-08-11 当左侧收藏夹收起的时候，清空当前收藏夹选中态  */
      // RetrieveHelper.setFavoriteActive({});
    };

    onMounted(() => {
      RetrieveHelper.setFavoriteWidth(collectWidth.value);
      emit('width-change', collectWidth.value);
    });

    const favoriteStyle = computed(() => ({
      minWidth: `${collectWidth.value}px`,
    }));

    return () => (
      <keep-alive>
        <DragContainer
          style={favoriteStyle.value}
          width={collectWidth.value}
          class='v3-bklog-collection'
          isShow={isShow.value}
          on={{
            'update:isShow': handleUpdateIsShow,
            'update:width': handleWidthChange,
          }}
        >
          <CollectMain
            isShowCollect={isShow.value}
            on-show-change={handleUpdateIsShow}
          />
        </DragContainer>
      </keep-alive>
    );
  },
});
