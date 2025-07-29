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

const COLORS_HEX = [
  // '#17B8BE',
  // '#F8DCA1',
  // '#B7885E',
  // '#FFCB99',
  // '#F89570',
  // '#829AE3',
  // '#E79FD5',
  // '#1E96BE',
  // '#89DAC1',
  // '#B3AD9E',
  // '#12939A',
  // '#DDB27C',
  // '#88572C',
  // '#FF9833',
  // '#EF5D28',
  // '#162A65',
  // '#DA70BF',
  // '#125C77',
  // '#4DC19C',
  // '#776E57'

  '#D2E6B8',
  '#8FDBB5',
  '#7FC7EB',
  '#B7C1F5',
  '#EEB4FA',
  '#FAA796',
  '#FFE294',
  '#B8D1A7',
  '#82C7B0',
  '#76A9DB',
  '#ABABE6',
  '#DB9EDB',
  '#E09D87',
  '#E0D782',
  '#B5E0AB',
  '#66CCCC',
  '#A3C6FF',
  '#CFBEFF',
  '#F5B7E0',
  '#FFCC99',
  '#EBF0A3',
  '#9CCC9C',
  '#61B2C2',
  '#93A6E6',
  '#C0A7E0',
  '#E0A7BA',
  '#EBCB8D',
  '#CBDB95',
];

export class ColorGenerator {
  colorsHex: string[];
  colorsRgb: [number, number, number][];
  cache: Map<string, number>;
  currentIdx: number;

  constructor(colorsHex: string[] = COLORS_HEX) {
    this.colorsHex = colorsHex;
    this.colorsRgb = colorsHex.map(strToRgb);
    this.cache = new Map();
    this.currentIdx = 0;
  }

  // eslint-disable-next-line @typescript-eslint/naming-convention
  _getColorIndex(key: string): number {
    let i = this.cache.get(key);
    // if (i === null) {
    if (i === undefined) {
      i = this.currentIdx;
      this.cache.set(key, this.currentIdx);

      this.currentIdx = ++this.currentIdx % this.colorsHex.length;
    }

    return i;
  }

  /**
   * Will assign a color to an arbitrary key.
   * If the key has been used already, it will
   * use the same color.
   */
  getColorByKey(key: string) {
    const i = this._getColorIndex(key);
    return this.colorsHex[i];
  }

  /**
   * Retrieve the RGB values associated with a key. Adds the key and associates
   * it with a color if the key is not recognized.
   * @return {number[]} An array of three ints [0, 255] representing a color.
   */
  getRgbColorByKey(key: string): [number, number, number] {
    const i = this._getColorIndex(key);
    return this.colorsRgb[i];
  }

  clear() {
    this.cache.clear();
    this.currentIdx = 0;
  }
}

// TS needs the precise return type
function strToRgb(s: string): [number, number, number] {
  if (s.length !== 7) {
    return [0, 0, 0];
  }
  const r = s.slice(1, 3);
  const g = s.slice(3, 5);
  const b = s.slice(5);
  return [Number.parseInt(r, 16), Number.parseInt(g, 16), Number.parseInt(b, 16)];
}

export default new ColorGenerator();
