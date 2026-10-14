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
import { type PropType, defineComponent, shallowRef } from 'vue';

import { PrimaryTable } from '@blueking/tdesign-ui';
import { Alert, Button, Input, Pagination, Radio, Switcher } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { formatCollectionTime, processKey, processLabels } from '../../utils/collection';

import type { CollectionForm } from '../../composables/use-collection-form';
import type { ProcessMode, ProcessRow } from '../../types/collection';

export default defineComponent({
  name: 'CollectionProcessSelector',
  props: {
    form: { type: Object as PropType<CollectionForm>, required: true },
    modes: { type: Array as PropType<ProcessMode[]>, required: true },
  },
  setup() {
    const { t } = useI18n();
    const collapsed = shallowRef(false);
    return { t, collapsed };
  },
  render() {
    const f = this.form;
    const d = f.draft.value;
    const p = d.process;
    const selected = f.selected.value;
    const columns = [
      {
        colKey: 'row-select',
        type: 'multiple' as const,
        width: 40,
        checkProps: ({ row }) => ({ disabled: f.dynamic.value || !!row.err_msg || !row.pid }),
      },
      { colKey: 'ip', title: this.t('主机 IP'), width: 120, cell: (_, { row }) => row.ip || `#${row.bk_host_id}` },
      { colKey: 'pid', title: 'PID', width: 70, cell: (_, { row }) => row.pid || '--' },
      {
        colKey: 'process_name',
        title: this.t('进程名'),
        minWidth: 100,
        ellipsis: true,
        cell: (_, { row }) => row.process_name || '--',
      },
      {
        colKey: 'command',
        title: this.t('命令行'),
        minWidth: 160,
        ellipsis: true,
        cell: (_, { row }) =>
          row.err_msg ? <span class='collection-error-text'>{row.err_msg}</span> : row.command || '--',
      },
      {
        colKey: 'started_at',
        title: this.t('启动时间'),
        width: 165,
        cell: (_, { row }) => formatCollectionTime(row.started_at, d.timezone),
      },
    ];
    const hostLabel = (row: ProcessRow) =>
      row.ip || d.hosts.find(host => host.host_id === row.bk_host_id)?.ip || `#${row.bk_host_id}`;
    return (
      <div class='collection-process-selector'>
        <div class='collection-process-query'>
          <div class='collection-process-conditions'>
            <div class='collection-process-inputs'>
              <Radio.Group
                modelValue={d.processMode}
                type='capsule'
                onChange={processMode => f.patch({ processMode })}
              >
                {this.modes.map(mode => (
                  <Radio.Button
                    key={mode}
                    label={mode}
                  >
                    {this.t(processLabels[mode])}
                  </Radio.Button>
                ))}
              </Radio.Group>
              {d.processMode === 'command' ? (
                <>
                  <Input
                    modelValue={p.matchPattern}
                    placeholder={this.t('直接字符串匹配，不支持正则，举例：/data/home/user00/word')}
                    onInput={matchPattern => f.patchProcess({ matchPattern })}
                  >
                    {{ prefix: () => <span class='collection-input-prefix'>{this.t('包含')}</span> }}
                  </Input>
                  <Input
                    modelValue={p.excludePattern}
                    placeholder={this.t('排除匹配到的进程，支持正则，举例：/data/home/user00/word[d].+')}
                    onInput={excludePattern => f.patchProcess({ excludePattern })}
                  >
                    {{ prefix: () => <span class='collection-input-prefix'>{this.t('排除')}</span> }}
                  </Input>
                </>
              ) : d.processMode === 'pid_file' ? (
                <Input
                  modelValue={p.pidPath}
                  placeholder={this.t('请输入 PID 文件的绝对路径')}
                  onInput={pidPath => f.patchProcess({ pidPath })}
                />
              ) : (
                <Input
                  modelValue={p.pids}
                  placeholder={this.t('请输入 PID，多个 PID 用逗号分隔')}
                  onInput={pids => f.patchProcess({ pids })}
                />
              )}
            </div>
            <Button
              loading={f.previewLoading.value}
              theme='primary'
              onClick={f.queryProcesses}
            >
              {this.t('查询')}
            </Button>
          </div>
          {d.processMode === 'command' && (
            <div class='collection-dynamic-toggle'>
              <Switcher
                modelValue={p.dynamic}
                size='small'
                onChange={dynamic => f.patchProcess({ dynamic })}
              />
              <span v-tippy={this.t('开启后保存匹配条件，在每次执行时重新匹配进程，无需选择具体进程')}>
                {this.t('动态下发')}
              </span>
            </div>
          )}
          {f.previewError.value && (
            <Alert
              class='collection-inline-alert'
              theme='danger'
              title={f.previewError.value}
            />
          )}
          <div v-tippy={{ content: this.t('已选择动态下发，无需具体选择进程'), onShow: () => f.dynamic.value }}>
            <PrimaryTable
              data={f.preview.value.data
                .slice((f.previewPage.value - 1) * 10, f.previewPage.value * 10)
                .map(row => ({ ...row, key: processKey(row) }))}
              columns={columns}
              empty={this.t(f.preview.value.columns.length ? '暂无匹配进程' : '输入条件并查询进程')}
              loading={f.previewLoading.value}
              rowKey='key'
              selectedRowKeys={f.dynamic.value ? [] : selected.map(processKey)}
              size='small'
              onSelectChange={keys => {
                if (!f.dynamic.value) f.selectPreview(keys);
              }}
            />
          </div>
          <Pagination
            class='collection-process-pagination'
            count={f.preview.value.data.length}
            limit={10}
            modelValue={f.previewPage.value}
            showLimit={false}
            small
            onChange={page => {
              f.previewPage.value = page;
            }}
          />
        </div>
        <aside class='collection-process-targets'>
          <h4>{this.t('目标进程')}</h4>
          {f.dynamic.value ? (
            <>
              <p>{this.t('已配置动态下发')}</p>
              <div class='collection-process-card'>
                <div>
                  {this.t('包含')}：{p.matchPattern || '--'}
                </div>
                {p.excludePattern && (
                  <div>
                    {this.t('排除')}：{p.excludePattern}
                  </div>
                )}
                <small>{this.t('命令行匹配')}</small>
              </div>
            </>
          ) : (
            <>
              <div class='collection-process-target-heading'>
                <Button
                  text
                  onClick={() => {
                    this.collapsed = !this.collapsed;
                  }}
                >
                  {this.collapsed ? '▸' : '▾'} {this.t('已选择 {n} 个进程', { n: selected.length })}
                </Button>
                <Button
                  disabled={!selected.length}
                  theme='primary'
                  text
                  onClick={() => f.selectProcesses([])}
                >
                  {this.t('清空')}
                </Button>
              </div>
              {!this.collapsed &&
                selected.map(row => (
                  <div
                    key={processKey(row)}
                    class='collection-process-card'
                  >
                    <div>PID：{row.pid}</div>
                    <small title={`${hostLabel(row)} / ${row.process_name || '--'}`}>
                      {hostLabel(row)} / {row.process_name || '--'}
                    </small>
                    <Button
                      class='collection-process-remove'
                      aria-label={this.t('删除')}
                      text
                      onClick={() => f.selectProcesses(selected.filter(item => processKey(item) !== processKey(row)))}
                    >
                      ×
                    </Button>
                  </div>
                ))}
              {!selected.length && (
                <p class='collection-muted'>
                  {this.t(
                    d.processMode === 'pid_file' ? '按 PID 文件路径采集，无需选择具体进程' : '请从左侧选择目标进程'
                  )}
                </p>
              )}
            </>
          )}
        </aside>
      </div>
    );
  },
});
