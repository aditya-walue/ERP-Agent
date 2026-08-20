<template>
  <div class="flex flex-col gap-4 sm:gap-5">
    <div v-if="messages.length === 0" class="motion-safe:animate-fade-rise flex flex-col items-center gap-5 px-1 pb-1 pt-4 text-center sm:pt-6">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 1024 1024"
        class="h-12 w-12 shrink-0 rounded-2xl bg-gradient-to-br from-brand-500 to-brand-600 p-2.5 fill-white shadow-[0_16px_30px_-16px_rgba(109,79,194,0.7)]"
      >
        <path d="M738.3 287.6H285.7c-59 0-106.8 47.8-106.8 106.8v303.1c0 59 47.8 106.8 106.8 106.8h81.5v111.1c0 .7.8 1.1 1.4.7l166.9-110.6 41.8-.8h117.4l43.6-.4c59 0 106.8-47.8 106.8-106.8V394.5c0-59-47.8-106.9-106.8-106.9zM351.7 448.2c0-29.5 23.9-53.5 53.5-53.5s53.5 23.9 53.5 53.5-23.9 53.5-53.5 53.5-53.5-23.9-53.5-53.5zm157.9 267.1c-67.8 0-123.8-47.5-132.3-109h264.6c-8.6 61.5-64.5 109-132.3 109zm110-213.7c-29.5 0-53.5-23.9-53.5-53.5s23.9-53.5 53.5-53.5 53.5 23.9 53.5 53.5-23.9 53.5-53.5 53.5zM867.2 644.5V453.1h26.5c19.4 0 35.1 15.7 35.1 35.1v121.1c0 19.4-15.7 35.1-35.1 35.1h-26.5zM95.2 609.4V488.2c0-19.4 15.7-35.1 35.1-35.1h26.5v191.3h-26.5c-19.4 0-35.1-15.7-35.1-35.1zM561.5 149.6c0 23.4-15.6 43.3-36.9 49.7v44.9h-30v-44.9c-21.4-6.5-36.9-26.3-36.9-49.7 0-28.6 23.3-51.9 51.9-51.9s51.9 23.3 51.9 51.9z" />
      </svg>

      <div class="flex flex-col gap-1.5">
        <h3 class="text-[15px] font-bold leading-snug text-slate-900">Ask me anything about your ERP</h3>
        <p class="mx-auto max-w-[280px] text-xs leading-relaxed text-slate-500">
          I can help you create records, troubleshoot errors, and answer how-to and workflow questions.
        </p>
      </div>

      <div class="flex w-full flex-col gap-2">
        <button
          v-for="question in suggestedQuestions"
          :key="question"
          type="button"
          class="w-full rounded-xl border border-slate-200/80 bg-slate-50 px-3.5 py-2.5 text-left text-xs font-medium text-slate-700 transition-all duration-200 hover:-translate-y-0.5 hover:border-brand-200 hover:bg-brand-50 hover:text-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/30"
          @click="$emit('ask', question)"
        >
          {{ question }}
        </button>
      </div>
    </div>
    <ChatMessage
      v-for="(msg, i) in messages"
      :key="i"
      :message="msg"
    />
  </div>
</template>

<script setup>
import ChatMessage from './ChatMessage.vue'

defineProps({
  messages: {
    type: Array,
    required: true,
  },
})

defineEmits(['ask'])

const suggestedQuestions = [
  'How do I create a Sales Invoice?',
  "Why can't I submit my Sales Order?",
  'What are the mandatory fields for a Purchase Order?',
  'What happens when I confirm a Sales Order?',
]
</script>
