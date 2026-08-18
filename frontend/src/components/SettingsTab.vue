<template>
  <div class="flex flex-col gap-4">
    <div class="chat-card motion-safe:animate-fade-rise rounded-xl p-4">
    <div class="flex items-start justify-between gap-4">
      <div>
        <p class="text-sm font-semibold text-slate-900">Enable Debug Tab</p>
        <p class="mt-1 text-xs text-slate-600">
          Show or hide the Debug tab inside this chatbot.
        </p>
        <p class="mt-2 text-[11px] font-medium" :class="debugEnabled ? 'text-emerald-700' : 'text-slate-500'">
          {{ debugEnabled ? 'Debug tab is active.' : 'Debug tab is currently off.' }}
        </p>
      </div>

      <button
        type="button"
        class="relative h-7 w-12 shrink-0 rounded-full border border-slate-200 transition-all duration-200"
        :class="debugEnabled ? 'bg-emerald-500/95' : 'bg-slate-300'"
        :aria-pressed="debugEnabled ? 'true' : 'false'"
        :title="debugEnabled ? 'Disable debug tab' : 'Enable debug tab'"
        @click="$emit('toggleDebug')"
      >
        <span
          class="absolute top-0.5 h-5.5 w-5.5 rounded-full bg-white shadow-sm transition-all duration-200"
          :class="debugEnabled ? 'left-[1.45rem]' : 'left-0.5'"
        ></span>
      </button>
    </div>
  </div>
    <div class="chat-card motion-safe:animate-fade-rise rounded-xl p-4">
      <div class="flex items-start justify-between gap-4">
        <div>
          <p class="text-sm font-semibold text-slate-900">Send non-ERP questions directly to AI</p>
          <p class="mt-1 text-xs text-slate-600">Questions unrelated to your ERP will skip the system and go straight to AI</p>
        </div>
        <button
          class="group relative h-7 w-12 shrink-0 rounded-full border border-slate-200 transition-all duration-200"
          :class="sendNonERPtoaiEnabled ? 'bg-emerald-500/95' : 'bg-slate-300'"
          :aria-pressed="sendNonERPtoaiEnabled ? 'true' : 'false'"
          :title="sendNonERPtoaiEnabled ? 'Non-ERP questions are being sent directly to AI' : 'Enable direct AI reply for non-ERP questions'"
          @click="$emit('toggleSendNonERP')"
        >
          <span
            class="absolute top-0.5 h-5.5 w-5.5 rounded-full bg-white shadow-sm transition-all duration-200"
            :class="sendNonERPtoaiEnabled  ? 'left-[1.45rem]' : 'left-0.5'"
          ></span>
        </button>
      </div>
      <p class="mt-3 text-[11px] font-medium" :class="sendNonERPtoaiEnabled  ? 'text-emerald-700' : 'text-slate-500'">
        {{ sendNonERPtoaiEnabled  ? 'Non-ERP questions are now routed directly to AI' : 'Direct AI routing is currently off' }}
      </p>
    </div>
  </div>
</template>

<script setup>
defineProps({
  debugEnabled: {
  type: Boolean,
  default: false,
},
sendNonERPtoaiEnabled: {
  type: Boolean,
  default: false,
}
})

defineEmits(['toggleDebug','toggleSendNonERP'])
</script>