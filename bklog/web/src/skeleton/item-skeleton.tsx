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

import { computed, defineComponent } from 'vue';

import './item-skeleton.scss';

export default defineComponent({
  name: 'ItemSkeleton',
  props: {
    rows: {
      type: Number,
      default: 3,
    },
    columns: {
      type: Number,
      default: 1,
    },
    rowHeight: {
      type: String,
      default: '20px',
    },
    gap: {
      type: String,
      default: '8px',
    },
    widths: {
      type: Array,
      default: () => [],
    },
    type: {
      type: String,
      default: 'list', // 'text', 'card', 'list', 'grid'
    },
  },
  setup(props) {
    // 缓存宽度配置计算
    const computedWidths = computed(() => {
      if (props.widths.length > 0) {
        return props.widths;
      }

      // 使用映射表替代switch-case
      const widthMap = {
        text: ['100%', '80%', '60%', '90%'],
        card: ['100%'],
        list: ['70px', '1fr', '100px'],
        grid: new Array(props.columns).fill('1fr'),
      };

      return widthMap[props.type] || new Array(props.columns).fill('1fr');
    });

    // 预定义样式对象
    const rowBaseStyle = computed(() => ({
      display: 'flex',
      gap: props.gap,
      marginTop: props.gap,
      flexDirection: props.type === 'list' ? 'row' : 'column',
      alignItems: props.type === 'list' ? 'center' : 'stretch',
    }));

    const skeletonStyle = computed(() => ({
      height: props.rowHeight,
      borderRadius: '4px',
    }));

    // 优化渲染函数
    return () => {
      const rows: any[] = [];
      const { rows: rowCount, columns } = props;
      const widths = computedWidths.value;
      const rowStyle = rowBaseStyle.value;
      const skeletonBaseStyle = skeletonStyle.value;

      for (let i = 0; i < rowCount; i++) {
        const cols: any[] = [];

        for (let j = 0; j < columns; j++) {
          const width = widths[j] || widths[0] || '100%';

          cols.push(
            <div
              key={`col-${j}`}
              style={{ ...skeletonBaseStyle, width }}
              class='skeleton'
            />,
          );
        }

        rows.push(
          <div
            key={`row-${i}`}
            style={rowStyle}
            class='skeleton-row'
          >
            {cols}
          </div>,
        );
      }

      return <div class='bk-log-item-skeleton'>{rows}</div>;
    };
  },
});
