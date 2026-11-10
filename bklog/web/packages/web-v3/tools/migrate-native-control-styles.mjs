/* Copyright (C) 2026 Tencent. BlueKing PaaS, MIT License. */
import fs from 'node:fs';
import { resolve, dirname, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from '@vue/compiler-sfc';
const root=fileURLToPath(new URL('../',import.meta.url));
const classes={
 'bk-form-input':'t-input__inner','bk-form-control':'t-input__wrap',
 'bk-alert':'t-alert','bk-alert-wraper':'t-alert','bk-alert-title':'t-alert__message',
 'bk-tag':'t-tag','bk-tag-close':'t-tag__icon-close','bk-tag-info':'t-tag--primary',
 'bk-progress':'t-progress','bk-progress-text':'t-progress__info','bk-badge':'t-badge',
 'bk-button':'t-button','bk-button-small':'t-size-s','bk-button-large':'t-size-l','bk-button-normal':'t-size-m','bk-button-text':'t-button--variant-text',
 't-button-small':'t-size-s','t-button-large':'t-size-l','t-button-normal':'t-size-m','t-button-text':'t-button--variant-text',
 'bk-checkbox':'t-checkbox','bk-checkbox-group':'t-checkbox-group','bk-checkbox-text':'t-checkbox__label','bk-checkbox-input':'t-checkbox__input',
 't-checkbox-text':'t-checkbox__label','t-checkbox-input':'t-checkbox__input',
 'bk-radio':'t-radio','bk-radio-group':'t-radio-group','bk-radio-button':'t-radio-button','bk-radio-text':'t-radio__label','bk-radio-input':'t-radio__input','bk-form-radio':'t-radio',
 't-radio-text':'t-radio__label','t-radio-input':'t-radio__input',
 'bk-switcher':'t-switch','bk-switcher-small':'t-size-s','bk-switcher-large':'t-size-l','bk-spin':'t-loading',
};
export const migrateControlSelectors=source=>source.replace(/\.[a-zA-Z_][\w-]*/g,token=>classes[token.slice(1)]?'.'+classes[token.slice(1)]:token)
 .replace(/(\.t-checkbox|\.t-radio|\.t-switch)\.is-checked\b/g,'$1.t-is-checked');
const walk=dir=>fs.readdirSync(dir,{withFileTypes:true}).flatMap(e=>e.isDirectory()?walk(resolve(dir,e.name)):[resolve(dir,e.name)]);
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const files=[];
 for(const file of walk(resolve(root,'src')).filter(f=>/\.(scss|css|vue)$/.test(f)&&!f.includes('/platform/compat/')&&!f.includes('/shared/assets/'))){
  const source=fs.readFileSync(file,'utf8');let output=source;
  if(file.endsWith('.vue')){
   const styles=parse(source).descriptor.styles;
   const backup=resolve('/tmp/bklog-native-controls-before',relative(root,file));
   const oldStyles=fs.existsSync(backup)?parse(fs.readFileSync(backup,'utf8')).descriptor.styles:[];
   for(let i=styles.length-1;i>=0;i--){const style=styles[i];let original=style.content;
    if(oldStyles[i]){let simulated=oldStyles[i].content;for(const[a,b]of Object.entries({'bk-button':'t-button','bk-checkbox':'t-checkbox','bk-checkbox-group':'t-checkbox-group','bk-radio':'t-radio','bk-radio-group':'t-radio-group','bk-radio-button':'t-radio-button','bk-switcher':'t-switch','bk-spin':'t-loading'}))simulated=simulated.replaceAll('.'+a,'.'+b);
     if(simulated===style.content)original=oldStyles[i].content;
    }
    output=output.slice(0,style.loc.start.offset)+migrateControlSelectors(original)+output.slice(style.loc.end.offset);
   }
  }else output=migrateControlSelectors(source);
  if(output!==source){files.push(relative(root,file));const backup=resolve('/tmp/bklog-native-controls-before',relative(root,file));if(!fs.existsSync(backup)){fs.mkdirSync(dirname(backup),{recursive:true});fs.writeFileSync(backup,source);}fs.writeFileSync(file,output);}
 }
 console.log(JSON.stringify({styleFiles:files.length,files}));
}
