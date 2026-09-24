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
import { type PropType, computed, defineComponent, shallowRef } from 'vue';

import { Button, Dropdown, Exception, Input, Radio } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { diffLegend } from '../../utils/flame-layout';
import { createViewState } from '../../utils/query';
import ProfilingSkeleton from '../profiling-skeleton';
import CallGraph from './call-graph';
import FlameCanvas from './flame-canvas';
import ProfileTable from './profile-table';

import type { GraphMode, ProfileResult, ProfileViewState } from '../../types';

import './profile-visualization.scss';

export default defineComponent({
  name: 'ProfileVisualization',
  props: {
    data: { type: Object as PropType<ProfileResult>, required: true },
    mode: { type: String as PropType<GraphMode>, default: 'combined' },
    view: { type: Object as PropType<ProfileViewState>, default: createViewState },
    callGraph: { type: String, default: '' },
    compared: Boolean,
    dataType: { type: String, default: '' },
    loading: Boolean,
    error: { type: String, default: '' },
  },
  emits: {
    viewChange: (_view: Partial<ProfileViewState>) => true,
    modeChange: (_mode: GraphMode) => true,
    export: () => true,
    retry: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const keyword = computed(() => props.view.keyword);
    const highlight = computed(() => props.view.highlight);
    const direction = computed(() => props.view.direction);
    const flame = shallowRef<{ exportPng: () => void }>();
    const modes = computed(() => [
      { id: 'table', icon: 'table', label: t('表格') },
      { id: 'combined', icon: 'mc-fenping', label: t('表格和火焰图') },
      { id: 'flame', icon: 'mc-flame', label: t('火焰图') },
      ...(!props.compared ? [{ id: 'callgraph', icon: 'Component', label: t('功能调用图') }] : []),
    ]);
    const empty = computed(() =>
      props.mode === 'callgraph'
        ? !props.callGraph
        : props.mode === 'table'
          ? !props.data.table_data?.items?.length
          : !props.data.flame_data?.name
    );
    function selectFunction(name: string) {
      // 点选函数同时回填搜索并高亮；再次点同项取消，手动搜索则解除选中态。
      const selected = highlight.value === name ? '' : name;
      emit('viewChange', { highlight: selected, keyword: selected });
    }
    function searchFunction(value: string) {
      emit('viewChange', { keyword: value, highlight: '' });
    }
    return { t, keyword, highlight, direction, flame, modes, empty, diffLegend, selectFunction, searchFunction };
  },
  render() {
    const showFlame = this.mode === 'flame' || this.mode === 'combined';
    const showTable = this.mode === 'table' || this.mode === 'combined';
    return (
      <section class='profile-visualization'>
        <div class='profile-visualization-toolbar'>
          <Radio.Group
            class='profile-view-modes'
            modelValue={this.mode}
            type='capsule'
            onChange={mode => this.$emit('modeChange', mode)}
          >
            {this.modes.map(mode => (
              <Radio.Button
                key={mode.id}
                label={mode.id}
              >
                <i
                  class={`icon-monitor icon-${mode.icon}`}
                  aria-label={mode.label}
                  title={mode.label}
                />
              </Radio.Button>
            ))}
          </Radio.Group>
          <Input
            class='profile-symbol-search'
            disabled={this.mode === 'callgraph'}
            modelValue={this.keyword}
            placeholder={this.t('搜索函数名')}
            type='search'
            clearable
            onClear={() => this.searchFunction('')}
            onInput={value => this.searchFunction(String(value))}
          />
          <Radio.Group
            class='profile-direction-modes'
            disabled={this.mode === 'callgraph'}
            modelValue={this.direction}
            type='capsule'
            onChange={value => {
              this.$emit('viewChange', { direction: value });
            }}
          >
            <Radio.Button label='ltr'>
              <i
                class='icon-monitor icon-AB'
                title={this.t('显示开头')}
              />
            </Radio.Button>
            <Radio.Button label='rtl'>
              <i
                class='icon-monitor icon-YZ'
                title={this.t('显示结尾')}
              />
            </Radio.Button>
          </Radio.Group>
          <Dropdown
            v-slots={{
              content: () => (
                <Dropdown.DropdownMenu>
                  <Dropdown.DropdownItem onClick={() => this.$emit('export')}>pprof</Dropdown.DropdownItem>
                  {showFlame && (
                    <Dropdown.DropdownItem onClick={() => this.flame?.exportPng()}>
                      {this.t('导出当前视图 PNG')}
                    </Dropdown.DropdownItem>
                  )}
                </Dropdown.DropdownMenu>
              ),
            }}
            disabled={this.loading || this.empty || !!this.error}
            placement='bottom-end'
          >
            <Button
              class='profile-download'
              aria-label={this.t('下载')}
              title={this.t('下载')}
            >
              <i class='icon-monitor icon-xiazai1' />
            </Button>
          </Dropdown>
        </div>
        <div
          class='profile-visualization-content'
          aria-busy={this.loading}
        >
          {this.loading ? (
            <>
              {showTable && (
                <div class='profile-table-pane'>
                  <ProfilingSkeleton
                    compared={this.compared}
                    variant='table'
                  />
                </div>
              )}
              {showFlame && (
                <div class='profile-flame-pane'>
                  <ProfilingSkeleton
                    compared={this.compared}
                    variant='flame'
                  />
                </div>
              )}
              {this.mode === 'callgraph' && <ProfilingSkeleton variant='callgraph' />}
            </>
          ) : this.error ? (
            <Exception
              description={this.error}
              scene='part'
              type='500'
            >
              <Button
                theme='primary'
                text
                onClick={() => this.$emit('retry')}
              >
                {this.t('重试')}
              </Button>
            </Exception>
          ) : this.empty ? (
            <Exception
              description={this.t('暂无数据')}
              scene='part'
              type='empty'
            />
          ) : (
            <>
              {showTable && (
                <div class={['profile-table-pane', { combined: this.mode === 'combined' }]}>
                  <ProfileTable
                    compared={this.compared}
                    dataType={this.dataType}
                    direction={this.direction}
                    highlight={this.highlight}
                    keyword={this.keyword}
                    rootTotal={this.data.table_data?.total || this.data.flame_data?.value || 0}
                    rows={this.data.table_data?.items || []}
                    sort={this.view.sort}
                    unit={this.data.unit}
                    onSelect={this.selectFunction}
                    onSortChange={sort => this.$emit('viewChange', { sort })}
                  />
                </div>
              )}
              {showFlame && (
                <div class='profile-flame-pane'>
                  {this.compared && (
                    <div
                      class='profile-diff-legend'
                      aria-label={this.t('差异图例')}
                    >
                      {this.diffLegend.map(item => (
                        <span
                          key={item.label}
                          style={{ backgroundColor: item.color }}
                        >
                          {item.label}
                        </span>
                      ))}
                    </div>
                  )}
                  <FlameCanvas
                    ref='flame'
                    data={this.data.flame_data}
                    dataType={this.dataType}
                    direction={this.direction}
                    focusPath={this.view.flameFocus}
                    highlight={this.highlight}
                    keyword={this.keyword}
                    unit={this.data.unit}
                    onFocusChange={flameFocus => this.$emit('viewChange', { flameFocus })}
                    onSearch={value => {
                      this.$emit('viewChange', { keyword: value, highlight: value });
                    }}
                    onSelect={name => {
                      this.$emit('viewChange', { highlight: name });
                    }}
                  />
                </div>
              )}
              {this.mode === 'callgraph' && (
                <CallGraph
                  svg={this.callGraph}
                  view={this.view.callGraph}
                  onViewChange={callGraph => this.$emit('viewChange', { callGraph })}
                />
              )}
            </>
          )}
        </div>
      </section>
    );
  },
});
