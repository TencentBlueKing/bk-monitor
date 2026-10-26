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

export type CollectorScenario = 'linux' | 'winevent' | 'container_file' | 'container_stdout' | 'bkdata' | 'es' | 'custom_report';
export type CollectStatus = 'running' | 'stopped' | 'failed' | 'pending';
export type WizardStep = 'classify' | 'config' | 'clean' | 'storage';

export interface CollectionItem {
  id: string;
  name: string;
  scenario: CollectorScenario;
  status: CollectStatus;
  path?: string;
  cluster?: string;
}

export interface CollectionSnapshot {
  uiState: 'idle' | 'filtered' | 'wizard' | 'error';
  wizardOpen: boolean;
  filterQuery: string;
  scenario: CollectorScenario | 'all';
  status: CollectStatus | 'all';
  step: WizardStep;
  error: string;
  items: CollectionItem[];
  draft: Partial<CollectionItem> & { name?: string };
}

export interface CollectionDraft {
  name?: string;
  scenario?: CollectorScenario;
  path?: string;
  cluster?: string;
}

const STEPS: WizardStep[] = ['classify', 'config', 'clean', 'storage'];

export const DEFAULT_COLLECTIONS: CollectionItem[] = [
  { id: 'col-1', name: 'nginx-access', scenario: 'linux', status: 'running', path: '/var/log/nginx/access.log', cluster: 'es-default' },
  { id: 'col-2', name: 'nginx-error', scenario: 'linux', status: 'failed', path: '/var/log/nginx/error.log', cluster: 'es-default' },
  { id: 'col-3', name: 'pod-stdout', scenario: 'container_stdout', status: 'stopped', cluster: 'es-default' },
];

export class CollectionController {
  private snapshot: CollectionSnapshot;

  constructor(items: CollectionItem[] = DEFAULT_COLLECTIONS) {
    this.snapshot = {
      uiState: 'idle',
      wizardOpen: false,
      filterQuery: '',
      scenario: 'all',
      status: 'all',
      step: 'classify',
      error: '',
      items: items.map(item => ({ ...item })),
      draft: {},
    };
  }

  getState(): CollectionSnapshot {
    return {
      ...this.snapshot,
      items: this.snapshot.items.map(item => ({ ...item })),
      draft: { ...this.snapshot.draft },
    };
  }

  getVisibleItems(): CollectionItem[] {
    return this.snapshot.items.filter(item => {
      if (this.snapshot.scenario !== 'all' && item.scenario !== this.snapshot.scenario) {
        return false;
      }
      if (this.snapshot.status !== 'all' && item.status !== this.snapshot.status) {
        return false;
      }
      const query = this.snapshot.filterQuery;
      return !query || item.name.includes(query) || item.scenario.includes(query);
    });
  }

  setFilterQuery(value: string): CollectionSnapshot {
    this.snapshot = { ...this.snapshot, filterQuery: String(value ?? '').trim(), uiState: 'filtered', error: '' };
    return this.getState();
  }

  setScenario(scenario: CollectorScenario | 'all'): CollectionSnapshot {
    this.snapshot = { ...this.snapshot, scenario, error: '' };
    return this.getState();
  }

  setStatus(status: CollectStatus | 'all'): CollectionSnapshot {
    this.snapshot = { ...this.snapshot, status, error: '' };
    return this.getState();
  }

  start(id: string): CollectionSnapshot {
    return this.setItemStatus(id, 'running', ['stopped', 'failed', 'pending']);
  }

  stop(id: string): CollectionSnapshot {
    return this.setItemStatus(id, 'stopped', ['running']);
  }

  remove(id: string): CollectionSnapshot {
    this.snapshot = {
      ...this.snapshot,
      error: '',
      items: this.snapshot.items.filter(item => item.id !== id),
    };
    return this.getState();
  }

  openWizard(): CollectionSnapshot {
    this.snapshot = { ...this.snapshot, uiState: 'wizard', wizardOpen: true, step: 'classify', draft: {}, error: '' };
    return this.getState();
  }

  closeWizard(): CollectionSnapshot {
    this.snapshot = { ...this.snapshot, uiState: 'idle', wizardOpen: false, step: 'classify', draft: {}, error: '' };
    return this.getState();
  }

  patchDraft(input: CollectionDraft): CollectionSnapshot {
    this.snapshot = { ...this.snapshot, draft: { ...this.snapshot.draft, ...input }, error: '' };
    return this.getState();
  }

  nextStep(): CollectionSnapshot {
    const error = this.validateStep(this.snapshot.step);
    if (error) {
      this.snapshot = { ...this.snapshot, uiState: 'error', error };
      return this.getState();
    }
    const index = STEPS.indexOf(this.snapshot.step);
    this.snapshot = { ...this.snapshot, step: STEPS[Math.min(STEPS.length - 1, index + 1)], uiState: 'wizard', error: '' };
    return this.getState();
  }

  prevStep(): CollectionSnapshot {
    const index = STEPS.indexOf(this.snapshot.step);
    this.snapshot = { ...this.snapshot, step: STEPS[Math.max(0, index - 1)], uiState: 'wizard', error: '' };
    return this.getState();
  }

  submitWizard(): CollectionSnapshot {
    for (const step of STEPS) {
      const error = this.validateStep(step);
      if (error) {
        this.snapshot = { ...this.snapshot, uiState: 'error', step, error };
        return this.getState();
      }
    }
    const name = String(this.snapshot.draft.name ?? '').trim();
    if (this.snapshot.items.some(item => item.name === name)) {
      this.snapshot = { ...this.snapshot, uiState: 'error', error: 'name already exists' };
      return this.getState();
    }
    this.snapshot = {
      uiState: 'idle',
      wizardOpen: false,
      filterQuery: this.snapshot.filterQuery,
      scenario: this.snapshot.scenario,
      status: this.snapshot.status,
      step: 'classify',
      error: '',
      draft: {},
      items: [
        ...this.snapshot.items,
        {
          id: `col-${Date.now()}`,
          name,
          scenario: this.snapshot.draft.scenario as CollectorScenario,
          status: 'pending',
          path: this.snapshot.draft.path,
          cluster: this.snapshot.draft.cluster,
        },
      ],
    };
    return this.getState();
  }

  private setItemStatus(id: string, status: CollectStatus, allowed: CollectStatus[]): CollectionSnapshot {
    const target = this.snapshot.items.find(item => item.id === id);
    if (!target) {
      this.snapshot = { ...this.snapshot, uiState: 'error', error: 'collection not found' };
      return this.getState();
    }
    if (!allowed.includes(target.status)) {
      this.snapshot = { ...this.snapshot, uiState: 'error', error: `cannot ${status} from ${target.status}` };
      return this.getState();
    }
    this.snapshot = {
      ...this.snapshot,
      uiState: 'idle',
      error: '',
      items: this.snapshot.items.map(item => (item.id === id ? { ...item, status } : item)),
    };
    return this.getState();
  }

  private validateStep(step: WizardStep): string {
    const draft = this.snapshot.draft;
    if (step === 'classify' && !draft.scenario) {
      return 'scenario is required';
    }
    if (step === 'config') {
      if (!String(draft.name ?? '').trim()) {
        return 'name is required';
      }
      if ((draft.scenario === 'linux' || draft.scenario === 'winevent') && !String(draft.path ?? '').trim()) {
        return 'path is required';
      }
    }
    if (step === 'storage' && !String(draft.cluster ?? '').trim()) {
      return 'cluster is required';
    }
    return '';
  }
}
