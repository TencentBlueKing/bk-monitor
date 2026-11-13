/** Audit static inline visuals on native controls; dynamic expressions stay owned by business code. */
import ts from 'typescript';
import { parse } from '@vue/compiler-sfc';
import { normalizeStyle, semanticValue } from './tdesign-style-source.mjs';
const nativeTag = name => /^(?:bk-|t-)/.test(name);
function aliases(text) {
  const names = new Set();
  const sf = ts.createSourceFile('imports.tsx', text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  for (const node of sf.statements) if (ts.isImportDeclaration(node) && /tdesign|compat\/tdesign/.test(node.moduleSpecifier.text)) {
    for (const element of node.importClause?.namedBindings?.elements || []) names.add(element.name.text);
  }
  return names;
}
const propertyName = text => text.replace(/^['"]|['"]$/g,'').replace(/[A-Z]/g,c=>'-'+c.toLowerCase());
function objectChanges(expression, base) {
  const prefix='const style = (';
  const sf=ts.createSourceFile('style.ts',prefix+expression+');',ts.ScriptTarget.Latest,true);
  const root=sf.statements[0]?.declarationList?.declarations[0]?.initializer;
  const object=root&&ts.isParenthesizedExpression(root)?root.expression:root;
  if(!object||!ts.isObjectLiteralExpression(object))return [];
  return object.properties.flatMap(property=>{
    if(!ts.isPropertyAssignment(property)||!ts.isStringLiteral(property.initializer))return [];
    const value=semanticValue(propertyName(property.name.getText(sf)),property.initializer.text);
    if(value===property.initializer.text)return [];
    return [{start:base+property.initializer.getStart(sf)-prefix.length+1,end:base+property.initializer.end-prefix.length-1,value}];
  });
}
function literalCss(css) {
  const result=normalizeStyle('.t-inline{'+css+'}');
  return result.output.slice('.t-inline{'.length,-1);
}
export function inlineControlChanges(file,text,metrics = { nativeStyleSites: 0, dynamicStyleSites: 0 }) {
  const changes=[], names=aliases(text);
  if(file.endsWith('.vue')) {
    const {descriptor}=parse(text);
    const script=[descriptor.script?.content,descriptor.scriptSetup?.content].filter(Boolean).join('\n');
    for(const name of aliases(script))names.add(name);
    const visit=node=>{
      if(node.type===1&&(nativeTag(node.tag)||names.has(node.tag))){
        for(const prop of node.props||[]){
          if(prop.type===6&&prop.name==='style'&&prop.value){
            metrics.nativeStyleSites++;
            const original=prop.value.content,value=literalCss(original);
            if(value!==original)changes.push({start:prop.value.loc.start.offset+1,end:prop.value.loc.end.offset-1,value});
          }else if(prop.type===7&&prop.name==='bind'&&prop.arg?.content==='style'&&prop.exp){metrics.nativeStyleSites++;metrics.dynamicStyleSites++;changes.push(...objectChanges(prop.exp.content,prop.exp.loc.start.offset));}
        }
      }
      for(const child of node.children||[])visit(child);
      for(const branch of node.branches||[])visit(branch);
    };
    if(descriptor.template?.ast)visit(descriptor.template.ast);
    for(const script of [descriptor.script,descriptor.scriptSetup].filter(Boolean)){
      for(const change of inlineControlChanges('sfc-script.tsx',script.content,metrics))changes.push({...change,start:change.start+script.loc.start.offset,end:change.end+script.loc.start.offset});
    }
  } else if(/\.[jt]sx?$/.test(file)) {
    const sf=ts.createSourceFile(file,text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX);
    const visit=node=>{
      if((ts.isJsxOpeningElement(node)||ts.isJsxSelfClosingElement(node))&&(nativeTag(node.tagName.getText(sf))||names.has(node.tagName.getText(sf)))) {
        for(const attribute of node.attributes.properties){
          if(!ts.isJsxAttribute(attribute)||attribute.name.getText(sf)!=='style'||!attribute.initializer)continue;
          metrics.nativeStyleSites++;
          if(ts.isStringLiteral(attribute.initializer)){
            const original=attribute.initializer.text,value=literalCss(original);
            if(value!==original)changes.push({start:attribute.initializer.getStart(sf)+1,end:attribute.initializer.end-1,value});
          }else if(ts.isJsxExpression(attribute.initializer)&&attribute.initializer.expression){
            metrics.dynamicStyleSites++;
            const expression=attribute.initializer.expression;
            changes.push(...objectChanges(expression.getText(sf),expression.getStart(sf)));
          }
        }
      }
      if(ts.isCallExpression(node)&&['h','createVNode','createElement'].includes(node.expression.getText(sf))&&node.arguments.length>=2){
        const tag=node.arguments[0],name=ts.isStringLiteral(tag)?tag.text:tag.getText(sf),props=node.arguments[1];
        if((nativeTag(name)||names.has(name))&&ts.isObjectLiteralExpression(props))for(const prop of props.properties){
          if(!ts.isPropertyAssignment(prop)||propertyName(prop.name.getText(sf))!=='style')continue;
          metrics.nativeStyleSites++;
          if(ts.isStringLiteral(prop.initializer)){
            const value=literalCss(prop.initializer.text);
            if(value!==prop.initializer.text)changes.push({start:prop.initializer.getStart(sf)+1,end:prop.initializer.end-1,value});
          }else{metrics.dynamicStyleSites++;changes.push(...objectChanges(prop.initializer.getText(sf),prop.initializer.getStart(sf)));}
        }
      }
      ts.forEachChild(node,visit);
    };visit(sf);
  }
  return changes.sort((a,b)=>b.start-a.start);
}
export function normalizeInlineControls(file,text) {
  const changes=inlineControlChanges(file,text);let output=text;
  for(const change of changes)output=output.slice(0,change.start)+change.value+output.slice(change.end);
  return {output,count:changes.length};
}

export function inlineControlStyleMetrics(file,text) {
  const metrics={nativeStyleSites:0,dynamicStyleSites:0};
  const changes=inlineControlChanges(file,text,metrics);
  return {...metrics,pendingInlineNormalization:changes.length};
}
