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
import { defineComponent, shallowRef } from 'vue';

import { useI18n } from 'vue-i18n';

import MonitorDrag from '../../../components/monitor-drag/monitor-drag';

import './trace-explore-layout.scss';

export default defineComponent({
  name: 'TraceExploreLayout',
  setup() {
    const { t } = useI18n();
    const isShow = shallowRef(true);
    const maxWidth = shallowRef(400);
    const minWidth = shallowRef(120);
    const width = shallowRef(200);

    const handleDragChange = (w: number) => {
      if (w < minWidth.value) {
        handleClickShrink(false);
      } else {
        width.value = w;
      }
    };

    const handleClickShrink = (val?: boolean) => {
      isShow.value = val ?? !isShow.value;
      width.value = isShow.value ? 200 : 0;
    };

    return {
      isShow,
      maxWidth,
      minWidth,
      width,
      handleDragChange,
      handleClickShrink,
      t,
    };
  },
  render() {
    return (
      <div class='trace-explore-layout-comp'>
        <div class='layout-aside'>
          <div
            style={{ width: `${this.width}px` }}
            class='layout-aside-content'
          >
            {this.$slots.aside?.()}
          </div>

          {this.isShow ? (
            <MonitorDrag
              isShow={this.isShow}
              lineText=''
              maxWidth={this.maxWidth}
              minWidth={this.minWidth}
              startPlacement='right'
              theme='simple-line-round'
              onMove={this.handleDragChange}
            />
          ) : (
            <div
              class='expand-trigger'
              v-bk-tooltips={{ content: this.t('展开') }}
              onClick={() => this.handleClickShrink(true)}
            >
              <i class='icon-monitor icon-gongneng-shouqi' />
            </div>
          )}
        </div>
        <div class='layout-main'>{this.$slots.default?.()}</div>
      </div>
    );
  },
});
