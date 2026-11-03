/**
 * 判断 slot 宿主是否有可渲染内容（忽略注释和空白文本）。
 * Vue 2 空 slot / 透传未填充 slot 时常留下 comment，不能用 CSS :empty。
 * @param {Node | null} el
 * @returns {boolean}
 */
export function hostHasRenderableContent(el) {
  if (!el) {
    return false;
  }

  const nodes = el.childNodes;
  for (let i = 0; i < nodes.length; i++) {
    const node = nodes[i];
    if (node.nodeType === 1) {
      return true;
    }
    if (node.nodeType === 3 && String(node.textContent).trim()) {
      return true;
    }
  }

  return false;
}
