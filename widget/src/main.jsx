import React from 'react'
import ReactDOM from 'react-dom/client'
import ChatWidget from './ChatWidget'

const params = new URLSearchParams(window.location.search)
const widgetId = params.get('widget_id')
const apiUrl = params.get('api') || 'http://localhost:8000'
const slot = parseInt(params.get('slot') || '0', 10)

if (!widgetId) {
  window.location.replace('/demo.html' + window.location.search)
} else {
  ReactDOM.createRoot(document.getElementById('root')).render(
    <ChatWidget widgetId={widgetId} apiUrl={apiUrl} slot={slot} />
  )
}
