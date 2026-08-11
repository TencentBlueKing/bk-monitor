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

/**
 * Shadow DOM 感知的选区读写。
 *
 * 监控 Trace 宿主把日志组件挂载在 `<trace-explore>` 的 shadow root 内（bk-weweb `setShadowDom`），
 * 浏览器会把 document 选区 retarget 到 shadow host 所在的那棵树：Range 的 startContainer /
 * endContainer 变成 host 的父节点（`div.trace-wrap-iframe`），offset 变成 host 的下标。
 * 结果是 `toString()` 取不到文本、`getClientRects()` 取不到真实矩形，划词菜单的
 * 复制 / 高亮 / 添加到本次检索全部拿到空串而失效。
 *
 * 因此选区一律通过本模块读取，按「选区可能所在的 shadow root」取未被 retarget 的结果：
 * 1. `Selection.getComposedRanges({ shadowRoots })`：标准 API（Chrome 137+ / Firefox 142+ / Safari 17+）；
 * 2. `ShadowRoot.getSelection()`：Chromium 私有 API，兜住 Chrome 137 之前的版本；
 * 3. 两者都拿不到时退回 document 选区，保持非 shadow 宿主下的原有行为。
 */

type StaticRangeLike = {
  startContainer?: Node;
  startOffset?: number;
  endContainer?: Node;
  endOffset?: number;
};

/** 判断是否为 ShadowRoot 类型 */
const isShadowRoot = (root: unknown): root is ShadowRoot => {
  return typeof ShadowRoot !== 'undefined' && root instanceof ShadowRoot;
};

/** 由内向外收集 node 所在的 shadow root 链；node 在普通文档树内时返回空数组。 */
export const getShadowRootChain = (contextNode?: Node | null): ShadowRoot[] => {
  const shadowRoots: ShadowRoot[] = [];
  let current: Node | null = contextNode ?? null;

  while (current) {
    const root = current.getRootNode?.();
    if (!isShadowRoot(root)) {
      break;
    }

    shadowRoots.push(root);
    current = root.host;
  }

  return shadowRoots;
};

/** 判断 Range 是否在 ShadowRoot 内 */
const isRangeInShadowRoots = (range: Range | null, shadowRoots: ShadowRoot[]) => {
  if (!range) {
    return false;
  }

  return (
    shadowRoots.includes(range.startContainer?.getRootNode?.() as ShadowRoot)
    || shadowRoots.includes(range.endContainer?.getRootNode?.() as ShadowRoot)
  );
};

/** 创建 Range 对象 */
const createRange = (staticRange?: StaticRangeLike) => {
  const { startContainer, startOffset, endContainer, endOffset } = staticRange ?? {};
  if (!startContainer || !endContainer) {
    return null;
  }

  try {
    const range = (startContainer.ownerDocument ?? document).createRange();
    range.setStart(startContainer, startOffset ?? 0);
    range.setEnd(endContainer, endOffset ?? 0);
    return range;
  } catch {
    // 两个端点不在同一棵树（跨 shadow 边界选取）时无法构造 Range
    return null;
  }
};

/** 获取合成 Range */
const getComposedRange = (selection: Selection, shadowRoots: ShadowRoot[]) => {
  const getComposedRanges = (selection as any).getComposedRanges;
  if (typeof getComposedRanges !== 'function') {
    return null;
  }

  // 标准签名是 getComposedRanges({ shadowRoots })，早期实现（如 Safari 17）用的是 rest 参数
  for (const args of [[{ shadowRoots }], shadowRoots]) {
    let range: Range | null = null;

    try {
      range = createRange(getComposedRanges.apply(selection, args)?.[0]);
    } catch {
      continue;
    }

    // shadowRoots 没被目标实现识别时拿到的仍是 retarget 后的结果，需要丢弃后换另一种签名
    if (isRangeInShadowRoots(range, shadowRoots)) {
      return range;
    }
  }

  return null;
};

/** 获取 ShadowRoot 内的 Range */
const getShadowRootRange = (shadowRoots: ShadowRoot[]) => {
  for (const shadowRoot of shadowRoots) {
    const selection = (shadowRoot as any).getSelection?.() as Selection | undefined;
    const range = selection?.rangeCount ? selection.getRangeAt(0) : null;

    if (isRangeInShadowRoots(range, shadowRoots)) {
      return range;
    }
  }

  return null;
};

/** 获取 document 内的 Range */
const getDocumentRanges = (selection: Selection | null) => {
  if (!selection?.rangeCount) {
    return [];
  }

  return Array.from({ length: selection.rangeCount }, (_, index) => selection.getRangeAt(index));
};

/**
 * 获取当前选区
 * @param contextNode 选区可能所在的节点（组件根节点或鼠标事件 target），用于定位 shadow root
 */
export const getSelectionRanges = (contextNode?: Node | null): Range[] => {
  const selection = window.getSelection();
  const shadowRoots = getShadowRootChain(contextNode);

  if (selection && shadowRoots.length) {
    const shadowRange = getComposedRange(selection, shadowRoots) ?? getShadowRootRange(shadowRoots);
    if (shadowRange) {
      return [shadowRange];
    }
  }

  return getDocumentRanges(selection);
};

/** 获取当前选区中的第一个 Range */
export const getSelectionRange = (contextNode?: Node | null): Range | null => {
  return getSelectionRanges(contextNode)[0] ?? null;
};

/** 获取当前选区中的文本 */
export const getSelectionText = (contextNode?: Node | null) => {
  return getSelectionRanges(contextNode)
    .map(range => range.toString())
    .join('');
};

/**
 * 回写选区。shadow 树内的端点用 addRange 写回会被 retarget 逻辑丢弃，
 * 需要用 setBaseAndExtent 直接指定端点节点。
 */
export const restoreSelectionRange = (range?: Range | null) => {
  const selection = window.getSelection();
  if (!range || !selection) {
    return;
  }

  try {
    if (typeof selection.setBaseAndExtent === 'function') {
      selection.setBaseAndExtent(range.startContainer, range.startOffset, range.endContainer, range.endOffset);
      return;
    }

    selection.removeAllRanges();
    selection.addRange(range);
  } catch {
    // 选区端点可能已经随行渲染被替换，回写失败时保持无选区状态
  }
};
