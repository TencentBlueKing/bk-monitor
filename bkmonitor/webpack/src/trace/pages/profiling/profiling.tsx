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

import { defineComponent, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Button, Form, ResizeLayout, Select, Switcher } from 'bkui-vue';

import { debounce } from '../../../monitor-common/utils/utils';
import { getDefautTimezone } from '../../../monitor-pc/i18n/dayjs';
import { DEFAULT_TIME_RANGE } from '../../components/time-range/utils';

import PageHeader, { ToolsFormData } from './components/page-header';
import EmptyCard from './empty-card';
import { SearchType } from './typings';

import './profiling.scss';

export default defineComponent({
  name: 'ProfilingPage',
  setup() {
    const { t } = useI18n();
    const searchFormData = reactive({
      autoQuery: true
    });
    const isShowFavorite = ref(false);
    const isShowSearch = ref(true);
    const searchType = ref<SearchType>(SearchType.Profiling); // 检索类型
    const toolsFormData = ref<ToolsFormData>({
      timeRange: DEFAULT_TIME_RANGE,
      timezone: getDefautTimezone(),
      refreshInterval: -1
    });
    function handleToolFormDataChange(val: ToolsFormData) {
      toolsFormData.value = val;
      handleQueryScopeDebounce();
    }
    function handleShowTypeChange(type: 'search' | 'favorite') {
      if (type === 'search') isShowSearch.value = !isShowSearch.value;
      else isShowFavorite.value = !isShowFavorite.value;
    }

    const handleQueryScopeDebounce = debounce(handleQuery, 300, false);

    function handleQuery(isBtnClick = false) {
      if (!isBtnClick && !searchFormData.autoQuery) return;
    }
    function handleSearchTypeChange(type: SearchType) {
      searchType.value = type;
    }
    return {
      t,
      isShowFavorite,
      isShowSearch,
      toolsFormData,
      searchType,
      handleToolFormDataChange,
      handleShowTypeChange,
      handleSearchTypeChange
    };
  },

  render() {
    const createProfilingComp = () => {
      return (
        <>
          <Form
            class='aside-common-form'
            formType='vertical'
          >
            <Form.FormItem label={this.$t('应用 / 服务')}>
              <div style='display: flex'>
                <Select style='flex: 1'></Select>
                <span class='icon-monitor icon-mc-copy-fill copy-icon'></span>
              </div>
            </Form.FormItem>
          </Form>
          <div class='aside-compare'>
            {this.$t('对比模式')} <Switcher size='small' />
          </div>
          <div class='search-title'>{this.$t('查询项')}</div>
          <Form
            class='aside-common-form'
            formType='vertical'
          >
            <Form.FormItem
              v-slots={{
                label: () => (
                  <span style='display:flex;align-items:center;'>
                    {this.$t('服务名称')} <span class='label-equal'>=</span>
                  </span>
                )
              }}
            >
              <Select></Select>
            </Form.FormItem>
            <Form.FormItem
              v-slots={{
                label: () => (
                  <span style='display:flex;align-items:center;'>
                    {this.$t('接口名称')} <span class='label-equal'>=</span>
                  </span>
                )
              }}
            >
              <Select></Select>
            </Form.FormItem>
          </Form>
          <Button
            class='add-button'
            outline
            theme='primary'
          >
            <span class='icon-monitor icon-mc-add add-icon' /> {this.$t('添加条件')}
          </Button>
          <div class='search-title'>{this.$t('对比项')}</div>
          <Form
            class='aside-common-form'
            formType='vertical'
          >
            <Form.FormItem
              v-slots={{
                label: () => (
                  <span style='display:flex;align-items:center;'>
                    {this.$t('服务名称')} <span class='label-equal'>=</span>
                  </span>
                )
              }}
            >
              <Select></Select>
            </Form.FormItem>
            <Form.FormItem
              v-slots={{
                label: () => (
                  <span style='display:flex;align-items:center;'>
                    {this.$t('接口名称')} <span class='label-equal'>=</span>
                  </span>
                )
              }}
            >
              <Select></Select>
            </Form.FormItem>
          </Form>
          <Button
            class='add-button'
            outline
            theme='primary'
          >
            <span class='icon-monitor icon-mc-add add-icon' /> {this.$t('添加条件')}
          </Button>
        </>
      );
    };
    const createUploadComp = () => {
      return (
        <>
          <div class='aside-compare'>
            {this.$t('对比模式')} <Switcher size='small' />
          </div>
          <Form
            class='aside-common-form'
            formType='vertical'
          >
            <Form.FormItem
              v-slots={{
                label: () => (
                  <span style='display:flex;align-items:center;'>
                    {this.$t('服务名称')} <span class='label-equal'>=</span>
                  </span>
                )
              }}
            >
              <Select></Select>
            </Form.FormItem>
            <Form.FormItem
              v-slots={{
                label: () => (
                  <span style='display:flex;align-items:center;'>
                    {this.$t('接口名称')} <span class='label-equal'>=</span>
                  </span>
                )
              }}
            >
              <Select></Select>
            </Form.FormItem>
          </Form>
          <Button
            class='add-button'
            outline
            theme='primary'
          >
            <span class='icon-monitor icon-mc-add add-icon' /> {this.$t('添加条件')}
          </Button>
        </>
      );
    };
    return (
      <div class='profiling-page'>
        <PageHeader
          v-model={this.toolsFormData}
          isShowFavorite={this.isShowFavorite}
          isShowSearch={this.isShowSearch}
          onShowTypeChange={this.handleShowTypeChange}
          onChange={this.handleToolFormDataChange}
        ></PageHeader>
        <ResizeLayout
          class='profiling-page-content'
          immediate={true}
          min={200}
          max={800}
          v-slots={{
            aside: () => (
              <div class='aside-wrap'>
                <div class='aside-title'>Profiling 检索</div>
                <Button.ButtonGroup class='aside-button-group'>
                  <Button
                    selected={this.searchType === SearchType.Profiling}
                    onClick={() => this.handleSearchTypeChange(SearchType.Profiling)}
                  >
                    {this.$t('持续 Profiling')}
                  </Button>
                  <Button
                    selected={this.searchType === SearchType.Upload}
                    onClick={() => this.handleSearchTypeChange(SearchType.Upload)}
                  >
                    {this.$t('上传 Profiling')}
                  </Button>
                </Button.ButtonGroup>
                {this.searchType === SearchType.Profiling ? createProfilingComp() : createUploadComp()}
              </div>
            ),
            main: () => (
              <div class='main-wrap'>
                <div class='empty-wrap'>
                  <EmptyCard
                    title={this.$t('持续 Profiling')}
                    desc={this.$t('直接进行 精准查询，定位到 Trace 详情')}
                  />
                  <EmptyCard
                    title={this.$t('上传 Profiling')}
                    desc={this.$t('可以切换到 范围查询，根据条件筛选 Trace')}
                  />
                </div>
              </div>
            )
          }}
        ></ResizeLayout>
      </div>
    );
  }
});
