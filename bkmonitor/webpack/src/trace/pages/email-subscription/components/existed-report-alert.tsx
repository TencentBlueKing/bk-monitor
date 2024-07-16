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

import { Alert } from 'bkui-vue';

type ExistedReportListItem = {
  id: number;
  name: string;
};

export default defineComponent({
  name: 'ExistedReportAlert',
  props: {
    existedReportList: {
      type: Array as PropType<ExistedReportListItem[]>,
      default: () => {
        return [];
      },
    },
  },
  emits: ['ReportNameClick'],
  setup(props, { emit }) {
    return {
      props,
      emit,
    };
  },
  render() {
    return (
      <Alert
        v-slots={{
          title: () => {
            return (
              <div>
                <i18n-t
                  v-slots={{
                    btn: () => {
                      return this.existedReportList.map((item, index) => {
                        return (
                          <span>
                            <span
                              style='color: #3A84FF;cursor: pointer;'
                              onClick={() => this.emit('ReportNameClick', item.id)}
                            >
                              {item.name}
                            </span>
                            {index + 1 === this.existedReportList.length ? '' : ' , '}
                          </span>
                        );
                      });
                    },
                  }}
                  keypath='当前已存在相同索引集的订阅 {btn} ，请确认是否要创建新订阅或是直接修改已有订阅内容？'
                />
              </div>
            );
          },
        }}
        theme='warning'
      />
    );
  },
});
