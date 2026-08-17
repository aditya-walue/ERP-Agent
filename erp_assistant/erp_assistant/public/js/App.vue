<template>
  <div class="erpa-root">
    <div class="erpa-messages" ref="scroll">
      <div v-if="messages.length === 0" class="erpa-empty">
        <p>Ask how <b>our</b> ERP works — custom fields, workflows, why a document won't submit, who can approve what.</p>
        <ul>
          <li @click="ask('How do I create a Sales Invoice?')">How do I create a Sales Invoice?</li>
          <li @click="ask('Why can\'t I submit this document?')">Why can't I submit this document?</li>
          <li @click="ask('What custom fields exist on Purchase Order?')">What custom fields exist on Purchase Order?</li>
        </ul>
      </div>

      <div v-for="(m, i) in messages" :key="i" :class="['erpa-msg', m.role]">
        <div class="erpa-bubble" v-html="render(m.content)"></div>
        <div v-if="m.citations && m.citations.length" class="erpa-cites">
          <span class="erpa-cites-label">Sources:</span>
          <span v-for="c in m.citations" :key="c.doctype"
                :class="['erpa-chip', c.is_customized ? 'custom' : 'std']"
                :title="'score ' + c.score">
            {{ c.doctype }}
          </span>
        </div>
      </div>

      <div v-if="loading" class="erpa-msg assistant">
        <div class="erpa-bubble erpa-typing"><span></span><span></span><span></span></div>
      </div>
    </div>

    <form class="erpa-input" @submit.prevent="send">
      <textarea
        v-model="draft"
        :disabled="loading"
        placeholder="Ask about this ERP implementation…"
        @keydown.enter.exact.prevent="send"
      ></textarea>
      <button type="submit" :disabled="loading || !draft.trim()">Ask</button>
    </form>
  </div>
</template>

<script>
import { marked } from "marked";

export default {
  name: "ErpAssistant",
  data() {
    return { draft: "", messages: [], loading: false };
  },
  methods: {
    render(text) {
      return marked.parse(text || "");
    },
    ask(q) {
      this.draft = q;
      this.send();
    },
    async send() {
      const question = this.draft.trim();
      if (!question || this.loading) return;
      this.messages.push({ role: "user", content: question });
      this.draft = "";
      this.loading = true;
      this.scroll();
      try {
        const r = await frappe.call({
          method: "erp_assistant.api.ask_agent",
          args: { question },
        });
        const data = (r && r.message) || {};
        this.messages.push({
          role: "assistant",
          content: data.answer || "(no answer)",
          citations: data.citations || [],
        });
      } catch (e) {
        this.messages.push({
          role: "assistant",
          content: "**Error:** " + (e.message || "request failed"),
        });
      } finally {
        this.loading = false;
        this.scroll();
      }
    },
    scroll() {
      this.$nextTick(() => {
        const el = this.$refs.scroll;
        if (el) el.scrollTop = el.scrollHeight;
      });
    },
  },
};
</script>

<style scoped>
.erpa-root { display: flex; flex-direction: column; height: calc(100vh - 120px); max-width: 900px; margin: 0 auto; }
.erpa-messages { flex: 1; overflow-y: auto; padding: 16px; }
.erpa-empty { color: var(--text-muted); text-align: center; margin-top: 40px; }
.erpa-empty ul { list-style: none; padding: 0; margin-top: 16px; }
.erpa-empty li { display: inline-block; margin: 4px; padding: 6px 12px; border: 1px solid var(--border-color); border-radius: 16px; cursor: pointer; font-size: 13px; }
.erpa-empty li:hover { background: var(--fg-hover-color); }
.erpa-msg { margin: 12px 0; display: flex; flex-direction: column; }
.erpa-msg.user { align-items: flex-end; }
.erpa-msg.assistant { align-items: flex-start; }
.erpa-bubble { padding: 10px 14px; border-radius: 12px; max-width: 85%; line-height: 1.5; }
.erpa-msg.user .erpa-bubble { background: var(--primary); color: #fff; }
.erpa-msg.assistant .erpa-bubble { background: var(--fg-color, #f4f5f6); border: 1px solid var(--border-color); }
.erpa-bubble :deep(h2) { font-size: 15px; margin: 8px 0 4px; }
.erpa-bubble :deep(ol), .erpa-bubble :deep(ul) { padding-left: 20px; }
.erpa-bubble :deep(pre) { background: rgba(0,0,0,.06); padding: 8px; border-radius: 6px; overflow-x: auto; }
.erpa-cites { margin-top: 6px; font-size: 12px; }
.erpa-cites-label { color: var(--text-muted); margin-right: 4px; }
.erpa-chip { display: inline-block; padding: 2px 8px; margin: 2px; border-radius: 10px; font-size: 11px; }
.erpa-chip.custom { background: #e8f5e9; color: #256029; }
.erpa-chip.std { background: #eceff1; color: #455a64; }
.erpa-input { display: flex; gap: 8px; padding: 12px; border-top: 1px solid var(--border-color); }
.erpa-input textarea { flex: 1; resize: none; height: 44px; padding: 10px; border: 1px solid var(--border-color); border-radius: 8px; font-family: inherit; }
.erpa-input button { padding: 0 20px; border: none; border-radius: 8px; background: var(--primary); color: #fff; cursor: pointer; }
.erpa-input button:disabled { opacity: .5; cursor: not-allowed; }
.erpa-typing span { display: inline-block; width: 6px; height: 6px; margin: 0 2px; background: var(--text-muted); border-radius: 50%; animation: erpa-blink 1.2s infinite both; }
.erpa-typing span:nth-child(2) { animation-delay: .2s; }
.erpa-typing span:nth-child(3) { animation-delay: .4s; }
@keyframes erpa-blink { 0%, 80%, 100% { opacity: .2; } 40% { opacity: 1; } }
</style>
