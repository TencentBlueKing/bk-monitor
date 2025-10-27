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

import { defineComponent, ref, computed, nextTick } from 'vue';

import useLocale from '@/hooks/use-locale';

export default defineComponent({
  name: 'TextFilter',
  setup(_, { expose }) {
    const { t } = useLocale();

    const filterType = ref(''); // 过滤类型
    const filterContent = ref({
      // 关键字过滤
      keyword: '',
      keyword_type: 'keyword_and',
      // 关键字范围
      start: '',
      end: '',
      // 最新行数
      line_num: 0,
      // 按行过滤
      start_line: 0,
      end_line: 0,
    });

    // 过滤选项列表
    const filterList = computed(() => [
      {
        id: 'match_word',
        name: t('关键字过滤'),
      },
      {
        id: 'match_range',
        name: t('关键字范围'),
      },
      {
        id: 'tail_line',
        name: t('最新行数'),
      },
      {
        id: 'line_range',
        name: t('按行过滤'),
      },
    ]);

    // 关键字类型列表
    const keywordTypeList = computed(() => [
      {
        id: 'keyword_and',
        name: t('与'),
      },
      {
        id: 'keyword_or',
        name: t('或'),
      },
      {
        id: 'keyword_not',
        name: t('非'),
      },
    ]);

    // 处理克隆数据
    const handleClone = ({ filter_type: filterTypeVal, filter_content: filterContentVal }: any) => {
      filterType.value = filterTypeVal;
      Object.assign(filterContent.value, filterContentVal);
    };

    // 处理数字输入变化
    const handleChangeNumber = (key: string, val: any) => {
      const num = Number(val);
      if (num <= 0 && val !== '') {
        // 保证大于0并触发响应式数据更新
        filterContent.value[key] = -1;
        nextTick(() => {
          filterContent.value[key] = 0;
        });
      } else {
        filterContent.value[key] = num;
      }
    };

    // 暴露方法和属性
    expose({
      handleClone,
      filterType,
      filterContent,
    });

    // 主渲染函数
    return () => (
      <div style='display: flex; align-items: center'>
        {/* 过滤类型选择器 */}
        <bk-select
          style='width: 174px; margin-right: 20px; background-color: #fff'
          value={filterType.value}
          onChange={(val: string) => (filterType.value = val)}
        >
          {filterList.value.map(option => (
            <bk-option
              id={option.id}
              key={option.id}
              name={option.name}
            />
          ))}
        </bk-select>

        {/* 关键字过滤 */}
        {filterType.value === 'match_word' && (
          <div style='display: flex; align-items: center'>
            <bk-input
              style='width: 300px'
              data-test-id='addNewExtraction_input_filterKeyword'
              maxlength={64}
              placeholder={t('多个关键字用英文逗号')}
              value={filterContent.value.keyword}
              onChange={(val: string) => (filterContent.value.keyword = val)}
            />
            <bk-select
              style='width: 70px; margin-right: 10px; background-color: #fff'
              clearable={false}
              data-test-id='addNewExtraction_select_filterCondition'
              value={filterContent.value.keyword_type}
              onChange={(val: string) => (filterContent.value.keyword_type = val)}
            >
              {keywordTypeList.value.map(option => (
                <bk-option
                  id={option.id}
                  key={option.id}
                  name={option.name}
                />
              ))}
            </bk-select>
            {t('关键字匹配模式')}
          </div>
        )}

        {/* 关键字范围 */}
        {filterType.value === 'match_range' && (
          <div>
            <i18n
              style='display: flex; align-items: center'
              path='从匹配{0}开始到匹配{1}之间的所有行'
            >
              <bk-input
                style='width: 180px; margin: 0 6px'
                maxlength={64}
                value={filterContent.value.start}
                onChange={(val: string) => (filterContent.value.start = val)}
              />
              <bk-input
                style='width: 180px; margin: 0 6px'
                maxlength={64}
                value={filterContent.value.end}
                onChange={(val: string) => (filterContent.value.end = val)}
              />
            </i18n>
          </div>
        )}

        {/* 最新行数 */}
        {filterType.value === 'tail_line' && (
          <div style='display: flex; align-items: center'>
            <bk-input
              style='width: 120px'
              placeholder={t('请输入整数')}
              precision={0}
              type='number'
              value={filterContent.value.line_num}
              onChange={(val: any) => handleChangeNumber('line_num', val)}
            />
          </div>
        )}

        {/* 按行过滤 */}
        {filterType.value === 'line_range' && (
          <div>
            <i18n
              style='display: flex; align-items: center'
              path='从第{0}行到第{1}行'
            >
              <bk-input
                style='width: 120px; margin: 0 6px'
                placeholder={t('请输入整数')}
                precision={0}
                type='number'
                value={filterContent.value.start_line}
                onChange={(val: any) => handleChangeNumber('start_line', val)}
              />
              <bk-input
                style='width: 120px; margin: 0 6px'
                placeholder={t('请输入整数')}
                precision={0}
                type='number'
                value={filterContent.value.end_line}
                onChange={(val: any) => handleChangeNumber('end_line', val)}
              />
            </i18n>
          </div>
        )}
      </div>
    );
  },
});
