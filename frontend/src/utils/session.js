const SESSION_KEY = 'changai_chat_id'
const CHAT_HISTORY_KEY = 'changai_chat_history'
const SUPPORT_HISTORY_KEY = 'changai_support_history'

export function getOrCreateChatId() {
  let chatId = sessionStorage.getItem(SESSION_KEY)
  if (!chatId) {
    chatId = `session_${Date.now()}_${crypto.randomUUID()}`
    sessionStorage.setItem(SESSION_KEY, chatId)
  }
  return chatId
}

// sessionStorage clears itself when the tab closes, so this is
// deliberately temporary — a reload/navigation within the same tab
// keeps the conversation, closing the tab starts fresh.
function loadHistory(key) {
  try {
    const raw = sessionStorage.getItem(key)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    // Drop any in-flight "Thinking..."/status bubble left over from a
    // request that was interrupted by the reload — it would otherwise
    // render as a permanently stuck loading message.
    return parsed.filter((msg) => !msg?.isStatus)
  } catch {
    return []
  }
}

function saveHistory(key, history) {
  try {
    sessionStorage.setItem(key, JSON.stringify(history))
  } catch {
    // sessionStorage full/unavailable — history just won't persist.
  }
}

export function loadChatHistory() {
  return loadHistory(CHAT_HISTORY_KEY)
}

export function saveChatHistory(history) {
  saveHistory(CHAT_HISTORY_KEY, history)
}

export function loadSupportHistory() {
  return loadHistory(SUPPORT_HISTORY_KEY)
}

export function saveSupportHistory(history) {
  saveHistory(SUPPORT_HISTORY_KEY, history)
}
