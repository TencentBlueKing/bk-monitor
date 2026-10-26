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

export type TimePreset = '15m' | '1h' | '24h';
export type ToolbarUiState = 'ready' | 'refreshing';

export interface TimeRange {
  startTime: number;
  endTime: number;
}

export interface SearchIntent {
  resetPage: boolean;
  timeRange: TimeRange;
}

export interface ToolbarSnapshot {
  uiState: ToolbarUiState;
  favoriteShown: boolean;
  timePreset: TimePreset;
  autoRefresh: boolean;
  timeRange: TimeRange;
}

const PRESET_MS: Record<TimePreset, number> = {
  '15m': 15 * 60 * 1000,
  '1h': 60 * 60 * 1000,
  '24h': 24 * 60 * 60 * 1000,
};

export function resolveTimeRange(preset: TimePreset, now = Date.now()): TimeRange {
  return {
    startTime: now - PRESET_MS[preset],
    endTime: now,
  };
}

export class ToolbarController {
  private snapshot: ToolbarSnapshot;
  private timer: ReturnType<typeof setInterval> | null = null;
  private readonly onTick: ((intent: SearchIntent) => void) | null;

  constructor(onTick: ((intent: SearchIntent) => void) | null = null, now = Date.now()) {
    this.onTick = onTick;
    this.snapshot = {
      uiState: 'ready',
      favoriteShown: true,
      timePreset: '15m',
      autoRefresh: false,
      timeRange: resolveTimeRange('15m', now),
    };
  }

  getState(): ToolbarSnapshot {
    return { ...this.snapshot, timeRange: { ...this.snapshot.timeRange } };
  }

  toggleFavoriteShown(): ToolbarSnapshot {
    this.snapshot = {
      ...this.snapshot,
      favoriteShown: !this.snapshot.favoriteShown,
    };
    return this.getState();
  }

  setTimePreset(preset: TimePreset, now = Date.now()): { state: ToolbarSnapshot; intent: SearchIntent } {
    const timeRange = resolveTimeRange(preset, now);
    this.snapshot = {
      ...this.snapshot,
      timePreset: preset,
      timeRange,
    };
    return {
      state: this.getState(),
      intent: { resetPage: true, timeRange },
    };
  }

  setAutoRefresh(enabled: boolean, intervalMs = 5000): ToolbarSnapshot {
    this.clearTimer();
    this.snapshot = {
      ...this.snapshot,
      autoRefresh: enabled,
      uiState: enabled ? 'refreshing' : 'ready',
    };
    if (enabled) {
      this.timer = setInterval(() => {
        this.onTick?.({
          resetPage: false,
          timeRange: { ...this.snapshot.timeRange },
        });
      }, intervalMs);
    }
    return this.getState();
  }

  createRefreshIntent(): SearchIntent {
    return {
      resetPage: false,
      timeRange: { ...this.snapshot.timeRange },
    };
  }

  dispose(): void {
    this.clearTimer();
  }

  private clearTimer(): void {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }
}
