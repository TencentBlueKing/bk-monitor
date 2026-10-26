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

export type RetrieveUiState = 'idle' | 'loading' | 'success' | 'empty' | 'error';

export interface LogRecord {
  id: string;
  dtEventTimeStamp: number;
  log: string;
  indexSetId?: string | null;
}

export interface SearchRequest {
  keyword: string;
  page?: number;
}

export interface SearchResponse {
  list: LogRecord[];
  total: number;
}

export type SearchFetcher = (
  request: { keyword: string; page: number; signal: AbortSignal },
) => Promise<SearchResponse>;

export interface RetrieveSnapshot {
  uiState: RetrieveUiState;
  keyword: string;
  page: number;
  records: LogRecord[];
  total: number;
  error: string;
  requestId: number;
}

const DEFAULT_SNAPSHOT: RetrieveSnapshot = {
  uiState: 'idle',
  keyword: '',
  page: 1,
  records: [],
  total: 0,
  error: '',
  requestId: 0,
};

export class RetrieveSearchController {
  private snapshot: RetrieveSnapshot = { ...DEFAULT_SNAPSHOT };
  private abortController: AbortController | null = null;
  private readonly fetcher: SearchFetcher;

  constructor(fetcher: SearchFetcher) {
    this.fetcher = fetcher;
  }

  getState(): RetrieveSnapshot {
    return { ...this.snapshot, records: [...this.snapshot.records] };
  }

  async submit(input: SearchRequest): Promise<RetrieveSnapshot> {
    const keyword = String(input.keyword ?? '').trim();
    if (!keyword) {
      this.snapshot = {
        ...this.snapshot,
        uiState: 'error',
        error: 'keyword is required',
      };
      return this.getState();
    }

    const keywordChanged = keyword !== this.snapshot.keyword;
    const page = keywordChanged ? 1 : Math.max(1, Number(input.page) || 1);
    const requestId = this.snapshot.requestId + 1;

    this.abortController?.abort();
    const abortController = new AbortController();
    this.abortController = abortController;

    this.snapshot = {
      ...this.snapshot,
      uiState: 'loading',
      keyword,
      page,
      error: '',
      requestId,
    };

    try {
      const result = await this.fetcher({
        keyword,
        page,
        signal: abortController.signal,
      });
      if (requestId !== this.snapshot.requestId) {
        return this.getState();
      }
      this.snapshot = {
        ...this.snapshot,
        uiState: result.list.length ? 'success' : 'empty',
        records: result.list,
        total: result.total,
        error: '',
      };
    } catch (error) {
      if (abortController.signal.aborted || requestId !== this.snapshot.requestId) {
        return this.getState();
      }
      this.snapshot = {
        ...this.snapshot,
        uiState: 'error',
        error: error instanceof Error ? error.message : String(error),
      };
    }

    return this.getState();
  }

  dispose(): void {
    this.abortController?.abort();
    this.abortController = null;
  }
}

export function createLocalSearchFetcher(dataset: LogRecord[]): SearchFetcher {
  return async ({ keyword, page, signal }) => {
    if (signal.aborted) {
      throw new DOMException('Aborted', 'AbortError');
    }
    const matched = dataset.filter(item => item.log.includes(keyword));
    const pageSize = 10;
    const start = (page - 1) * pageSize;
    return {
      list: matched.slice(start, start + pageSize),
      total: matched.length,
    };
  };
}
