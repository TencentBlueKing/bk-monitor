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
import { Shape } from '@antv/g6';

import CancelFeedbackRoot from '../../../static/img/failure/icon-cancel-feedback.svg';
import FeedbackRoot from '../../../static/img/failure/icon-feedback.svg';
import { NODE_TYPE_SVG } from './node-type-svg';
import { getNodeAttrs, truncateText } from './utils';

// service combo的实现，主要重写g6 原型本身对于label的实现
export default {
  shapeType: 'rect',
  // update数据时，drawLabel不会自动更新，这里自行实现更新
  labelChange(item) {
    const group = item.getContainer();
    const model = item.getModel();
    const { entity, alert_all_recorved } = model;
    const shape = group.find(e => e.get('name') === 'service-combo-tag-border');
    const imageShape = group.find(e => e.get('name') === 'service-combo-tag-img');
    shape?.attr?.({
      fill: entity.is_on_alert ? '#F55555' : '#6C6F78',
    });
    let diffX = 0;
    if (!entity?.is_on_alert && !alert_all_recorved) {
      if (shape.attrs.opacity > 0) {
        shape.attr({
          opacity: 0,
        });
        imageShape.attr({
          opacity: 0,
        });
        diffX = -16;
      }
    } else {
      if (!shape.attrs.opacity) {
        diffX = 16;
        shape.attr({ opacity: 1 });
        imageShape.attr({ opacity: 1 });
      }
    }
    diffX !== 0 &&
      group.find(e => {
        ['service-node-text', 'service-node-rect', 'sub-combo-feedback-text', 'sub-combo-feedback-img'].includes(
          e.get('name')
        ) && e.attr({ x: e.attrs.x + diffX });
      });
  },
  drawLabel(cfg, group) {
    const rectCombo = Shape.Combo.getShape('rect');
    const labelStyle = rectCombo.getLabelStyle!(cfg, {}, group);
    const getLabelStyleByPosition = rectCombo.getLabelStyleByPosition;
    const { entity, alert_all_recorved, is_feedback_root } = cfg;
    // 各shape的间距
    const padding = 4;

    group.addShape('circle', {
      attrs: {
        x: labelStyle.x + padding,
        y: labelStyle.y + padding,
        zIndex: 10,
        opacity: entity?.is_on_alert || alert_all_recorved ? 1 : 0,
        lineWidth: 1, // 描边宽度
        r: 8, // 圆半径
        fill: entity.is_on_alert ? '#F55555' : '#6C6F78',
      },
      name: 'service-combo-tag-border',
    });
    group.addShape('image', {
      zIndex: 12,
      attrs: {
        x: labelStyle.x - 2,
        y: labelStyle.y - 3,
        opacity: entity?.is_on_alert || alert_all_recorved ? 1 : 0,
        width: 12,
        height: 12,
        img: NODE_TYPE_SVG.Alert,
      },
      draggable: false,
      name: 'service-combo-tag-img',
    });
    // 覆盖原型上的数据，手动增加原label的间距
    (this as any).getLabelStyleByPosition = (...args) => {
      const { entity, alert_all_recorved } = args[0];
      const style = getLabelStyleByPosition.apply(rectCombo, args);
      style.x = entity.is_on_alert || alert_all_recorved ? style.x + 12 + padding : style.x - 7 + padding;
      style.y = style.y - 1;
      return style;
    };
    const labelShape = rectCombo.drawLabel.apply(this, [cfg, group]);

    if (entity?.is_root || is_feedback_root) {
      const labelBBox = labelShape.getBBox();
      const nodeAttrs = getNodeAttrs({ entity: cfg as any });
      group.addShape('rect', {
        zIndex: 10,
        attrs: {
          x: labelBBox.x + labelBBox.width + padding,
          y: labelBBox.y - 2,
          width: 24,
          height: 14,
          radius: 7,
          stroke: '#3A3B3D',
          fill: entity.is_root ? '#F55555' : '#FF9C01',
        },
        name: 'service-node-rect',
      });
      group.addShape('text', {
        zIndex: 11,
        attrs: {
          x: labelBBox.x + labelBBox.width + 12 + padding,
          y: labelBBox.y + 5,
          textAlign: 'center',
          textBaseline: 'middle',
          text: truncateText(window.i18n.t('根因'), 28, 11, 'PingFangSC-Medium'),
          fontSize: 9,
          fill: '#fff',
          ...nodeAttrs.textAttrs,
        },
        name: 'service-node-text',
      });
    }
    // "反馈新根因"标识
    if (!entity?.is_root) {
      const labelBBox = labelShape.getBBox();
      const feedbackImg = group.addShape('image', {
        zIndex: 10,
        attrs: {
          x: labelBBox.x + labelBBox.width + padding + (is_feedback_root ? 26 : 0),
          y: labelBBox.y - 1,
          width: 12,
          height: 12,
          cursor: 'pointer',
          img: is_feedback_root ? CancelFeedbackRoot : FeedbackRoot,
          opacity: 0,
        },
        name: 'sub-combo-feedback-img',
      });
      const feedbackText = group.addShape('text', {
        zIndex: 10,
        attrs: {
          x: labelBBox.x + labelBBox.width + 39 + (is_feedback_root ? 30 : 0), // 这里39为文字宽度37 + 2间距
          y: labelBBox.y + 6,
          textAlign: 'center',
          textBaseline: 'middle',
          text: window.i18n.t(is_feedback_root ? '取消反馈根因' : '反馈新根因'),
          fontSize: 9,
          height: 30,
          fill: '#699DF4',
          cursor: 'pointer',
          opacity: 0,
        },
        name: 'sub-combo-feedback-text',
      });
      feedbackImg.set('className', 'sub-combo-label-feedback');
      feedbackText.set('className', 'sub-combo-label-feedback');
    }
    return labelShape;
  },
};
