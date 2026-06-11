/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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

import { Button, Sideslider } from 'bkui-vue';

import './tapd-sideslider.scss';

export default defineComponent({
  name: 'TapdSideslider',
  props: {
    show: {
      type: Boolean,
      required: true,
    },
  },
  emits: ['update:show'],
  setup(_, { emit }) {
    const count = shallowRef(1);

    const handleShowChange = (isShow: boolean) => {
      emit('update:show', isShow);
    };

    return {
      count,
      handleShowChange,
    };
  },
  render() {
    return (
      <Sideslider
        width='80%'
        extCls='create-tapd-sides-slider'
        v-slots={{
          header: () => (
            <div class='create-tapd-side-slider-header'>
              <div class='create-tapd-side-slider-header-title'>{this.$t('TAPD 单据')}</div>
              <div class='tapd-auth-text'>
                <i class='icon-monitor icon-mc-check-fill' />
                <span class='tips-text'>
                  {this.$t('已授权 TAPD 项目列表 · 已关联 {count} 个项目', { count: this.count })},
                </span>
                <Button
                  class='cancel-auth-btn'
                  text
                >
                  {this.$t('解除授权')}
                </Button>
              </div>
            </div>
          ),
          default: () => (
            <div class='create-tapd-side-slider-content'>
              <div class='create-tapd-form-header' />

              <div class='create-tapd-footer'>
                <Button theme='primary'>{this.$t('确认创建')}</Button>
                <Button>{this.$t('取消')}</Button>
              </div>
            </div>
          ),
        }}
        isShow={this.show}
        onUpdate:isShow={this.handleShowChange}
      />
    );
  },
});
