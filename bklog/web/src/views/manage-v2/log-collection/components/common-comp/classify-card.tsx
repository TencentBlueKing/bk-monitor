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

import { defineComponent, type PropType } from 'vue';

import './classify-card.scss';

// 使用 webpack 的 require.context 预加载该目录下的所有 png 资源
const iconsContext = (require as any).context('@/images/log-collection', false, /\.png$/);

export default defineComponent({
  name: 'ClassifyCard',
  props: {
    data: {
      type: Object as PropType<{ icon?: string; name?: string }>,
      default: () => ({}),
    },
    activeKey: {
      type: String,
      default: '',
    },
  },
  emits: ['choose'],

  setup(props, { emit }) {
    const resolveIconUrl = (iconName?: string) => {
      if (!iconName) {
        return '';
      }
      try {
        return iconsContext(`./${iconName}.png`);
      } catch (e) {
        console.log(e);
        return '';
      }
    };
    /** 选中 */
    const handleChoose = () => {
      emit('choose', props.data);
    };

    return () => (
      <div
        class={{
          'classify-card-main': true,
          active: props.activeKey === props.data?.value,
        }}
        on-Click={handleChoose}
      >
        <div
          style={{
            background: `url(${resolveIconUrl(props.data?.icon)})`,
            'background-size': '100% 100%',
          }}
          class='card-icon'
        />
        <div class='card-txt'>{props.data?.name}</div>
        <i class='bklog-icon bklog-correct icon-correct' />
      </div>
    );
  },
});
