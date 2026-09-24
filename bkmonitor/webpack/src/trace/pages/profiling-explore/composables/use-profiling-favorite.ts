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
import { type Ref, computed, shallowRef, watch } from 'vue';

import { Message } from 'bkui-vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import { saveFavorite } from '../services/profiling';
import { restoreQueryState } from '../utils/query';
import { useAppStore } from '@/store/modules/app';

import type { ProfilingFavorite, ProfilingFavoriteConfig, QueryState } from '../types';
import type { IFavoriteGroup } from '@/pages/trace-explore/components/favorite-box/types';

export function useProfilingFavorite({
  state,
  initial,
  apply,
}: {
  apply: (value: unknown) => Promise<void>;
  initial: Ref<null | ProfilingFavorite>;
  state: Ref<QueryState>;
}) {
  const { t } = useI18n();
  const app = useAppStore();
  const route = useRoute();
  const router = useRouter();
  const current = shallowRef<null | ProfilingFavorite>(null);
  const visible = shallowRef(false);
  const editing = shallowRef(false);
  const editData = shallowRef<IFavoriteGroup['favorites'][number] | null>(null);
  const saving = shallowRef(false);
  const selected = computed(() =>
    current.value?.config.profiling.view.tab === state.value.view.tab
      ? state.value.view.tab === 'file'
        ? {
            where: current.value.config.profiling.file?.where || [],
            commonWhere: current.value.config.profiling.file?.commonWhere || [],
          }
        : { where: current.value.config.profiling.where, commonWhere: current.value.config.profiling.commonWhere || [] }
      : null
  );
  watch(initial, value => {
    current.value = value;
  });

  function buildConfig(): ProfilingFavoriteConfig {
    // 收藏保存可恢复的完整页面条件而非 API 参数；快照避免后续编辑改变待保存内容。
    return {
      version: 1,
      bk_biz_id: Number(app.bizId),
      profiling: restoreQueryState(JSON.parse(JSON.stringify(state.value)), state.value.timezone),
    };
  }

  async function save(edit: boolean, onSaved: () => void) {
    if (!edit || current.value?.config.profiling.view.tab !== state.value.view.tab) {
      editData.value = {
        id: 0,
        name: '',
        group_id: null,
        create_user: '',
        update_user: '',
        update_time: '',
        config: buildConfig(),
      };
      editing.value = true;
      return;
    }
    if (saving.value) return;
    saving.value = true;
    try {
      const config = buildConfig();
      await saveFavorite(current.value.id, config);
      current.value = { ...current.value, config };
      onSaved();
      Message({ theme: 'success', message: t('收藏成功') });
    } finally {
      saving.value = false;
    }
  }

  async function select(favorite: ProfilingFavorite | undefined) {
    if (!favorite) {
      current.value = null;
      return;
    }
    if (!favorite.config?.profiling) {
      Message({ theme: 'error', message: t('收藏配置无效') });
      return;
    }
    current.value = favorite;
    await apply(favorite.config.profiling);
  }

  function open(favorite: ProfilingFavorite) {
    const { href } = router.resolve({ path: route.path, query: { favorite_id: favorite.id } });
    window.open(`${location.pathname}?bizId=${app.bizId}${href}`, '_blank', 'noopener,noreferrer');
  }

  return { current, visible, editing, editData, selected, saving, save, select, open };
}
