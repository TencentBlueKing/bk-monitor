/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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

import _get from 'lodash/get';

import EUpdateTypes from './e-update-types';

import type { TNil } from '../../typings';
import type { DraggableBounds, DraggingUpdate } from './types';

const LEFT_MOUSE_BUTTON = 0;

type DraggableManagerOptions = {
  getBounds: (tag: string | TNil) => DraggableBounds;
  onDragEnd?: (update: DraggingUpdate) => void;
  onDragMove?: (update: DraggingUpdate) => void;
  onDragStart?: (update: DraggingUpdate) => void;
  onMouseEnter?: (update: DraggingUpdate) => void;
  onMouseLeave?: (update: DraggingUpdate) => void;
  onMouseMove?: (update: DraggingUpdate) => void;
  resetBoundsOnResize?: boolean;
  tag?: string;
};

export default class DraggableManager {
  // cache the last known DraggableBounds (invalidate via `#resetBounds())
  _bounds: DraggableBounds | TNil;
  _isDragging: boolean;
  // optional callbacks for various dragging events
  _onMouseEnter: ((update: DraggingUpdate) => void) | TNil;
  _onMouseLeave: ((update: DraggingUpdate) => void) | TNil;
  _onMouseMove: ((update: DraggingUpdate) => void) | TNil;
  _onDragStart: ((update: DraggingUpdate) => void) | TNil;
  _onDragMove: ((update: DraggingUpdate) => void) | TNil;
  _onDragEnd: ((update: DraggingUpdate) => void) | TNil;
  // whether to reset the bounds on window resize
  _resetBoundsOnResize: boolean;

  /**
   * Get the `DraggableBounds` for the current drag. The returned value is
   * cached until either `#resetBounds()` is called or the window is resized
   * (assuming `_resetBoundsOnResize` is `true`). The `DraggableBounds` defines
   * the range the current drag can span to. It also establishes the left offset
   * to adjust `clientX` by (from the `MouseEvent`s).
   */
  getBounds: (tag: string | TNil) => DraggableBounds;

  // convenience data
  tag: string | TNil;

  // handlers for integration with DOM elements
  handleMouseEnter: (event: MouseEvent) => void;
  handleMouseMove: (event: MouseEvent) => void;
  handleMouseLeave: (event: MouseEvent) => void;
  handleMouseDown: (event: MouseEvent) => void;

  constructor({ getBounds, tag, resetBoundsOnResize = true, ...rest }: DraggableManagerOptions) {
    this.handleMouseDown = this._handleDragEvent;
    this.handleMouseEnter = this._handleMinorMouseEvent;
    this.handleMouseMove = this._handleMinorMouseEvent;
    this.handleMouseLeave = this._handleMinorMouseEvent;

    this.getBounds = getBounds;
    this.tag = tag;
    this._isDragging = false;
    this._bounds = undefined;
    this._resetBoundsOnResize = Boolean(resetBoundsOnResize);
    if (this._resetBoundsOnResize) {
      window.addEventListener('resize', this.resetBounds);
    }
    this._onMouseEnter = rest.onMouseEnter;
    this._onMouseLeave = rest.onMouseLeave;
    this._onMouseMove = rest.onMouseMove;
    this._onDragStart = rest.onDragStart;
    this._onDragMove = rest.onDragMove;
    this._onDragEnd = rest.onDragEnd;
  }

  _getBounds(): DraggableBounds {
    if (!this._bounds) {
      this._bounds = this.getBounds(this.tag);
    }
    return this._bounds;
  }

  _getPosition(clientX: number) {
    const { clientXLeft, maxValue, minValue, width } = this._getBounds();
    let x = clientX - clientXLeft;
    let value = x / width;
    if (minValue != null && value < minValue) {
      value = minValue;
      x = minValue * width;
    } else if (maxValue != null && value > maxValue) {
      value = maxValue;
      x = maxValue * width;
    }
    return { value, x };
  }

  _stopDragging() {
    window.removeEventListener('mousemove', this._handleDragEvent);
    window.removeEventListener('mouseup', this._handleDragEvent);
    const style = _get(document, 'body.style');
    if (style) {
      style.userSelect = null;
    }
    this._isDragging = false;
  }

  isDragging() {
    return this._isDragging;
  }

  dispose() {
    if (this._isDragging) {
      this._stopDragging();
    }
    if (this._resetBoundsOnResize) {
      window.removeEventListener('resize', this.resetBounds);
    }
    this._bounds = undefined;
    this._onMouseEnter = undefined;
    this._onMouseLeave = undefined;
    this._onMouseMove = undefined;
    this._onDragStart = undefined;
    this._onDragMove = undefined;
    this._onDragEnd = undefined;
  }

  resetBounds = () => {
    this._bounds = undefined;
  };

  _handleMinorMouseEvent = (event: MouseEvent) => {
    const { button, clientX, type: eventType } = event;
    if (this._isDragging || button !== LEFT_MOUSE_BUTTON) {
      return;
    }
    let type: EUpdateTypes | null = null;
    let handler: ((update: DraggingUpdate) => void) | TNil;
    if (eventType === 'mouseenter') {
      type = EUpdateTypes.MouseEnter;
      handler = this._onMouseEnter;
    } else if (eventType === 'mouseleave') {
      type = EUpdateTypes.MouseLeave;
      handler = this._onMouseLeave;
    } else if (eventType === 'mousemove') {
      type = EUpdateTypes.MouseMove;
      handler = this._onMouseMove;
    } else {
      throw new Error(`invalid event type: ${eventType}`);
    }
    if (!handler) {
      return;
    }
    const { value, x } = this._getPosition(clientX);
    handler({
      event,
      type,
      value,
      x,
      manager: this,
      tag: this.tag,
    });
  };

  _handleDragEvent = (event: MouseEvent) => {
    const { button, clientX, type: eventType } = event;
    let type: EUpdateTypes | null = null;
    let handler: ((update: DraggingUpdate) => void) | TNil;
    if (eventType === 'mousedown') {
      if (this._isDragging || button !== LEFT_MOUSE_BUTTON) {
        return;
      }
      window.addEventListener('mousemove', this._handleDragEvent);
      window.addEventListener('mouseup', this._handleDragEvent);
      const style = _get(document, 'body.style');
      if (style) {
        style.userSelect = 'none';
      }
      this._isDragging = true;

      type = EUpdateTypes.DragStart;
      handler = this._onDragStart;
    } else if (eventType === 'mousemove') {
      if (!this._isDragging) {
        return;
      }
      type = EUpdateTypes.DragMove;
      handler = this._onDragMove;
    } else if (eventType === 'mouseup') {
      if (!this._isDragging) {
        return;
      }
      this._stopDragging();
      type = EUpdateTypes.DragEnd;
      handler = this._onDragEnd;
    } else {
      throw new Error(`invalid event type: ${eventType}`);
    }
    if (!handler) {
      return;
    }
    const { value, x } = this._getPosition(clientX);
    handler({
      event,
      type,
      value,
      x,
      manager: this,
      tag: this.tag,
    });
  };
}
