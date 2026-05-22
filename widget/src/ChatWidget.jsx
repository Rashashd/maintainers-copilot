import React, { useState, useEffect, useRef } from 'react'

// Inline markdown: **bold**, *italic*, `code`, preserves newlines
function parseMarkdown(text) {
  if (!text) return null
  return text.split('\n').flatMap((line, li, arr) => {
    const parts = []
    const re = /\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`/g
    let last = 0, m, k = 0
    while ((m = re.exec(line)) !== null) {
      if (m.index > last) parts.push(line.slice(last, m.index))
      if (m[1] !== undefined)
        parts.push(<strong key={k++}>{m[1]}</strong>)
      else if (m[2] !== undefined)
        parts.push(<em key={k++}>{m[2]}</em>)
      else
        parts.push(
          <code key={k++} style={{
            background: 'rgba(0,0,0,0.07)', borderRadius: 3,
            padding: '1px 5px', fontSize: '0.87em', fontFamily: 'monospace',
          }}>{m[3]}</code>
        )
      last = m.index + m[0].length
    }
    if (last < line.length) parts.push(line.slice(last))
    const out = [<React.Fragment key={li}>{parts}</React.Fragment>]
    if (li < arr.length - 1) out.push(<br key={`br${li}`} />)
    return out
  })
}

export default function ChatWidget({ widgetId, apiUrl, slot = 0 }) {
  const [config, setConfig] = useState(null)
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [statusText, setStatusText] = useState('')
  const bottomRef = useRef(null)

  const sessionId = useRef(
    sessionStorage.getItem('cw_session') || crypto.randomUUID()
  )
  useEffect(() => {
    sessionStorage.setItem('cw_session', sessionId.current)
  }, [])

  useEffect(() => {
    if (!widgetId) return
    fetch(`${apiUrl}/widget/config/${widgetId}`)
      .then(r => r.ok ? r.json() : null)
      .then(cfg => { if (cfg) setConfig(cfg) })
      .catch(() => {})
  }, [widgetId, apiUrl])

  useEffect(() => {
    if (config && messages.length === 0) {
      setMessages([{ role: 'assistant', content: config.greeting }])
    }
  }, [config])

  useEffect(() => {
    window.parent.postMessage(
      { type: 'widget-resize', height: open ? 520 : 72, expanded: open, slot }, '*'
    )
  }, [open])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, statusText])

  const primary = config?.theme?.primary_color || '#2563eb'

  async function send() {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setLoading(true)
    setStatusText('Thinking…')

    // Placeholder assistant message to stream into
    setMessages(prev => [...prev, { role: 'assistant', content: '', streaming: true }])

    try {
      const resp = await fetch(`${apiUrl}/widget/${widgetId}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId.current }),
      })
      if (!resp.ok || !resp.body) throw new Error('stream error')

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const parts = buf.split('\n\n')
        buf = parts.pop()
        for (const part of parts) {
          if (!part.startsWith('data: ')) continue
          try {
            const ev = JSON.parse(part.slice(6))
            if (ev.type === 'token') {
              setStatusText('')
              setMessages(prev => {
                const copy = [...prev]
                const last = copy[copy.length - 1]
                if (last?.role === 'assistant')
                  copy[copy.length - 1] = { ...last, content: last.content + ev.text }
                return copy
              })
            } else if (ev.type === 'status') {
              setStatusText(ev.text)
            } else if (ev.type === 'done') {
              if (ev.session_id) sessionId.current = ev.session_id
              setMessages(prev => {
                const copy = [...prev]
                const last = copy[copy.length - 1]
                if (last?.role === 'assistant')
                  copy[copy.length - 1] = { ...last, streaming: false }
                return copy
              })
              setStatusText('')
            }
          } catch {}
        }
      }
    } catch {
      setMessages(prev => {
        const copy = [...prev]
        const last = copy[copy.length - 1]
        if (last?.role === 'assistant' && last.streaming)
          copy[copy.length - 1] = { role: 'assistant', content: 'Something went wrong. Please try again.' }
        else
          copy.push({ role: 'assistant', content: 'Something went wrong. Please try again.' })
        return copy
      })
      setStatusText('')
    } finally {
      setLoading(false)
    }
  }

  if (!config) return null

  if (!open) {
    return (
      <div style={{ position: 'fixed', bottom: 16, right: 16 }}>
        <button
          onClick={() => setOpen(true)}
          title={config.greeting}
          style={{
            width: 56, height: 56, borderRadius: '50%',
            background: primary, border: 'none', cursor: 'pointer',
            boxShadow: '0 4px 20px rgba(0,0,0,0.28)',
            fontSize: 24, color: '#fff',
            transition: 'transform 0.15s, box-shadow 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.transform = 'scale(1.08)' }}
          onMouseLeave={e => { e.currentTarget.style.transform = 'scale(1)' }}
        >
          💬
        </button>
      </div>
    )
  }

  return (
    <div style={{
      position: 'fixed', bottom: 0, right: 0,
      width: 370, height: 520,
      display: 'flex', flexDirection: 'column',
      borderRadius: '14px 14px 0 0',
      boxShadow: '0 -8px 40px rgba(0,0,0,0.18)',
      background: '#fff', overflow: 'hidden',
      border: '1px solid #e2e8f0',
      fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif',
    }}>

      {/* Header */}
      <div style={{
        background: `linear-gradient(135deg, ${primary}, ${primary}cc)`,
        color: '#fff', padding: '14px 16px',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        flexShrink: 0, borderBottom: '1px solid rgba(255,255,255,0.15)',
      }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 15, letterSpacing: '-0.2px' }}>
            {config.name}
          </div>
          <div style={{ fontSize: 11, opacity: 0.75, marginTop: 2, fontStyle: 'italic' }}>
            Powered by AI · Ask me anything
          </div>
        </div>
        <button
          onClick={() => setOpen(false)}
          style={{
            background: 'rgba(255,255,255,0.15)', border: 'none',
            color: '#fff', cursor: 'pointer', fontSize: 18,
            width: 28, height: 28, borderRadius: '50%',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            transition: 'background 0.15s',
          }}
          onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.25)' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'rgba(255,255,255,0.15)' }}
        >×</button>
      </div>

      {/* Messages */}
      <div style={{
        flex: 1, overflowY: 'auto', padding: '14px 12px 6px',
        display: 'flex', flexDirection: 'column', gap: 10,
        background: '#f8fafc',
      }}>
        {messages.map((m, i) => (
          <div key={i} style={{
            alignSelf: m.role === 'user' ? 'flex-end' : 'flex-start',
            maxWidth: '82%',
          }}>
            {m.role === 'assistant' && (
              <div style={{
                fontSize: 10, fontWeight: 600, color: '#94a3b8',
                marginBottom: 3, letterSpacing: '0.04em', textTransform: 'uppercase',
              }}>
                Assistant
              </div>
            )}
            <div style={{
              background: m.role === 'user' ? primary : '#fff',
              color: m.role === 'user' ? '#fff' : '#1e293b',
              borderRadius: m.role === 'user' ? '14px 14px 3px 14px' : '14px 14px 14px 3px',
              padding: '9px 13px',
              fontSize: 13.5, lineHeight: 1.6,
              boxShadow: m.role === 'user'
                ? `0 2px 8px ${primary}44`
                : '0 1px 4px rgba(0,0,0,0.08)',
              border: m.role === 'assistant' ? '1px solid #e2e8f0' : 'none',
            }}>
              {parseMarkdown(m.content)}
              {m.streaming && (
                <span style={{
                  display: 'inline-block', width: 2, height: '1em',
                  background: '#94a3b8', marginLeft: 2,
                  verticalAlign: 'text-bottom',
                  animation: 'blink 0.8s step-end infinite',
                }} />
              )}
            </div>
          </div>
        ))}

        {statusText && (
          <div style={{
            alignSelf: 'flex-start', color: '#94a3b8',
            fontSize: 12, fontStyle: 'italic',
            display: 'flex', alignItems: 'center', gap: 6, paddingLeft: 2,
          }}>
            <span style={{ animation: 'spin 1s linear infinite', display: 'inline-block' }}>⟳</span>
            {statusText}
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <div style={{
        borderTop: '1px solid #e2e8f0', display: 'flex',
        padding: '10px 10px', gap: 8, flexShrink: 0, background: '#fff',
      }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder="Ask a question…"
          disabled={loading}
          style={{
            flex: 1, border: '1.5px solid #e2e8f0', borderRadius: 10,
            padding: '8px 12px', fontSize: 13.5, outline: 'none',
            fontFamily: 'inherit', background: loading ? '#f8fafc' : '#fff',
            transition: 'border-color 0.15s',
            color: '#1e293b',
          }}
          onFocus={e => { e.target.style.borderColor = primary }}
          onBlur={e => { e.target.style.borderColor = '#e2e8f0' }}
        />
        <button
          onClick={send}
          disabled={loading || !input.trim()}
          style={{
            background: primary, color: '#fff', border: 'none',
            borderRadius: 10, padding: '8px 16px', cursor: 'pointer',
            fontSize: 13.5, fontWeight: 700,
            opacity: (loading || !input.trim()) ? 0.45 : 1,
            transition: 'opacity 0.15s, transform 0.1s',
            letterSpacing: '0.01em',
          }}
          onMouseEnter={e => { if (!loading && input.trim()) e.currentTarget.style.transform = 'scale(1.04)' }}
          onMouseLeave={e => { e.currentTarget.style.transform = 'scale(1)' }}
        >
          Send
        </button>
      </div>

      <style>{`
        @keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
        @keyframes spin  { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
      `}</style>
    </div>
  )
}
