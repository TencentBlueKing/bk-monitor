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
export const defaultConfig = {
  startOnLoad: false,
  maxTextSize: 20000000,
  fontSize: 12,
  sequence: {
    hideUnusedParticipants: false,
    activationWidth: 10,
    // Margin to the right and left of the sequence diagram
    diagramMarginX: 10,
    // Margin to the over and under the sequence diagram
    diagramMarginY: 10,
    //  Margin between actors
    actorMargin: 16,
    // Width of actor boxes
    width: 40,
    // Height of actor boxes
    height: 50,
    // Margin around loop boxes
    boxMargin: 16,
    // Margin around the text in loop/alt/opt boxes
    boxTextMargin: 10,
    // margin around notes
    noteMargin: 10,
    // Space between messages
    messageMargin: 1,
    // Multiline message alignment
    messageAlign: 'center',
    // Mirror actors under diagram
    mirrorActors: true,
    // forces actor popup menus to always be visible (to support E2E testing).
    forceMenus: false,
    // Prolongs the edge of the diagram downwards
    bottomMarginAdj: 1,
    /**
     * **Notes:** When this flag is set to true, the height and width is set to 100% and is then
     * scaling with the available space. If set to false, the absolute space required is used.
     */
    useMaxWidth: true,
    /**
     * | Parameter   | Description                          | Type    | Required | Values      |
     * | ----------- | ------------------------------------ | ------- | -------- | ----------- |
     * | rightAngles | display curve arrows as right angles | boolean | Required | true, false |
     *
     * **Notes:**
     *
     * This will display arrows that start and begin at the same node as right angles, rather than a
     * curve
     *
     * Default value: false
     */
    rightAngles: false,
    // This will show the node numbers
    showSequenceNumbers: false,
    // This sets the font size of the actor's description
    actorFontSize: 12,
    // This sets the font family of the actor's description
    actorFontFamily: '"Open Sans", sans-serif',
    // This sets the font weight of the actor's description
    actorFontWeight: 400,
    //  This sets the font size of actor-attached notes
    noteFontSize: 12,
    // This sets the font family of actor-attached notes
    noteFontFamily: '"trebuchet ms", verdana, arial, sans-serif',
    // This sets the font weight of the note's description
    noteFontWeight: 400,
    // This sets the text alignment of actor-attached notes
    noteAlign: 'left',
    // This sets the font size of actor messages
    messageFontSize: 12,
    // This sets the font family of actor messages
    messageFontFamily: '"trebuchet ms", verdana, arial, sans-serif',
    // This sets the font weight of the message's description
    messageFontWeight: 400,
    // This sets the auto-wrap state for the diagram
    wrap: false,
    // This sets the auto-wrap padding for the diagram (sides only)
    wrapPadding: 10,
    // This sets the width of the loop-box (loop, alt, opt, par)
    labelBoxWidth: 50,
    // This sets the height of the loop-box (loop, alt, opt, par)
    labelBoxHeight: 20,
  },
  // securityLevel: 'sandbox',
  themeVariables: {
    fontSize: '12px',
    signalColor: '#B4BCD4',
    textColor: '#63656E',
    actorBkg: '##EAEBF0',
    actorBorder: '#EAEBF0',
    actorTextColor: '#63656E',
    actorLineColor: '#DCDEE5',
    activationBkgColor: '#C4C6CC',
    activationBorderColor: '#DCDEE5',
    noteBkgColor: '#fdd',
    noteBorderColor: '#fdd',
  },
};
