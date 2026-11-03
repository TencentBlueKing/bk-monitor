/* Copyright (C) 2026 Tencent. BlueKing PaaS, MIT License. */
import fs from 'node:fs';
import { dirname, resolve, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import { parse } from '@vue/compiler-sfc';
const root=fileURLToPath(new URL('../',import.meta.url));
export const choiceControls={
 'bk-checkbox':{export:'Checkbox',old:'bkCheckbox'},
 'bk-checkbox-group':{export:'CheckboxGroup',old:'bkCheckboxGroup'},
 'bk-radio':{export:'Radio',old:'bkRadio'},
 'bk-radio-button':{export:'RadioButton',old:'bkRadioButton'},
 'bk-radio-group':{export:'RadioGroup',old:'bkRadioGroup'},
 'bk-switcher':{export:'Switch',old:'bkSwitcher'},
 'bk-spin':{export:'Loading',old:'bkSpin'},
};
const walk=dir=>fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(resolve(dir,e.name)):[resolve(dir,e.name)]);
export function migrateChoiceControls(source,filename){
 const descriptor=filename.endsWith('.vue')?parse(source).descriptor:null;
 const edits=[],counts={};const put=(start,end,text)=>edits.push({start,end,text});
 const blocks=descriptor?[descriptor.script,descriptor.scriptSetup].filter(Boolean).map(s=>({text:s.content,offset:s.loc.start.offset})):[{text:source,offset:0}];
 const importsByName=new Map();
 for(const block of blocks){
  const ast=ts.createSourceFile(filename,block.text,ts.ScriptTarget.Latest,true,ts.ScriptKind.TSX),native=new Set();
  const pos=n=>block.offset+n.getStart(ast),end=n=>block.offset+n.end;
  for(const node of ast.statements) if(ts.isImportDeclaration(node)&&/compat\/tdesign\/magic-controls/.test(node.moduleSpecifier.text)){
   const all=[...(node.importClause?.namedBindings?.elements||[])]; const retained=[];
   for(const e of all){const old=(e.propertyName||e.name).text;const found=Object.entries(choiceControls).find(([,spec])=>spec.old===old);if(found){importsByName.set(e.name.text,found[0]);native.add(`${found[1].export} as ${e.name.text}`);}else retained.push(e);}
   if(all.length!==retained.length)put(pos(node),end(node),retained.length?`import { ${retained.map(e=>e.getText(ast)).join(', ')} } from ${node.moduleSpecifier.getText(ast)};`:'');
  }
  const val=p=>!p.initializer?'true':ts.isJsxExpression(p.initializer)?p.initializer.expression?.getText(ast)||'true':p.initializer.getText(ast);
  const visit=node=>{
   if(ts.isJsxOpeningElement(node)||ts.isJsxSelfClosingElement(node)){
    const tag=node.tagName.getText(ast),key=choiceControls[tag]?tag:importsByName.get(tag),spec=choiceControls[key];
    if(spec){counts[key]=(counts[key]||0)+1;
     if(key===tag){const nativeName='T'+spec.export;put(pos(node.tagName),end(node.tagName),nativeName);native.add(`${spec.export} as ${nativeName}`);}
     const props=node.attributes.properties.filter(ts.isJsxAttribute),get=name=>props.find(p=>p.name.getText(ast)===name);
     let parent=node.parent;while(parent&&!ts.isJsxElement(parent))parent=parent.parent;
     let ancestor=parent?.parent;let inGroup=false;while(ancestor){if(ts.isJsxElement(ancestor)&&['bk-checkbox-group','TCheckboxGroup',...[...importsByName].filter(([,v])=>v==='bk-checkbox-group').map(([k])=>k)].includes(ancestor.openingElement.tagName.getText(ast))){inGroup=true;break;}ancestor=ancestor.parent;}
     for(const prop of props){const name=prop.name.getText(ast),value=val(prop);
      if((key==='bk-radio'||key==='bk-radio-button')&&name==='label')put(pos(prop.name),end(prop.name),'value');
      if(key==='bk-checkbox'&&name==='label')put(pos(prop.name),end(prop.name),'value');
      if(key==='bk-checkbox'&&name==='value'&&!inGroup&&!get('label')&&!get('checked'))put(pos(prop.name),end(prop.name),'checked');
      if(key==='bk-checkbox'&&((name==='true-value'&&value==='true')||(name==='false-value'&&value==='false')))put(pos(prop),end(prop),'');
      if(key==='bk-switcher'&&name==='theme')put(pos(prop),end(prop),'');
      if(key==='bk-switcher'&&name==='preCheck'){const model=get('value')||get('v-model');if(!model)throw Error(`Switch guard without state: ${filename}`);put(pos(prop),end(prop),`beforeChange={() => (${value})(!(${val(model)}))}`);}
      if(key==='bk-spin'&&name==='size'&&/^['"]mini['"]$/.test(value))put(pos(prop.initializer),end(prop.initializer),'"small"');
      if(name==='ext-cls'){const cls=get('class');if(cls){put(pos(cls.initializer),end(cls.initializer),`{[${val(cls)}, ${value}]}`);put(pos(prop),end(prop),'');}else put(pos(prop.name),end(prop.name),'class');}
     }
    }
   }
   if(ts.isJsxClosingElement(node)&&choiceControls[node.tagName.getText(ast)])put(pos(node.tagName),end(node.tagName),'T'+choiceControls[node.tagName.getText(ast)].export);
   ts.forEachChild(node,visit);
  };visit(ast);
  if(native.size)put(block.offset,block.offset,`\nimport { ${[...native].join(', ')} } from 'tdesign-vue-next';\n`);
 }
 if(descriptor?.template?.ast){
  const visit=(node,ancestors=[])=>{
   if(node.type===1&&choiceControls[node.tag]){
    const key=node.tag,spec=choiceControls[key],nativeTag='t-'+spec.export.replace(/[A-Z]/g,(c,i)=>(i?'-':'')+c.toLowerCase());counts[key]=(counts[key]||0)+1;
    const start=node.loc.start.offset,local=node.loc.source;put(start+1,start+1+key.length,nativeTag);const close=local.lastIndexOf('</'+key);if(close>=0)put(start+close+2,start+close+2+key.length,nativeTag);
    const name=p=>p.type===6?p.name:p.arg?.content;const value=p=>p.type===6?p.value?JSON.stringify(p.value.content):'true':p.exp?.content||'true';const get=n=>node.props.find(p=>name(p)===n);const rename=(p,n)=>put(p.loc.start.offset,p.loc.end.offset,p.loc.source.replace(name(p),n));
    const inGroup=ancestors.some(n=>['bk-checkbox-group','t-checkbox-group'].includes(n.tag));
    for(const prop of node.props){const n=name(prop),v=value(prop);
     if(['bk-radio','bk-radio-button'].includes(key)&&n==='label')rename(prop,'value');
     if(key==='bk-checkbox'&&n==='label')rename(prop,'value');
     if(key==='bk-checkbox'&&n==='value'&&!inGroup&&!get('label')&&!get('checked'))rename(prop,'checked');
     if(key==='bk-checkbox'&&((n==='true-value'&&v==='true')||(n==='false-value'&&v==='false')))put(prop.loc.start.offset,prop.loc.end.offset,'');
     if(key==='bk-switcher'&&n==='theme')put(prop.loc.start.offset,prop.loc.end.offset,'');
     if(key==='bk-switcher'&&n==='pre-check'){const model=get('value')||node.props.find(p=>p.type===7&&p.name==='model');if(!model)throw Error(`Switch guard without state: ${filename}`);put(prop.loc.start.offset,prop.loc.end.offset,`:before-change="() => (${v})(!(${value(model)}))"`);}
     if(key==='bk-spin'&&n==='size'&&v==='"mini"')put(prop.loc.start.offset,prop.loc.end.offset,'size="small"');
     if(n==='ext-cls'){const cls=get('class');if(cls){put(cls.loc.start.offset,cls.loc.end.offset,`:class="[${value(cls).replaceAll('"',"'")}, ${v.replaceAll('"',"'")}]"`);put(prop.loc.start.offset,prop.loc.end.offset,'');}else rename(prop,'class');}
    }
   }
   for(const child of node.children||[])visit(child,[...ancestors,node]);
  };visit(descriptor.template.ast);
 }
 let output=source;for(const e of edits.sort((a,b)=>b.start-a.start||b.end-a.end))output=output.slice(0,e.start)+e.text+output.slice(e.end);
 for(const [key,spec]of Object.entries(choiceControls)){const native='t-'+spec.export.replace(/[A-Z]/g,(c,i)=>(i?'-':'')+c.toLowerCase());output=output.replace(new RegExp('\\.'+key+'(?![\\w-])','g'),'.'+native);}
 return{output,counts};
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const report={files:[],counts:{}};for(const file of walk(resolve(root,'src')).filter(f=>/\.(vue|[jt]sx?)$/.test(f)&&!f.includes('/platform/compat/')&&!f.endsWith('.d.ts'))){const source=fs.readFileSync(file,'utf8'),result=migrateChoiceControls(source,file);for(const [k,n]of Object.entries(result.counts))report.counts[k]=(report.counts[k]||0)+n;if(result.output!==source){report.files.push(relative(root,file));if(process.argv.includes('--write')){const backup=resolve('/tmp/bklog-native-controls-before',relative(root,file));if(!fs.existsSync(backup)){fs.mkdirSync(dirname(backup),{recursive:true});fs.writeFileSync(backup,source);}fs.writeFileSync(file,result.output);}}}fs.writeFileSync(resolve(root,'ai-native/choice-controls-migration.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({files:report.files.length,counts:report.counts}));
}
