### 记录部分常用脚本命令

1. 将django.po 读取到内存字典中
```python
import polib

# 定义要读取的文件名
filename = 'locale/en/LC_MESSAGES/django.po'

# 创建一个空字典，用于存储条目
dictionary = {}

# 打开.po文件并读取条目
po = polib.pofile(filename)
for entry in po:
    # 忽略没有翻译的条目
    if not entry.translated():
        continue

    # 将msgid添加到字典中
    key = entry.msgid

    # 将msgstr添加到字典中
    value = entry.msgstr

    # 将条目添加到字典中
    dictionary[key] = value

```

2. 将内存字典内容覆盖到新django.po文件。
```python
import polib
filename = 'locale/en/LC_MESSAGES/django.po'
po = polib.pofile(filename)
dictionary = {}
# 存量覆盖
# 遍历字典并更新条目
for key, value in dictionary.items():
    # 在.po文件中查找msgid
    entry = po.find(key)
    if not entry:
        continue
    # 更新msgstr
    entry.msgstr = value

# 增量覆盖
# 遍历字典并更新条目
for key, value in dictionary.items():
    # 在.po文件中查找msgid
    entry = po.find(key)
    # 如果找不到这个条目，则新建一个POEntry对象并添加到.po文件中
    if not entry:
        # 增量覆盖
        entry = polib.POEntry(msgid=key)
        # 将条目添加到.po文件中
        po.append(entry)

    # 更新msgstr
    entry.msgstr = value

# 保存
if dictionary:
    # 保存更新后的.po文件
    po.save()
```

3. 将内存字典写入json文件
```python
import json
# dictionary = {}
f = open("../translation/bkmonitor/backend/content.json", "w")
f.write(json.dumps(dictionary, ensure_ascii=False, indent=2))
f.close()

# 读取 json 文件内容
```
f = open("../translation/bkmonitor/backend/content.json", "r")
dictionary = json.loads(f.read())
f.close()

4. 清理重复词条
```python
import polib

def remove_duplicate_msgid(pofile_path):
    # 加载 .po 文件
    po = polib.pofile(pofile_path)

    # 定义一个字典，用于存储非重复的 msgid 和其对应的 msgstr
    msg_map = {}

    # 遍历每一个 entry
    for entry in po:
        # 如果当前 entry 的 msgid 已经在 msg_map 中存在，则将当前 entry 的 msgstr 添加到 msg_map 对应的 entry 中的 msgstr 字段
        if entry.msgid in msg_map:
            msg_map[entry.msgid].msgstr += entry.msgstr
        else:
            # 如果当前 entry 的 msgid 在 msg_map 中不存在，则将当前 entry 添加到 msg_map 中
            msg_map[entry.msgid] = entry

    # 重新生成 .po 文件
    po = polib.POFile()
    po.metadata = po.metadata
    po[:] = msg_map.values()
    po.save(pofile_path)
    
# 调用 remove_duplicate_msgid 函数，传入指定的 .po 文件路径
remove_duplicate_msgid('locale/en/LC_MESSAGES/django.po')
```