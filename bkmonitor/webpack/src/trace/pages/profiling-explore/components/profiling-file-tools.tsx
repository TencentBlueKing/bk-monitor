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
import { type PropType, computed, defineComponent, onMounted, onScopeDispose, shallowRef } from 'vue';

import { Button, Select } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { fileStatusLabels } from '../utils/file';
import ProfilingFileDetail from './profiling-file-detail';
import ProfilingFileUpload from './profiling-file-upload';

import type { ProfileFile } from '../types/file';

export default defineComponent({
  name: 'ProfilingExploreFileTools',
  props: {
    records: { type: Array as PropType<ProfileFile[]>, default: () => [] },
    profileId: { type: String, default: '' },
    fileName: { type: String, default: '' },
    loading: Boolean,
  },
  emits: {
    select: (_file: ProfileFile) => true,
    refresh: () => true,
    uploaded: (_file: ProfileFile) => true,
  },
  setup(props) {
    const { t } = useI18n();
    const uploadShow = shallowRef(false);
    const detailId = shallowRef('');
    const selector = shallowRef<{ hidePopover: () => void; showPopover: () => void }>();
    const selected = computed(() => props.records.find(item => item.profile_id === props.profileId));
    const detail = computed(() => props.records.find(item => item.profile_id === detailId.value));
    function shortcut(event: KeyboardEvent) {
      if (uploadShow.value || detailId.value || !(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== 'o')
        return;
      event.preventDefault();
      selector.value?.showPopover();
    }
    function openUpload() {
      uploadShow.value = true;
    }
    onMounted(() => window.addEventListener('keydown', shortcut));
    onScopeDispose(() => window.removeEventListener('keydown', shortcut));
    return { t, uploadShow, detailId, selector, selected, detail, fileStatusLabels, openUpload };
  },
  render() {
    return (
      <div class='profiling-file-tools'>
        <Button
          theme='primary'
          onClick={this.openUpload}
        >
          <i class='icon-monitor icon-upload-cloud' /> {this.t('上传文件')}
        </Button>
        <Select
          ref='selector'
          class='profiling-file-select'
          clearable={false}
          inputSearch={false}
          loading={this.loading && !this.records.length}
          modelValue={this.profileId}
          popoverMinWidth={540}
          popoverOptions={{ extCls: 'profiling-file-popover' }}
          filterable
          onSelect={id => {
            const file = this.records.find(item => item.profile_id === id);
            if (file?.status === 'store_succeed') this.$emit('select', file);
          }}
          onToggle={show => {
            if (show) this.$emit('refresh');
          }}
        >
          {{
            trigger: () => (
              <button
                class='profiling-file-trigger'
                aria-label={this.t('选择文件')}
                type='button'
              >
                <span>{this.t('文件')}:</span>
                {this.selected && (
                  <i
                    class={`profiling-file-status ${this.selected.status}`}
                    title={this.t(this.fileStatusLabels[this.selected.status])}
                  />
                )}
                <span
                  class='profiling-file-name'
                  v-overflow-tips
                >
                  {this.selected?.file_name || this.fileName || this.t('请选择文件')}
                </span>
                <kbd>cmd+o</kbd>
                <i class='icon-monitor icon-mc-triangle-down' />
              </button>
            ),
            default: () =>
              this.records.map(file => (
                <Select.Option
                  id={file.profile_id}
                  key={file.profile_id}
                  disabled={file.status !== 'store_succeed'}
                  name={`${file.file_name} ${file.origin_file_name}`}
                >
                  <div class='profiling-file-option'>
                    <i class={`profiling-file-status ${file.status}`} />
                    <span class='profiling-file-status-text'>
                      {this.t(this.fileStatusLabels[file.status] || file.status)}
                    </span>
                    <span
                      class='profiling-file-option-name'
                      v-overflow-tips
                    >
                      {file.file_name} <span>({file.origin_file_name})</span>
                    </span>
                    <Button
                      aria-label={`${this.t('文件详情')}: ${file.file_name}`}
                      theme='primary'
                      text
                      onClick={event => {
                        event.stopPropagation();
                        this.selector?.hidePopover();
                        this.detailId = file.profile_id;
                      }}
                    >
                      <i class='icon-monitor icon-mc-detail' />
                    </Button>
                  </div>
                </Select.Option>
              )),
          }}
        </Select>
        <ProfilingFileUpload
          show={this.uploadShow}
          onClose={() => {
            this.uploadShow = false;
          }}
          onUploaded={file => this.$emit('uploaded', file)}
        />
        <ProfilingFileDetail
          file={this.detail}
          onClose={() => {
            this.detailId = '';
          }}
        />
      </div>
    );
  },
});
