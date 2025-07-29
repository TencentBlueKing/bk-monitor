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
import './icon-font.scss';

interface IIconFontProps {
  activeStyle?: boolean /** 选中样式 */;
  classes?: string[] /** 组件类名 */;
  fontSize?: number /** icon字体大小 */;
  height?: number /** 高度 */;
  hoverStyle?: boolean /** hover时的样式 */;
  icon: string /** icon-font */;
  width?: number /** 宽度 */;
  onClick?: () => void /** 点击方法 */;
}
const IconFont = (props: IIconFontProps) => {
  /** 设置默认值 */
  const localWidth = props.width || 16;
  const localHeight = props.height || 16;
  const localFontSize = props.fontSize || 14;
  const localClasses = props?.classes || [];
  return (
    <i
      style={`--height: ${localHeight}px; --width: ${localWidth}px; --font-size: ${localFontSize}px;`}
      class={[
        'trace-icon-font',
        'icon-monitor',
        props.icon,
        {
          'icon-hover-style': props.hoverStyle ?? false,
          'icon-active-style': props.activeStyle ?? false,
        },
        ...localClasses,
      ]}
    />
  );
};
export default IconFont;
