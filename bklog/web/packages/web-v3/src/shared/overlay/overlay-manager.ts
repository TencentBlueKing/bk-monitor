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

export type OverlayKind = 'dialog' | 'drawer' | 'popup' | 'tooltip' | 'message';

export interface OverlayOpenInput {
  id: string;
  kind: OverlayKind;
  group?: string;
  dismissible?: boolean;
}

export interface OverlayRecord extends OverlayOpenInput {
  zIndex: number;
  dismissible: boolean;
}

const BASE_Z_INDEX = 2500;

export class OverlayManager {
  private stack: OverlayRecord[] = [];
  private nextZIndex = BASE_Z_INDEX;

  open(input: OverlayOpenInput): OverlayRecord {
    if (input.group) {
      this.stack = this.stack.filter(item => item.group !== input.group);
    }
    this.stack = this.stack.filter(item => item.id !== input.id);
    const record: OverlayRecord = {
      ...input,
      dismissible: input.dismissible !== false,
      zIndex: this.nextZIndex,
    };
    this.nextZIndex += 10;
    this.stack.push(record);
    return { ...record };
  }

  close(id: string): OverlayRecord | null {
    const index = this.stack.findIndex(item => item.id === id);
    if (index < 0) {
      return null;
    }
    const [removed] = this.stack.splice(index, 1);
    return removed ?? null;
  }

  closeTop(): OverlayRecord | null {
    for (let index = this.stack.length - 1; index >= 0; index -= 1) {
      if (this.stack[index].dismissible) {
        return this.stack.splice(index, 1)[0];
      }
    }
    return null;
  }

  handleEscape(): OverlayRecord | null {
    return this.closeTop();
  }

  getTop(): OverlayRecord | null {
    return this.stack.length ? { ...this.stack[this.stack.length - 1] } : null;
  }

  getStack(): OverlayRecord[] {
    return this.stack.map(item => ({ ...item }));
  }

  clear(): void {
    this.stack = [];
    this.nextZIndex = BASE_Z_INDEX;
  }
}

export const overlayManager = new OverlayManager();
