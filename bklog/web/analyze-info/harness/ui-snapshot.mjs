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
export function captureUi({bindings=[]}={}) {
  const styleKeys=['fontFamily','fontSize','fontWeight','lineHeight','color','backgroundColor','borderTopWidth','borderTopColor','borderRadius','padding','margin','whiteSpace','textOverflow','overflow','position','zIndex','transform','opacity','pointerEvents','isolation'];
  const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.display!=='none'&&s.visibility!=='hidden'&&s.opacity!=='0'&&!e.closest('[hidden]');};
  const rectangle=e=>{const r=e.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height};};
  const role=e=>e.getAttribute('role')??({BUTTON:'button',INPUT:e.type==='checkbox'?'checkbox':'textbox',TEXTAREA:'textbox',SELECT:'combobox',A:'link'}[e.tagName]??null);
  const visibleText = element => {
    const text = [], walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      let hidden = false;
      for (let parent = node.parentElement; parent; parent = parent.parentElement) {
        const style = getComputedStyle(parent);
        if (parent.hidden || parent.getAttribute('aria-hidden') === 'true' || style.display === 'none' || style.visibility === 'hidden') {hidden = true;break;}
        if (parent === element) break;
      }
      if (!hidden) text.push(node.textContent);
    }
    return text.join('').trim();
  };
  const name=e=>e.getAttribute('aria-label')??(e.getAttribute('aria-labelledby')?.split(/\s+/).map(id=>document.getElementById(id)?.textContent??'').join(' '))??e.getAttribute('title')??visibleText(e);
  const nodes=[],errors=[];
  for(const binding of bindings){
    const matches=[...document.querySelectorAll(binding.selector)].filter(visible);
    if(matches.length!==1){errors.push({semanticId:binding.semanticId,kind:matches.length?'AMBIGUOUS_TARGET':'MISSING_TARGET',matches:matches.length});continue;}
    const e=matches[0],s=getComputedStyle(e),rect=rectangle(e),contexts=[],scroll=[];
    const nameTargets=binding.nameSelector?[...e.querySelectorAll(binding.nameSelector)].filter(visible):[e];
    if(nameTargets.length!==1){errors.push({semanticId:binding.semanticId,kind:'INVALID_NAME_TARGET',matches:nameTargets.length});continue;}
    for(let p=e.parentElement;p;p=p.parentElement){const ps=getComputedStyle(p);if(ps.transform!=='none'||Number(ps.opacity)<1||ps.isolation==='isolate'||ps.zIndex!=='auto'&&ps.position!=='static')contexts.push({tag:p.tagName,rect:rectangle(p),position:ps.position,zIndex:ps.zIndex,transform:ps.transform,opacity:ps.opacity,isolation:ps.isolation});if(/auto|scroll|hidden|clip/.test(ps.overflow+ps.overflowX+ps.overflowY))scroll.push({tag:p.tagName,rect:rectangle(p),scrollTop:p.scrollTop,scrollLeft:p.scrollLeft,scrollHeight:p.scrollHeight,scrollWidth:p.scrollWidth,clientHeight:p.clientHeight,clientWidth:p.clientWidth,overflow:ps.overflow});}
    const points=[[rect.x+rect.width/2,rect.y+rect.height/2],[rect.x+2,rect.y+2],[rect.x+rect.width-2,rect.y+rect.height-2]].filter(([x,y])=>x>=0&&y>=0&&x<innerWidth&&y<innerHeight).map(([x,y])=>{const top=document.elementsFromPoint(x,y)[0];return{x,y,hit:!!top&&(top===e||e.contains(top)),topTag:top?.tagName??null};});
    let clip={left:Math.max(0,rect.x),top:Math.max(0,rect.y),right:Math.min(innerWidth,rect.x+rect.width),bottom:Math.min(innerHeight,rect.y+rect.height)};
    for(const a of scroll){clip={left:Math.max(clip.left,a.rect.x),top:Math.max(clip.top,a.rect.y),right:Math.min(clip.right,a.rect.x+a.clientWidth),bottom:Math.min(clip.bottom,a.rect.y+a.clientHeight)};}
    const visibleArea=Math.max(0,clip.right-clip.left)*Math.max(0,clip.bottom-clip.top);
    nodes.push({semanticId:binding.semanticId,role:role(e),name:name(nameTargets[0]),value:e.type==='password'?'[redacted]':('value'in e?e.value:undefined),checked:'checked'in e?e.checked:undefined,expanded:e.hasAttribute('aria-expanded')?e.getAttribute('aria-expanded')==='true':undefined,disabled:!!e.disabled||e.getAttribute('aria-disabled')==='true',focused:document.activeElement===e||e.contains(document.activeElement),rect,styles:Object.fromEntries(styleKeys.map(k=>[k,s[k]])),stackingContexts:contexts,scrollAncestors:scroll,hitTests:points,occluded:points.length?points.every(p=>!p.hit):undefined,clippedRatio:rect.width*rect.height?1-visibleArea/(rect.width*rect.height):1});
  }
  return{schemaVersion:1,url:location.href,viewport:{width:innerWidth,height:innerHeight,dpr:devicePixelRatio},nodes,errors};
}


/** Wait for finite CSS transitions and consecutive stable animation frames. */
export async function waitForUiIdle(locator) {
  await locator.evaluate(async element => {
    let previous, stable = 0;
    const deadline = performance.now() + 5000;
    while (performance.now() < deadline) {
      await new Promise(resolve => requestAnimationFrame(resolve));
      const animations = new Set();
      for (let node = element; node; node = node.parentElement) {
        for (const animation of node.getAnimations()) {
          if (animation.playState === 'running' && animation.effect?.getComputedTiming().iterations !== Infinity) animations.add(animation);
        }
      }
      if (animations.size) {
        await Promise.race([
          Promise.all([...animations].map(animation => animation.finished.catch(() => {}))),
          new Promise((_, reject) => setTimeout(() => reject(new Error('UI_ANIMATION_NOT_SETTLED')), Math.max(0, deadline - performance.now()))),
        ]);
        previous = undefined;stable = 0;continue;
      }
      const rect = element.getBoundingClientRect();
      const current = [rect.x, rect.y, rect.width, rect.height];
      if (previous && current.every((value, index) => Math.abs(value - previous[index]) < 0.05)) stable++;
      else stable = 0;
      if (stable >= 2) return;
      previous = current;
    }
    throw new Error('UI_GEOMETRY_NOT_SETTLED');
  });
}
