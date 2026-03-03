import { useEffect, useRef, useState, useCallback } from 'react'

const WS_URL = import.meta.env.VITE_WS_URL ?? 'ws://localhost:8000/ws/events'
const RECONNECT_DELAY_MS = 3000
const MAX_RECONNECT_ATTEMPTS = 10

export function useWebSocket(path, onMessage) {
  const wsRef            = useRef(null)
  const reconnectCount   = useRef(0)
  const reconnectTimeout = useRef(null)
  const [status, setStatus] = useState('connecting')   // connecting|open|closed|error

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const url = WS_URL.replace(/\/ws\/.*$/, '') + path
    const ws  = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setStatus('open')
      reconnectCount.current = 0
    }

    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data)
        onMessage(data)
      } catch (err) {
        console.warn('[WS] Failed to parse message', err)
      }
    }

    ws.onerror = () => setStatus('error')

    ws.onclose = () => {
      setStatus('closed')
      wsRef.current = null
      if (reconnectCount.current < MAX_RECONNECT_ATTEMPTS) {
        reconnectCount.current++
        reconnectTimeout.current = setTimeout(connect, RECONNECT_DELAY_MS)
      }
    }
  }, [path, onMessage])

  useEffect(() => {
    connect()
    return () => {
      clearTimeout(reconnectTimeout.current)
      wsRef.current?.close()
    }
  }, [connect])

  // Send a keepalive ping every 30s to prevent server timeout
  useEffect(() => {
    const interval = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30_000)
    return () => clearInterval(interval)
  }, [])

  return { status }
}
