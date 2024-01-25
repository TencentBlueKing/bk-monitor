/* eslint-disable no-plusplus */
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
export class UseTopoChart {
  containerHtml = null;
  imageHtml = null;

  scale = 1; // 当前大小缩放比例
  isDragging = false; // 当前是否拖动状态
  dragStartX = 0; // 拖动 x 坐标
  dragStartY = 0; // 拖动 y 坐标
  imgX = 0; // 图片 x 坐标
  imgY = 0; // 图片 y 坐标
  zoomSpeed = 0.1; // 缩放步长

  constructor(container: HTMLDivElement, image: HTMLDivElement) {
    this.containerHtml = container;
    this.imageHtml = image;
    this.updateImageTransform();
    this.initEvents();
  }

  initEvents() {
    this.imageHtml?.addEventListener('mousedown', (event: MouseEvent) => {
      event.preventDefault();
      this.isDragging = true;
      this.dragStartX = event.clientX - this.imgX;
      this.dragStartY = event.clientY - this.imgY;
    });

    /** 拖动图片 */
    this.containerHtml?.addEventListener('mousemove', (event: MouseEvent) => {
      if (this.isDragging) {
        this.imgX = event.clientX - this.dragStartX;
        this.imgY = event.clientY - this.dragStartY;
        this.updateImageTransform();
      }
    });

    this.containerHtml?.addEventListener('mouseup', () => {
      this.isDragging = false;
    });

    /** 缩放图片 */
    this.containerHtml?.addEventListener('wheel', (event: WheelEvent) => {
      event.preventDefault();
      this.scale += event.deltaY * -this.zoomSpeed;
      this.scale = Math.max(this.scale, 1); // 设置最小缩放限制
      this.scale = Math.min(this.scale, 50); // 设置最大缩放限制
      this.updateImageTransform();
    });
  }

  /** 更新图片大小和坐标 */
  updateImageTransform() {
    const { imgX, imgY, scale } = this;
    this.imageHtml.style.transform = `translate(${imgX}px, ${imgY}px) scale(${scale})`;
  }
}
