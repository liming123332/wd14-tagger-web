import { ref, onMounted, onUnmounted } from 'vue'

// 图片粘贴（Ctrl+V）+ 拖放的公共逻辑。
// 仅处理 image/*；纯文本粘贴不拦截，交给输入框正常处理
// （不破坏 PromptBoxPage 粘贴文本拆分 / UploadPage 批量标签输入）。
//
// 用法：const { dragging, dropHandlers } = useImagePasteDrop(files => ...)
//       <div v-bind="dropHandlers" :class="{ active: dragging }">...</div>
export function useImagePasteDrop(onFiles: (files: File[]) => void) {
  const dragging = ref(false)

  function onDrop(e: DragEvent) {
    dragging.value = false
    const files = Array.from(e.dataTransfer?.files || []).filter(f => f.type.startsWith('image/'))
    if (files.length) onFiles(files)
  }

  function onPaste(e: ClipboardEvent) {
    const items = e.clipboardData?.items
    if (!items) return
    const files: File[] = []
    for (const it of Array.from(items)) {
      if (it.kind === 'file' && it.type.startsWith('image/')) {
        const f = it.getAsFile()
        if (f) files.push(f)
      }
    }
    // 有图片才拦截（防止图片被当文本插入输入框）；纯文本不拦截
    if (files.length) { e.preventDefault(); onFiles(files) }
  }

  onMounted(() => window.addEventListener('paste', onPaste))
  onUnmounted(() => window.removeEventListener('paste', onPaste))

  return {
    dragging,
    dropHandlers: {
      onDragover: (e: DragEvent) => { e.preventDefault(); dragging.value = true },
      onDragleave: () => { dragging.value = false },
      onDrop,
    },
  }
}
