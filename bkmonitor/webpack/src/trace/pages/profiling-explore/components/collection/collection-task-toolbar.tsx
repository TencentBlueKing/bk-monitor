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
import { defineComponent } from 'vue';

import { Alert, Button, Input } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './collection-task-toolbar.scss';

export default defineComponent({
  name: 'CollectionTaskToolbar',
  props: {
    keyword: { type: String, default: '' },
    loading: { type: Boolean, default: false },
  },
  emits: {
    keywordChange: (_value: string) => true,
    refresh: () => true,
  },
  setup() {
    return { t: useI18n().t };
  },
  render() {
    return (
      <div class='collection-task-toolbar'>
        <div class='collection-task-toolbar-header'>
          <Alert
            class='collection-task-guide'
            v-slots={{
              title: () => (
                <i18n-t keypath='新建任务：如果选择 <{0}> 提交后将马上进入<采集任务历史>；如果选择 <{1} / {2}> 将进入下方的 <定时任务列表>。'>
                  <b>{this.t('立即执行')}</b>
                  <b>{this.t('指定时间')}</b>
                  <b>{this.t('周期执行')}</b>
                </i18n-t>
              ),
            }}
            theme='info'
          />
          <div class='collection-task-toolbar-bar'>
            <Input
              class='collection-task-search'
              modelValue={this.keyword}
              placeholder={this.t('搜索任务名称')}
              type='search'
              clearable
              onClear={() => this.$emit('keywordChange', '')}
              onInput={keyword => this.$emit('keywordChange', keyword)}
            />
            <Button
              loading={this.loading}
              onClick={() => this.$emit('refresh')}
            >
              {this.t('刷新')}
            </Button>
          </div>
        </div>
        <div class='collection-task-toolbar-content'>{this.$slots.default?.()}</div>
      </div>
    );
  },
});
