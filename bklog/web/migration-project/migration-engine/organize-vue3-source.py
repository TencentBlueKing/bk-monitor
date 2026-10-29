# Copyright (C) 2021 THL A29 Limited, a Tencent company. MIT License.
from pathlib import Path, PurePosixPath
import json, hashlib, re, tarfile, shutil
import sys
root=Path(__file__).resolve().parents[2]/'packages/web-v3'
if '--apply' not in sys.argv:
 print('Historical one-shot relocation. Read source-map.json; pass --apply only before first migration.')
 sys.exit(0)
source=root/'src-native'; target=root/'src'; assets=root/'ai-native'; assets.mkdir(exist_ok=True)
# Ownership follows source business responsibilities; implementation generations stay explicit.
view_domains={'retrieve':'retrieval/classic','retrieve-v2':'retrieval/workbench','retrieve-v3':'retrieval/workspace','retrieve-core':'retrieval/core','manage-v2/log-collection':'collection/current','manage-v2/log-clean':'cleaning/current','manage-v2/grok-manage':'grok/current','manage-v2/log-archive':'archive/current','manage-v2/log-extract':'extraction/current','manage-v2/es-cluster':'clusters/current','manage-v2/client-log':'client-logs/management','manage/log-archive':'archive/classic','manage/log-clean':'cleaning/classic','manage/manage-access':'index-sets','manage/manage-extract':'extraction/classic','manage/field-masking-separate':'masking','manage/es-cluster-status':'clusters/status','manage/report-management':'reporting','manage/manage-data-link':'data-links','manage/trace-track':'tracing','dashboard':'dashboards','authorization':'authorization','client-log-search':'client-logs/search','data-id-url':'data-id','extract':'extraction/download','share':'sharing','un-authorized':'authorization/denied','playground':'playground'}
component_domains={'collection-access':'collection/access','log-masking':'masking/components','log-ip-selector':'collection/ip-selector','ip-select':'collection/ip-select','filter-rule':'collection/filter-rule','log-import':'index-sets/import','import-from-other-index-set':'index-sets/import-from-other','index-set-label-select':'index-sets/label-select','rule-config-operate':'cleaning/rule-config','rule-table':'cleaning/rule-table','monitor-echarts':'charts','log-view':'retrieval/log-view','nav':'navigation','global-setting':'preferences','global-dialog':'preferences/dialog'}
services={'grok':'grok','archive':'archive','clean':'cleaning','masking':'masking','collect':'collection','container':'collection','ip-chooser':'collection','indexSet':'index-sets','result-tables':'index-sets','source':'index-sets','custom':'index-sets','favorite':'retrieval','retrieve':'retrieval','union-search':'retrieval','log-clustering':'retrieval','graph-analysis':'retrieval','particulars':'retrieval','extract':'extraction','extract-manage':'extraction','dashboard':'dashboards','client-log':'client-logs','new-report':'reporting','link-configuration':'data-links','authorization':'authorization','auth':'authorization','alert_strategy':'alerts','monitor':'monitoring','plugins':'integrations','migrate':'migration'}
top={'router':'app/router','store':'app/state','api':'platform/http','request':'platform/request','storage':'platform/persistence','language':'platform/i18n','adapters':'platform/compat','common':'shared/lib','hooks':'shared/composables','mixins':'shared/mixins','utils':'shared/utils','global':'shared/global','directives':'shared/directives','plugins':'platform/plugins','const':'shared/constants','scss':'shared/styles','static':'shared/assets/static','images':'shared/assets/images','assets':'shared/assets/resources','skeleton':'app/skeleton'}
special={'main.js':'app/bootstrap/start.js','app.tsx':'app/shell/app.tsx','app.scss':'app/shell/app.scss','preload.ts':'app/bootstrap/preload.ts','public-path.js':'app/bootstrap/public-path.js','polyfill.ts':'platform/compat/polyfill.ts','open-telemetry.ts':'platform/observability/open-telemetry.ts','index.d.ts':'shared/types/index.d.ts','vue-virtual-scroller.d.ts':'shared/types/vue-virtual-scroller.d.ts','index.html':'index.html'}
def mapped(p):
 s=p.as_posix()
 if s in special:return special[s]
 if s.startswith('views/'):
  rest=s[6:]
  for prefix,domain in sorted(view_domains.items(),key=lambda x:-len(x[0])):
   if rest==prefix or rest.startswith(prefix+'/'):return 'features/'+domain+rest[len(prefix):]
  if rest=='404.vue':return 'app/shell/not-found.vue'
  if rest.startswith('retrieve-'):return 'features/retrieval/'+rest
  return 'features/management/'+rest
 if s.startswith('components/'):
  rest=s[11:]; name=rest.split('/')[0]
  if name in component_domains:return 'features/'+component_domains[name]+rest[len(name):]
  return 'shared/ui/'+rest
 if s.startswith('services/'):
  domain=services.get(p.stem)
  return ('features/'+domain+'/services/' if domain else 'platform/services/')+p.name
 first,*tail=p.parts
 if first in top:return top[first]+'/'+('/'.join(tail))
 raise ValueError(s)
files=sorted(p for p in source.rglob('*') if p.is_file()); mapping={p.relative_to(source).as_posix():mapped(p.relative_to(source)) for p in files}
assert len(set(mapping.values()))==len(files),'Target collision'
exts=['','.js','.ts','.tsx','.jsx','.vue','.mjs','.scss','.css','.json']
def resolve(raw, owner):
 base=raw.split('?')[0].split('#')[0]
 if base.startswith('@/'): path=source/base[2:]
 elif base.startswith('.') and not base.startswith('...'):path=source/owner.parent/base
 elif base.startswith('/images/'):path=source/base[1:]
 else:return None
 # Resolve Sass partials and extensionless/index imports without changing package imports.
 for suffix in exts:
  cand=Path(str(path)+suffix).resolve()
  if cand.is_file() and cand.is_relative_to(source):return cand.relative_to(source).as_posix()
 for suffix in exts[1:]:
  for cand in [path/('index'+suffix),path.with_name('_'+path.name+suffix)]:
   if cand.is_file() and cand.resolve().is_relative_to(source):return cand.resolve().relative_to(source).as_posix()
 return None
quoted=re.compile(r'''(?P<q>['"])(?P<value>[^'"\n]+)(?P=q)''')
text_ext={'.js','.ts','.tsx','.jsx','.vue','.mjs','.scss','.css','.json','.html','.svg'}
rewrites=0; edges=[]
def rewrite(text,owner,dest):
 global rewrites
 def sub(match):
  global rewrites
  raw=match['value']; found=resolve(raw,owner)
  if not found:return match[0]
  new=mapping[found]; marker=re.search(r'[?#]',raw); tail=raw[marker.start():] if marker else ''
  clean=raw[:marker.start()] if marker else raw
  # Preserve extension omission but resolve directory imports to explicit index modules.
  if not PurePosixPath(clean).suffix and PurePosixPath(found).suffix in exts[1:]:new=str(PurePosixPath(new).with_suffix(''))
  if raw.startswith('@/'): value='@/'+new
  else:
   import os
   value=os.path.relpath(new,str(PurePosixPath(dest).parent))
   if not value.startswith('.'):value='./'+value
  value+=tail
  edges.append({'from':dest,'to':mapping[found],'specifier':value})
  rewrites+=int(raw!=value)
  return match['q']+value+match['q']
 text=quoted.sub(sub,text)
 # CSS url() can be unquoted; assets and glob keys need stable build-time source-root paths.
 def css(match):
  raw=match[1];found=resolve(raw,owner)
  if not found:return match[0]
  import os
  rel=os.path.relpath(mapping[found],str(PurePosixPath(dest).parent))
  return 'url('+rel+')'
 text=re.sub(r'url\(([^\s\'"()]+)\)',css,text)
 if owner.as_posix().endswith('common-comp/classify-card.tsx'):
  text=text.replace('/images/log-collection/','/shared/assets/images/log-collection/')
 return text
manifest={'schemaVersion':1,'sourceRoot':'src-native','targetRoot':'src','sourceCount':len(files),'files':[]}
prepared={}
for p in files:
 old=p.relative_to(source).as_posix(); dest=mapping[old]; data=p.read_bytes()
 if p.suffix in text_ext:data=rewrite(data.decode('utf-8'),PurePosixPath(old),dest).encode()
 prepared[dest]=data
 manifest['files'].append({'source':old,'target':dest,'sourceSha256':hashlib.sha256(p.read_bytes()).hexdigest(),'targetSha256':hashlib.sha256(data).hexdigest()})
# Freeze the prototype before switching ownership. Never delete the source baseline.
archive=root/'architecture-archive';archive.mkdir(exist_ok=True)
archivefile=archive/'src-prototype-20261028.tar.gz'
assert not archivefile.exists(),'Already migrated: review instead of reapplying'
with tarfile.open(archivefile,'w:gz') as tar:tar.add(target,arcname='src')
(archive/'manifest.json').write_text(json.dumps({'archive':archivefile.name,'sha256':hashlib.sha256(archivefile.read_bytes()).hexdigest(),'purpose':'Pre-architecture src prototype; includes existing uncommitted changes'},indent=2)+'\n')
shutil.rmtree(target)
for name,data in prepared.items():
 p=target/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
license=(source/'main.js').read_text().split('*/',1)[0]+'*/\n\n'
(target/'main.js').write_text(license+"// Composition entry: keep business initialization in app/bootstrap.\nimport './app/bootstrap/start.js';\n")
(assets/'source-map.json').write_text(json.dumps(manifest,indent=2)+'\n')
(assets/'relocation-edges.json').write_text(json.dumps({'schemaVersion':1,'kind':'resolved path references (not a complete dynamic graph)','edges':edges},indent=2)+'\n')
print(json.dumps({'files':len(files),'rewrittenReferences':rewrites,'referenceEdges':len(edges),'domains':sorted({s.split('/')[1] for s in mapping.values() if s.startswith('features/')})},indent=2))
# Existing tests must exercise the new source, while retaining Vue2 comparison fixtures.
tests=root/'tests';shutil.copytree(root/'tests-native',tests)
for p in tests.rglob('*.mjs'):
 text=p.read_text()
 for old,new in sorted(mapping.items(),key=lambda x:-len(x[0])):
  text=text.replace('../src-native/'+old,'../src/'+new)
 p.write_text(text)
