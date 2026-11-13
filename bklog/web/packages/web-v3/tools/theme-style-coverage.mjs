/** Full source ownership ledger; records source metadata only, never runtime data. */
import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { resolve, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { inlineControlStyleMetrics } from './inline-control-styles.mjs';
import { styleDeclarations, normalizeStyle } from './tdesign-style-source.mjs';
const project=fileURLToPath(new URL('../',import.meta.url)),source=resolve(project,'src');
const ledgerFile=resolve(project,'ai-native/theme-style-contracts.json');
const walk=dir=>readdirSync(dir,{withFileTypes:true}).flatMap(entry=>entry.isDirectory()?walk(resolve(dir,entry.name)):entry.isFile()?[resolve(dir,entry.name)]:[]);
const visual=/^(?:color|background(?:-color)?|border(?:-(?:top|right|bottom|left))?(?:-color)?|outline(?:-color)?|font(?:-size|-family|-weight)?|line-height|box-shadow|border-radius|fill|stroke)$/;
const files=[];let pending=0;
for(const path of walk(source).filter(path=>/\.(scss|vue|[jt]sx?)$/.test(path))){
 const file=relative(source,path).replaceAll('\\','/'),text=readFileSync(path,'utf8');
 const sections=file.endsWith('.scss')?[text]:[...text.matchAll(/<style\b[^>]*>([\s\S]*?)<\/style>/g)].map(match=>match[1]);
 const declarations=sections.flatMap(styleDeclarations);
 const inline=inlineControlStyleMetrics(file,text);
 const contracts=[...text.matchAll(/@include bklogControls\.([\w-]+)/g)].map(match=>match[1]);
 const classes=[...new Set(sections.flatMap(section=>(section.replace(/\/\*[\s\S]*?\*\//g,'').replace(/\/\/[^\n]*/g,'').match(/\.t-[\w-]+/g)||[])))].sort();
 if(!classes.length&&!contracts.length&&!inline.nativeStyleSites)continue;
 const owner=file.startsWith('features/')?'business-context':file.startsWith('shared/styles/theme/')?'shared-theme':file.startsWith('shared/ui/')?'shared-control':'application-shell';
 const localVisual=declarations.filter(decl=>visual.test(decl.property)&&!decl.value.includes('--bklog-'));
 const pendingNormalization=sections.reduce((sum,section)=>sum+normalizeStyle(section).count,0);
 pending+=pendingNormalization+inline.pendingInlineNormalization;
 files.push({file,owner,inline,componentClasses:classes,sharedContracts:[...new Set(contracts)].sort(),semanticDeclarations:declarations.filter(decl=>decl.value.includes('--bklog-')).length,contextualDeclarations:declarations.filter(decl=>!visual.test(decl.property)).length,localVisualProperties:[...new Set(localVisual.map(decl=>decl.property))].sort(),localVisualDeclarations:localVisual.length,pendingNormalization});
}
files.sort((a,b)=>a.file.localeCompare(b.file));
const coverage={schemaVersion:1,scope:'SCSS, Vue style blocks and static inline visuals on native controls. Dynamic inline bindings retain business ownership. Local geometry, state adaptations, transparent/inherit values and special visuals retain their source selector; not a runtime acceptance ledger.',files};
if(process.argv.includes('--write'))writeFileSync(ledgerFile,JSON.stringify(coverage,null,2)+'\n');
else {
 const expected=JSON.parse(readFileSync(ledgerFile,'utf8'));
 if(JSON.stringify(expected)!==JSON.stringify(coverage)){console.error('Theme source ownership changed; review the affected files before updating the ledger.');process.exitCode=1;}
}
const modules={};for(const file of files.filter(file=>file.owner==='business-context')){const module=file.file.split('/')[1];modules[module]=(modules[module]||0)+1;}
console.log(JSON.stringify({status:pending?'PENDING_NORMALIZATION':process.exitCode?'REVIEW_REQUIRED':'COVERED',files:files.length,businessFiles:files.filter(file=>file.owner==='business-context').length,pendingNormalization:pending,inlineSites:files.reduce((sum,file)=>sum+file.inline.nativeStyleSites,0),dynamicInlineSites:files.reduce((sum,file)=>sum+file.inline.dynamicStyleSites,0),modules},null,2));
if(pending)process.exitCode=1;
