<template>
  <div
    class="motion-safe:animate-fade-rise flex w-full gap-1.5"
    :class="message.role === 'user' ? 'flex-col items-end' : 'items-start'"
  >
    <BotIcon v-if="message.role !== 'user'" />

    <div v-if="message.role !== 'user'" class="flex min-w-0 max-w-[calc(100%-2.5rem)] flex-1 flex-col max-[600px]:max-w-[calc(100%-2.25rem)]">
      <div
        v-if="isLoadingStatus"
        class="flex w-fit flex-col items-start gap-1"
      >
        <div
          class="chat-card inline-flex w-fit rounded-[10px_10px_10px_3px] px-3 py-2"
          role="status"
          aria-live="polite"
          :aria-label="loaderLabel"
        >
          <div class="inline-flex items-center gap-1.5">
            <span class="relative inline-flex h-4 w-4 shrink-0 items-center justify-center">
              <span class="absolute inset-0 rounded-full border border-transparent border-t-[#4b89ff] border-r-[#4b89ff]/70 animate-gemini-arc"></span>
              <svg viewBox="0 0 24 24" class="relative h-3 w-3 text-[#4b89ff] animate-gemini-spark" aria-hidden="true">
                <path fill="currentColor" d="M12 2.8c.52 3.22 1.6 5.66 3.22 7.28 1.62 1.62 4.06 2.7 7.28 3.22-3.22.52-5.66 1.6-7.28 3.22-1.62 1.62-2.7 4.06-3.22 7.28-.52-3.22-1.6-5.66-3.22-7.28-1.62-1.62-4.06-2.7-7.28-3.22 3.22-.52 5.66-1.6 7.28-3.22 1.62-1.62 2.7-4.06 3.22-7.28Z"/>
              </svg>
            </span>
            <span class="sr-only">{{ loaderLabel }}</span>
            <span class="inline-flex items-center gap-1" aria-hidden="true">
              <span class="h-1.5 w-1.5 rounded-full bg-[#3a67c9] motion-safe:animate-dot-wave" style="animation-delay: 0ms"></span>
              <span class="h-1.5 w-1.5 rounded-full bg-[#3a67c9] motion-safe:animate-dot-wave" style="animation-delay: 160ms"></span>
              <span class="h-1.5 w-1.5 rounded-full bg-[#3a67c9] motion-safe:animate-dot-wave" style="animation-delay: 320ms"></span>
            </span>
          </div>
        </div>
      </div>
      <div
        v-else
        class="flex w-fit max-w-full flex-col items-start gap-2"
      >
        <div
          class="chat-card relative w-fit max-w-full whitespace-pre-line rounded-[10px_10px_10px_3px] px-4 py-3 text-xs leading-relaxed wrap-anywhere text-slate-900"
        >
          <div
            class="overflow-x-auto"
            :class="shouldCollapse && !isExpanded ? 'max-h-48 overflow-y-hidden' : ''"
            v-html="renderedMessage"
            @click="handleMessageClick"
          ></div>
          <div
            v-if="shouldCollapse && !isExpanded"
            class="pointer-events-none absolute inset-x-0 bottom-0 h-14 rounded-b-[10px] bg-linear-to-t from-white via-white/92 to-white/0"
            aria-hidden="true"
          ></div>
        </div>

        <div
          v-if="shouldCollapse"
          class="flex flex-wrap items-center gap-2"
        >
          <button
            type="button"
            class="inline-flex items-center rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-600 transition-colors duration-200 hover:border-brand-200 hover:text-brand-600"
            :title="isExpanded ? 'Collapse response' : 'Expand response'"
            :aria-label="isExpanded ? 'Collapse response' : 'Expand response'"
            @click="isExpanded = !isExpanded"
          >
            {{ isExpanded ? 'Collapse' : 'Expand' }}
          </button>
        </div>
      </div>
    </div>

    <div
  v-else
  class="w-fit max-w-[85%] whitespace-pre-line rounded-[13px_13px_3px_13px] bg-linear-to-br from-brand-500 to-brand-600 px-4 py-3 text-[11px] leading-relaxed wrap-anywhere text-white shadow-[0_14px_30px_-18px_rgba(109,79,194,0.85)] max-[600px]:max-w-[88%]"
  v-html="renderedMessage"
></div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import BotIcon from './BotIcon.vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

const props = defineProps({
  message: {
    type: Object,
    required: true,
  },
})

const isExpanded = ref(false)

function getSpeakableText(raw) {
  if (typeof raw !== 'string') return ''
    // Strip markdown before anything else
  const stripped = raw
    .replace(/[\u{1F000}-\u{1FFFF}]/gu, '')  // emojis block 1
    .replace(/[\u{2600}-\u{26FF}]/gu, '')     // emojis block 2
    .replace(/[\u{2700}-\u{27BF}]/gu, '')    
    .replace(/\*\*(.*?)\*\*/g, '$1')   // **bold**
    .replace(/\*(.*?)\*/g, '$1')        // *italic*
    .replace(/`([^`]+)`/g, '$1')        // `code`
    .replace(/#{1,6}\s+/g, '')          // # headings
    .replace(/[-*+]\s+/g, '')           // • bullet points
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // [links](url)
    .replace(/\s+/g, ' ') 
  if (!stripped.includes('<')) return stripped.trim()
  const parser = new DOMParser()
  const doc = parser.parseFromString(raw, 'text/html')
  return (doc.body.textContent || '').replace(/\s+/g, ' ').trim()
}

function isPlaceholderStatus() {
  return Boolean(props.message?.isStatus)
}
function handleMessageClick(event) {
  const link = event.target.closest('a')

  if (!link || !link.href) return

  event.preventDefault()
  event.stopPropagation()

  window.open(link.href, '_blank', 'noopener,noreferrer')
}
const normalizedMessageText = computed(() => getSpeakableText(props.message?.text || ''))

const isLoadingStatus = computed(() => (
  props.message?.role !== 'user' && isPlaceholderStatus()
))

const loaderLabel = computed(() => {
  if (!props.message?.isStatus) return ''
  if (props.message.statusType === 'support') return 'Sending to support'
  return normalizedMessageText.value || 'Thinking'
})

const shouldCollapse = computed(() => {
  if (props.message?.role === 'user' || isLoadingStatus.value) return false

  const plainText = normalizedMessageText.value
  const lineCount = plainText.split(/\n+/).filter(Boolean).length
  return plainText.length > 520 || lineCount > 8
})

const renderedMessage = computed(() => {
  const raw = props.message?.text || ''
  return DOMPurify.sanitize(marked.parse(raw))
})

watch(
  () => props.message.text,
  () => {
    isExpanded.value = false
  },
)

</script>
