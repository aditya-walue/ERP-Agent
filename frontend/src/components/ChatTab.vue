<template>
  <div class="flex flex-col gap-4 sm:gap-5">
    <div v-if="messages.length === 0" class="motion-safe:animate-fade-rise flex w-full items-start gap-1.5">
      <BotIcon />
      <div class="w-fit max-w-[calc(100%-2.5rem)] rounded-[10px_10px_10px_3px] border border-brand-100 bg-gradient-to-br from-brand-50 to-white px-4 py-3 shadow-[0_12px_28px_-22px_rgba(109,79,194,0.55)] max-[600px]:max-w-[calc(100%-2.25rem)]">
        <p class="text-xs font-semibold leading-relaxed text-slate-900">
          Hi! I'm your ERP assistant
        </p>
        <p class="mt-1 text-[11px] leading-relaxed text-slate-500">
          Ask me how to do something, what a customization does, or what's not working.
        </p>
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
import BotIcon from './BotIcon.vue'
import ChatMessage from './ChatMessage.vue'

defineProps({
  messages: {
    type: Array,
    required: true,
  },
})
</script>
