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

import useLocale from '@/hooks/use-locale';

export default defineComponent({
  name: 'BatchInput',
  setup() {
    const showBtachDialog = ref(false);
    const { $t } = useLocale();
    const style = {
      color: '#3A84FF',
      padding: '2px 4px',
      cursor: 'pointer',
    };

    const handleMouseup = (e: MouseEvent) => {
      e.stopPropagation();
      e.preventDefault();
      e.stopImmediatePropagation();
    };
    return () => (
      <span
        style={style}
        onClick={() => (showBtachDialog.value = true)}
      >
        {$t('批量输入')}
        <bk-dialog
          width='860px'
          title={$t('批量输入')}
          value={showBtachDialog.value}
        >
          <div
            style='display: flex; padding: 16px 24px;'
            onMouseup={handleMouseup}
          >
            <div style='width: 400px; height: 358px;'>
              <div>解析文本</div>
              <div>
                <bk-input
                  maxlength={100}
                  placeholder='请使用，；｜换行等进行分隔'
                  rows={16}
                  type='textarea'
                ></bk-input>
              </div>
              <div style='margin-top: 16px;display: flex;justify-content: space-between;'>
                <bk-button
                  style='width: 280px'
                  outline={true}
                  theme='primary'
                >
                  点击解析
                </bk-button>
                <bk-button>清空</bk-button>
              </div>
            </div>
            <div style='width: 460px; margin-left: 16px;'>
              <div>选择解析结果</div>
              <bk-table></bk-table>
            </div>
          </div>
        </bk-dialog>
      </span>
    );
  },
});
