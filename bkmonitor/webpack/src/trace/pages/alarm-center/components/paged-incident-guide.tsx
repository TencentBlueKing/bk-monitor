/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { type PropType, defineComponent, onBeforeUnmount, onMounted, reactive, shallowRef } from 'vue';

import { Button, Loading, Select } from 'bkui-vue';
import { FormSpacePages } from 'monitor-common/utils/space-selection';
import { useI18n } from 'vue-i18n';

import DataAccess from '../../../components/data-access';

import type { ISpaceItem } from 'monitor-common/typings';

/** Mounted only while the virtual incident scope's onboarding drawer is open. */
export default defineComponent({
  name: 'PagedIncidentGuide',
  props: {
    authorizedSpaceCount: Number,
    enabledBizIds: { type: Array as PropType<number[]>, required: true },
    wxCsLink: String,
  },
  emits: ['enabled'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const pages = reactive(new FormSpacePages());
    const selected = shallowRef<ISpaceItem>();
    const chooseFirst = () => {
      if (!selected.value) selected.value = pages.items[0];
    };
    const search = async (query = '') => {
      if (await pages.search(query)) chooseFirst();
    };
    const more = async () => {
      if (await pages.retryOrNext()) chooseFirst();
    };
    const renderMore = () =>
      (pages.failed || pages.hasMore) && (
        <Button
          loading={pages.loading}
          text
          onClick={more}
        >
          {t(pages.failed ? '重试' : '加载更多')}
        </Button>
      );
    onMounted(() => search());
    onBeforeUnmount(() => pages.reset());

    const renderPicker = () => (
      <div class='legend-select-wrapper'>
        <Select
          class='legend-select'
          v-slots={{ extension: renderMore }}
          behavior='simplicity'
          clearable={false}
          modelValue={selected.value.bk_biz_id}
          remoteMethod={search}
          filterable
          onUpdate:modelValue={id => {
            const space = pages.items.find(item => item.bk_biz_id === Number(id));
            if (space) selected.value = space;
          }}
        >
          {pages.items.map(space => (
            <Select.Option
              id={space.bk_biz_id}
              key={space.bk_biz_id}
              name={`${space.space_name} (#${space.space_id})`}
            />
          ))}
        </Select>
        <div class='legend-select-desc'>
          <i class='icon-monitor icon-hint' />
          {t('可以切换查看不同空间的接入数据情况')}
        </div>
      </div>
    );
    return () =>
      selected.value ? (
        <DataAccess
          key={selected.value.bk_biz_id}
          v-slots={{ spacePicker: renderPicker }}
          enabledBizIds={props.enabledBizIds}
          mode={props.enabledBizIds.length || props.authorizedSpaceCount === undefined ? 'guide' : 'empty'}
          spaceList={[selected.value]}
          totalCount={props.authorizedSpaceCount}
          wxCsLink={props.wxCsLink}
          onEnabled={() => emit('enabled')}
        />
      ) : (
        <Loading loading={pages.loading}>
          {pages.failed || pages.hasMore ? renderMore() : !pages.loading && t('暂无数据')}
        </Loading>
      );
  },
});
