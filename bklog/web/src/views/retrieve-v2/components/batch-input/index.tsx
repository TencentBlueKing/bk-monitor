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
import { defineComponent, ref, nextTick } from 'vue';

import { messageError } from '@/common/bkmagic';
import useLocale from '@/hooks/use-locale';

export default defineComponent({
  name: 'BatchInput',
  emits: ['value-change', 'show-change'],
  setup(_, { emit }) {
    const showBtachDialog = ref(false);
    const textValue = ref('');
    const splitResult = ref([]);
    const selectResult = ref([]);
    const { $t } = useLocale();
    const style = {
      color: '#3A84FF',
      padding: '2px 4px',
      cursor: 'pointer',
    };

    const handleDialogValueChange = isShow => {
      nextTick(() => {
        handleClearBtnClick();
      });
      showBtachDialog.value = isShow;
      emit('show-change', isShow);
    };

    const handleInputTextChange = val => {
      textValue.value = val;
    };

    const splitComplexTextEnhanced = text => {
      if (!text || typeof text !== 'string') {
        return [];
      }

      const result: string[] = [];

      // 使用更精确的正则表达式和exec循环
      const pattern = /"([^"]*)"|'([^']*)'|"([^"]*)"|'([^']*)'|([^,，;；|｜\r\n]+)/g;

      let match: any;
      while ((match = pattern.exec(text)) !== null) {
        // match[1-4] 是各种引号内的内容（不包括引号）
        // match[5] 是非分隔符内容
        let content = match[1] ?? match[2] ?? match[3] ?? match[4] ?? match[5];

        // 如果是普通内容（match[5]），需要trim
        if (match[5]) {
          content = content.trim();
        }

        // 只添加非空内容
        if (content !== undefined && content !== '') {
          result.push(content);
        }
      }

      return result;
    };

    const handleResolveBtnClick = () => {
      if (textValue.value.length) {
        splitResult.value = splitComplexTextEnhanced(textValue.value);
        return;
      }

      messageError('请输入需要解析的文本');
    };

    const handleClearBtnClick = () => {
      splitResult.value = [];
      textValue.value = '';
    };
    const handleConfirm = () => {
      emit('value-change', selectResult.value);
      showBtachDialog.value = false;
    };

    const handleSelect = selectedRows => {
      selectResult.value = selectedRows;
    };
    return () => (
      <span
        style={style}
        onClick={() => (showBtachDialog.value = true)}
      >
        {$t('批量输入')}
        <bk-dialog
          width='860px'
          header-position='left'
          mask-close={false}
          title={$t('批量输入')}
          value={showBtachDialog.value}
          on-value-change={handleDialogValueChange}
        >
          <div style='display: flex; padding: 16px 0px;'>
            <div style='width: 400px; height: 358px;'>
              <div style='padding-bottom: 6px'>
                解析文本<span style='color: #EA3636; padding-left: 2px;'>*</span>
              </div>
              <div>
                <bk-input
                  maxlength={100}
                  placeholder='请使用，；｜换行等进行分隔'
                  rows={16}
                  type='textarea'
                  value={textValue.value}
                  on-change={handleInputTextChange}
                />
              </div>
              <div style='margin-top: 16px;display: flex;justify-content: space-between;'>
                <bk-button
                  style='width: 280px;margin-right: 8px'
                  outline={true}
                  theme='primary'
                  on-click={handleResolveBtnClick}
                >
                  点击解析
                </bk-button>
                <bk-button on-click={handleClearBtnClick}>清空</bk-button>
              </div>
            </div>
            <div style='width: 460px; margin-left: 16px;'>
              <div style='padding-bottom: 6px'>选择解析结果</div>
              <bk-table
                data={splitResult.value}
                empty-text={$t('请先在右侧输入并解析')}
                max-height='316'
                on-select={handleSelect}
                onselect-all={handleSelect}
              >
                <bk-table-column type='selection' />
                <bk-table-column
                  scopedSlots={{
                    default: ({ row }) => {
                      return row;
                    },
                  }}
                  label='解析结果'
                />
              </bk-table>
            </div>
          </div>
          <div slot='footer'>
            <bk-button
              style='margin-right: 8px'
              class='btn-confirm'
              disabled={!selectResult.value.length}
              theme='primary'
              on-click={handleConfirm}
            >
              确认
            </bk-button>
            <bk-button
              class='btn-cancel'
              onClick={() => (showBtachDialog.value = false)}
            >
              取消
            </bk-button>
          </div>
        </bk-dialog>
      </span>
    );
  },
});
