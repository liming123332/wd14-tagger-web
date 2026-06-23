# 收藏列表新增在前 + 提示词收藏「粘贴拆分（可附图）」— 设计规格

日期：2026-06-23

## 背景

- `/collections`（[CollectionListPage.vue](../../../frontend/src/views/CollectionListPage.vue)）的列表顺序由后端 `listPromptbox()` 返回顺序决定，而后端 [create()](../../../backend/storage/promptbox_store.py#L96-L98) 用 `items.append(item)` 把新收藏加到**末尾**、前端 `load()` 原样使用——**新记录排在最后**。用户希望新增记录排在最前面。
- 提示词收藏工作台 [PromptBoxPage.vue](../../../frontend/src/views/PromptBoxPage.vue) 现有两条产项路径：①「上传图片反推」得到**带图项**（提示词是反推的）；②顶部反推卡片内的「粘贴拆分」得到**无图项**（只拆分提示词、不存图）。用户的新场景是「**保存一张图 + 自己写好的提示词、不反推**」——现有两条路都不满足（反推会覆盖提示词、粘贴拆分不带图）。

## 目标

1. `/collections` 列表按创建时间倒序——新增记录排最前。
2. PromptBoxPage 新增「**粘贴拆分（可附图）**」入口：粘贴自己写好的提示词 + 选一张图 → 拆分 + 存图（不反推）→ 带图工作区项 → 可连图带提示词另存为收藏。

## 非目标（YAGNI）

- 顶部「粘贴拆分（无图）」**保留不动**——它服务于「只想拆分提示词、不要图」，与本次新增的「附图」入口职责不同，不合并、不移除。
- 后端列表分页/排序参数：前端按 `created_at` 倒序足够，不动后端 `list_all`。
- 粘贴拆分附图强制必填：图可选；附图→带图项（主场景），不附图→无图项（退化，等价顶部能力，用户走顶部即可）。
- 抽公共「粘贴拆分」组件：顶部无图与左侧可附图差异在附图上传逻辑，内联两处即可，不抽组件。

## 现状（关键事实）

- `PromptboxItem.created_at`：ISO 字符串，`datetime.now().astimezone().isoformat(timespec="seconds")`（统一本地时区、zero-padded 固定格式）→ 字符串字典序 = 时间序，可直接 `localeCompare` 排序。
- CollectionListPage：`items`（全量）→ `filtered`（computed，前端子串搜索）→ `paged`（computed，切片 30/页）。`filtered`/`paged` 均不改顺序。
- PromptBoxPage：`items`（`WorkspaceItem[]`，反推项有 `local_id/original/thumb`，粘贴项这三者为空）→ `selectedIdx` → `selected`。`doPasteSplit`（顶部）调 `splitPrompt(text)` push 无图项。「拆分编辑（选中项）」卡片 `v-if="selected"`（空工作区不显示）。`saveAsCollection` 对 `selected` 项：有 `local_id/original` 则 `workspaceToFile` 取图附上、否则无图。
- 后端 [analyze](../../../backend/api/routes_promptbox.py#L67) 端点：图落 workspace（`store.save_workspace_image`）+ 反推 + 分类。`save_workspace_image(local_id, pil, source_name)` 已具备「只存图」能力，但无独立「不反推」端点暴露。
- 工作区图 URL：`promptboxWorkspaceImageUrl(localId, name)` = `/api/promptbox/workspace/${localId}/image/${name}`。

## 设计

### 需求 1：收藏列表新增在前（纯前端）

[CollectionListPage.vue](../../../frontend/src/views/CollectionListPage.vue) 的 `filtered` computed 末尾加倒序排序：

```ts
const filtered = computed(() => {
  const k = keyword.value.trim().toLowerCase()
  const base = k
    ? items.value.filter(it =>
        (it.title || '').toLowerCase().includes(k) ||
        (it.raw_prompt || '').toLowerCase().includes(k))
    : items.value
  // 新增在前：created_at 倒序（ISO 字符串 localeCompare 倒序 = 时间倒序）
  return [...base].sort((a, b) => (b.created_at || '').localeCompare(a.created_at || ''))
})
```

- 在 `filtered` 排序（而非 `items`）保证搜索结果也新在前；`paged` 切片继承 `filtered` 顺序。
- 不动后端、不动 `RandomPage`（它调 `listPromptbox` 后 Fisher-Yates 洗牌，顺序无关）。
- `created_at` 缺失时按空串兜底；同秒项保留 `base` 原序（V8 稳定排序，`base` 为文件 append 序=旧在前），可接受。

### 需求 2：粘贴拆分（可附图）

#### 2a. 后端新增「只存图不反推」端点

[routes_promptbox.py](../../../backend/api/routes_promptbox.py) 新增（注册位置紧跟 `analyze`、在 `/{item_id}` 之前）：

```python
@router.post("/workspace/image")
def upload_workspace_image(files: list[UploadFile] = File(...)):
    """只存图到 workspace、不反推：供「粘贴拆分（可附图）」给自写提示词附图用。
    复用 save_workspace_image；不调 tagger/classifier。"""
    store = get_promptbox_store()
    out = []
    for f in files:
        try:
            pil = Image.open(f.file)
            pil.load()
        except (UnidentifiedImageError, OSError) as e:
            raise HTTPException(status_code=400, detail=f"bad image {f.filename}: {e}")
        local_id = store.new_id()
        orig, thumb, w, h = store.save_workspace_image(local_id, pil, f.filename or "img.png")
        out.append({"local_id": local_id, "original": orig, "thumb": thumb, "width": w, "height": h})
    return {"items": out}
```

- 复用 `store.save_workspace_image`（原图 + webp 缩略图落 `workspace/<local_id>/`），与 `analyze` 的存图路径一致，`saveAsCollection` 的 `workspaceToFile` 可正常取图。
- 不加载/不调用 tagger、classifier。

#### 2b. 前端 client 新增上传函数

[client.ts](../../../frontend/src/api/client.ts)：

```ts
export interface WorkspaceImageInfo {
  local_id: string; original: string; thumb: string; width: number; height: number
}
export async function uploadPromptboxWorkspaceImage(
  files: File[],
): Promise<{ items: WorkspaceImageInfo[] }> {
  const fd = new FormData()
  for (const f of files) fd.append('files', f)
  const r = await fetch(`${base}/api/promptbox/workspace/image`, { method: 'POST', body: fd })
  if (!r.ok) throw new Error(await r.text())
  return r.json()
}
```

#### 2c. PromptBoxPage 新增「粘贴拆分（可附图）」独立卡片

[PromptBoxPage.vue](../../../frontend/src/views/PromptBoxPage.vue)：

**布局**（解决死锁 + 满足"左侧"）：当前「拆分编辑（选中项）」卡片 `v-if="selected"`，若把粘贴拆分塞其内部，空工作区时入口消失、无法新建第一项。故新增卡片**独立、始终可见**，与拆分编辑卡片同行 flex 左右排列。

```html
<!-- 工作区网格之后、原有 </n-space> 之前插入：粘贴拆分（可附图） + 拆分编辑 同一行 -->
<div class="edit-row">
  <n-card title="粘贴拆分（可附图）" class="paste-card">
    <n-input v-model:value="pasteTextImg" type="textarea" :rows="5"
             placeholder="粘贴自己写好的提示词，逗号或换行分隔" />
    <n-upload multiple :default-upload="false" :show-file-list="false"
              v-model:file-list="pasteFileList" @change="onPasteFileChange" accept="image/*">
      <n-button size="small">选择附图（可选）</n-button>
    </n-upload>
    <span v-if="pasteFileName" style="font-size:12px;color:var(--cat-input-color,#888)">{{ pasteFileName }}</span>
    <n-button style="margin-top:8px" :loading="splitting" type="primary"
              @click="doPasteSplitWithImage">粘贴拆分</n-button>
  </n-card>
  <n-card v-if="selected" title="拆分编辑（选中项）" class="edit-card">
    <!-- 现有分类编辑（6 类 + extras + 标题/复制/保存）原样搬入，内容不变 -->
  </n-card>
</div>
```

> 注：原「拆分编辑（选中项）」`<n-card>` 的**内部内容**（`v-for` 分类编辑 + 标题/复制/另存按钮）整体不变，只是外层从独立卡片改为 `.edit-row` 内的右栏 `.edit-card`。顶部反推卡片里的「粘贴拆分（无图）」**原样保留**。

**状态 + 逻辑**（新增，与顶部 `pasteText`/`doPasteSplit` 并存、独立变量）：

```ts
const pasteTextImg = ref('')
const pasteFile = ref<File | null>(null)
const pasteFileList = ref<any[]>([])
const pasteFileName = computed(() => pasteFile.value?.name || '')

function onPasteFileChange(opts: any) {
  const f = (opts.fileList || []).map((x: any) => x.file).filter(Boolean)[0] || null
  pasteFile.value = f
}

async function doPasteSplitWithImage() {
  const text = pasteTextImg.value.trim()
  if (!text) { msg.warning('请先输入提示词'); return }
  splitting.value = true
  try {
    let local_id = '', original = '', thumb = ''
    if (pasteFile.value) {
      const up = await uploadPromptboxWorkspaceImage([pasteFile.value])
      const m = up.items[0]
      local_id = m.local_id; original = m.original; thumb = m.thumb
    }
    const res = await splitPrompt(text)
    items.value = [...items.value, {
      local_id, original, thumb,
      categories: { ...emptyCats(), ...res.categories },
      extras: [...res.extras], raw_prompt: text,
    }]
    selectedIdx.value = items.value.length - 1
    pasteTextImg.value = ''
    pasteFile.value = null
    pasteFileList.value = []
    msg.success(local_id ? '已拆分（含图）' : '已拆分')
  } catch (e: any) { msg.error('拆分失败：' + e.message) }
  finally { splitting.value = false }
}
```

- `splitting` 复用（顶部 `doPasteSplit` 也用），两入口不会同时触发。
- 附图→带图项（`local_id/original/thumb` 非空，`saveAsCollection` 会取图）；不附图→无图项（等价顶部能力）。
- `import` 增加 `uploadPromptboxWorkspaceImage`。

**样式**：

```css
.edit-row { display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap }
.paste-card { width: 300px; flex-shrink: 0 }
.paste-card > :deep(.n-card__content) { display: flex; flex-direction: column; gap: 8px }
.edit-card { flex: 1; min-width: 300px }
@media (max-width: 760px) { .paste-card, .edit-card { width: 100%; flex: 1 1 100% } }
```

## 测试

### 前端 vitest

[CollectionListPage.test.ts](../../../frontend/src/__tests__/CollectionListPage.test.ts)（已存在）增补：
- **排序**：mock `listPromptbox` 返回 `created_at` 升序 3 条（a<b<c）→ 渲染卡片顺序为 c,b,a（新在前）。
- **搜索后仍倒序**：关键词命中多条 → 命中项按倒序渲染。

[PromptBoxPage.test.ts](../../../frontend/src/__tests__/PromptBoxPage.test.ts)（已存在，若没有则新建）增补：
- **粘贴+附图**：填 `pasteTextImg` + 模拟选图 → 点「粘贴拆分」→ 调 `uploadPromptboxWorkspaceImage` + `splitPrompt`，`items` 末尾新增项 `thumb` 非空（带图）。
- **粘贴不附图**：仅填 `pasteTextImg` → 点「粘贴拆分」→ 仅调 `splitPrompt`（不调上传），新增项 `thumb` 为空。
- **顶部回归**：顶部「粘贴拆分（无图）」仍产无图项（确保保留未破坏）。

### 后端 pytest

`backend/api/test_routes_promptbox.py`（若存在则增补，否则新建）增补：
- **workspace/image 存图不反推**：POST `/api/promptbox/workspace/image` 带一张图 → 200，`items[0]` 含 `local_id/original/thumb`，workspace 目录下存在原图与 `thumb.webp`；`get_tagger` **未被调用**（mock 断言）。
- **坏图 400**：非图文件 → 400 `bad image`。

## 整合包同步

- 前端 `npm run build` → `frontend/dist` → cp 到两处整合包：
  - `i:\trae\wd14\WD14-Tagger-Web-Portable\wd14-tagger-web\frontend\dist`
  - `I:\WD14-Tagger-Web-Portable\wd14-tagger-web\frontend\dist`
- 后端 `backend/api/routes_promptbox.py` → cp 到两处整合包同路径（**只同步该文件，绝不重新打包**——`pack_portable.py` 会清空用户数据，且该文件用户正在改）。

## 风险与权衡

- **两个粘贴拆分入口共存**：顶部（无图快速拆分）与左侧（可附图）。职责不同、变量独立，用户明确两者都要；可接受冗余。
- **created_at 同秒稳定排序**：极少触发；触发时旧项在前，可接受。
- **附图可选导致的与顶部重叠**：不附图时左侧退化为无图项，与顶部等效；不报错，用户主走附图路径。
- **布局响应式**：窄屏（≤760px）左右栏堆叠为上下，保证可用。
