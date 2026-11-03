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
import { computed, shallowRef, watch } from 'vue';

import type { DiagnosisInteraction } from './types';

interface DiagnosisCardsStateOptions {
  getCardIds: () => string[];
  getControlledExpandedIds: () => string[] | undefined;
  getDefaultExpandedIds?: () => string[];
  getExpandAll: () => boolean | undefined;
  onInteraction: (interaction: DiagnosisInteraction) => void;
  onUpdate: (expandedIds: string[]) => void;
}

export const useDiagnosisCardsState = ({
  getCardIds,
  getControlledExpandedIds,
  getDefaultExpandedIds,
  getExpandAll,
  onUpdate,
  onInteraction,
}: DiagnosisCardsStateOptions) => {
  const localExpandedIds = shallowRef<string[]>([]);
  let initializedDefaults = false;

  watch(
    [getCardIds, getControlledExpandedIds, getExpandAll],
    ([cardIds, controlledExpandedIds, expandAll]) => {
      if (controlledExpandedIds) {
        localExpandedIds.value = controlledExpandedIds.filter(id => cardIds.includes(id));
        return;
      }
      if (expandAll !== undefined) {
        localExpandedIds.value = expandAll ? [...cardIds] : [];
        return;
      }
      if (!initializedDefaults && cardIds.length) {
        localExpandedIds.value = (getDefaultExpandedIds?.() || []).filter(id => cardIds.includes(id));
        initializedDefaults = true;
        return;
      }
      localExpandedIds.value = localExpandedIds.value.filter(id => cardIds.includes(id));
    },
    { immediate: true }
  );

  const resolvedExpandedIds = computed(() => getControlledExpandedIds() || localExpandedIds.value);

  const updateExpandedIds = (expandedIds: string[]) => {
    const nextIds = [...new Set(expandedIds)].filter(id => getCardIds().includes(id));
    if (!getControlledExpandedIds()) localExpandedIds.value = nextIds;
    onUpdate(nextIds);
  };

  const handleToggle = (id: string, expanded: boolean) => {
    const currentIds = resolvedExpandedIds.value;
    updateExpandedIds(expanded ? [...currentIds, id] : currentIds.filter(item => item !== id));
  };

  const handleInteraction = (interaction?: DiagnosisInteraction) => {
    if (interaction) onInteraction(interaction);
  };

  return {
    resolvedExpandedIds,
    isExpanded: (id: string) => resolvedExpandedIds.value.includes(id),
    handleToggle,
    handleInteraction,
    updateExpandedIds,
  };
};
