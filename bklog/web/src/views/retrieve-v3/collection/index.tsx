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

import V2Collection from '../../retrieve-v2/collect/collect-index';

import './index.scss';

export default defineComponent({
  name: 'V3Collection',
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['width-change'],
  setup(props, { emit }) {
    const showContent = computed(() => props.isShow);
    const collectWidth = ref(240);
    const handleWidthChange = (width: number) => {
      collectWidth.value = width;
      emit('width-change', width);
    };

    onMounted(() => {
      emit('width-change', collectWidth.value);
    });

    return () => {
      return (
        <V2Collection
          width={collectWidth.value}
          onUpdate:width={handleWidthChange}
          class='v3-bklog-collection'
          is-show={showContent.value}
        ></V2Collection>
      );
    };
  },
});
