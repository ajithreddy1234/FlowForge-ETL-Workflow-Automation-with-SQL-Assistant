import { useEffect, useState } from 'react'
import { Eye, EyeOff, CheckCircle, AlertTriangle, Save, Database } from 'lucide-react'
import { useStore } from '../../store'
import * as connectionApi from '../../services/connectionApi'
import { ApiError } from '../../services/apiClient'

export default function CredentialPanel({ node }) {
  const updateNodeData = useStore(s => s.updateNodeData)
  const d = node.data
  const [showPwd, setShowPwd] = useState(false)
  const [connections, setConnections] = useState([])
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState('')

  const isConfigured = !!(d.host && d.database && d.username)
  const isConnected = d.connectionStatus === 'connected'
  const connectionError = d.connectionStatus === 'error' ? d.connectionError : ''
  const dbType = d.db_type || 'mysql'
  const defaultPort = dbType === 'redshift' ? 5439 : dbType === 'postgresql' ? 5432 : 3306

  useEffect(() => {
    connectionApi.listConnections().then(setConnections).catch(() => {})
  }, [])

  const updateConnectionField = (changes) => {
    updateNodeData(node.id, {
      ...changes,
      connection_id: null,
      connection_name: '',
      connectionStatus: 'idle',
      connectionError: null,
      runStatus: 'idle',
      runError: null,
    })
  }

  const selectSavedConnection = (connectionId) => {
    if (!connectionId) {
      updateNodeData(node.id, {
        connection_id: null,
        connection_name: '',
        connectionStatus: 'idle',
      })
      return
    }
    const selected = connections.find(item => String(item.id) === String(connectionId))
    if (!selected) return
    updateNodeData(node.id, {
      connection_id: selected.id,
      connection_name: selected.name,
      label: selected.name,
      db_type: selected.db_type,
      host: selected.host,
      port: selected.port || '',
      database: selected.database,
      username: selected.username,
      password: '',
      connectionStatus: 'connected',
      connectionError: null,
    })
  }

  const saveConnection = async () => {
    setSaving(true)
    setSaveError('')
    try {
      const saved = await connectionApi.createConnection({
        name: (d.label || '').trim() || `${d.database} connection`,
        db_type: dbType,
        host: d.host,
        port: d.port || '',
        database: d.database,
        username: d.username,
        password: d.password || '',
        allowed_schemas: [],
      })
      setConnections(items => [saved, ...items.filter(item => item.id !== saved.id)])
      updateNodeData(node.id, {
        connection_id: saved.id,
        connection_name: saved.name,
        label: saved.name,
        password: '',
        connectionStatus: 'connected',
        connectionError: null,
      })
    } catch (error) {
      setSaveError(error instanceof ApiError ? error.message : 'Could not save connection')
    } finally {
      setSaving(false)
    }
  }

  if (import.meta.env.VITE_PUBLIC_DEMO === 'true') return <div className="p-4 space-y-4"><SectionHeader title="Synthetic orders" subtitle="Read-only sandbox connection" /><StatusBox tone="success" icon={CheckCircle}>Connected to synthetic_orders</StatusBox><InfoBox>Use the orders table: order_id, order_date, region, category, amount, status. This public sandbox cannot connect to external databases.</InfoBox><button className="void-focus rounded-lg bg-accent px-4 py-2 text-sm" onClick={() => updateNodeData(node.id, { connection_id: 1, connectionStatus: 'connected', host: 'sandbox', database: 'synthetic_orders', username: 'demo' })}>Use synthetic orders</button></div>

  return (
    <div className="p-4 space-y-4">
      <SectionHeader title="Credential" subtitle="Database connection settings" />

      <Field label="Saved Connection" hint="Saved passwords stay encrypted on the server and are never returned to this browser.">
        <select
          className="void-focus w-full rounded-lg px-3 py-2 text-sm outline-none"
          style={inputStyle}
          value={d.connection_id || ''}
          onChange={event => selectSavedConnection(event.target.value)}
        >
          <option value="">Create a new connection…</option>
          {connections.map(connection => (
            <option key={connection.id} value={connection.id}>
              {connection.name} · {connection.db_type}
            </option>
          ))}
        </select>
      </Field>

      {isConnected ? (
        <StatusBox tone="success" icon={CheckCircle}>Database connection verified</StatusBox>
      ) : connectionError ? (
        <StatusBox tone="error" icon={AlertTriangle}>{connectionError}</StatusBox>
      ) : isConfigured && (
        <StatusBox tone="warning" icon={AlertTriangle}>Check the DB connection before previewing or running.</StatusBox>
      )}

      <Field label="Node Label">
        <TextInput
          value={d.label || ''}
          onChange={v => updateNodeData(node.id, { label: v })}
          placeholder="My DB credentials"
        />
      </Field>

      <div className="border-t border-white/[0.07] pt-3">
        <p className="mb-3 text-xs font-semibold text-white/70">Database Connection</p>

        <div className="space-y-3">
          <Field label="Database Type" required>
            <select
              className="void-focus w-full rounded-lg px-3 py-2 text-sm outline-none transition-colors"
              style={inputStyle}
              value={dbType}
              onChange={e => updateConnectionField({
                db_type: e.target.value,
                port: e.target.value === 'redshift' ? '5439' : e.target.value === 'postgresql' ? '5432' : '3306',
              })}
            >
              <option value="mysql">MySQL</option>
              <option value="postgresql">PostgreSQL</option>
              <option value="redshift">Amazon Redshift</option>
            </select>
          </Field>

          <div className="flex gap-2">
            <div className="flex-1">
              <Field label="Host" required>
                <TextInput
                  value={d.host || ''}
                  onChange={v => updateConnectionField({ host: v })}
                  placeholder="localhost"
                />
              </Field>
            </div>
            <div style={{ width: 80 }}>
              <Field label="Port">
                <TextInput
                  value={d.port || ''}
                  onChange={v => updateConnectionField({ port: v })}
                  placeholder={String(defaultPort)}
                  type="number"
                />
              </Field>
            </div>
          </div>

          <Field label="Database Name" required>
            <TextInput
              value={d.database || ''}
              onChange={v => updateConnectionField({ database: v })}
              placeholder="sales_db"
            />
          </Field>

          <Field label="Username" required>
            <TextInput
              value={d.username || ''}
              onChange={v => updateConnectionField({ username: v })}
              placeholder={dbType === 'redshift' ? 'awsuser' : 'mysql_user'}
            />
          </Field>

          <Field label="Password">
            <div style={{ position: 'relative' }}>
              <input
                type={showPwd ? 'text' : 'password'}
                className="void-focus w-full rounded-lg text-sm outline-none"
                style={{ ...inputStyle, padding: '8px 36px 8px 12px' }}
                value={d.password || ''}
                onChange={e => updateConnectionField({ password: e.target.value })}
                placeholder="Password"
              />
              <button
                type="button"
                onClick={() => setShowPwd(v => !v)}
                aria-label={showPwd ? 'Hide password' : 'Show password'}
                style={{
                  position: 'absolute', right: 8, top: '50%',
                  transform: 'translateY(-50%)',
                  background: 'none', border: 'none',
                  cursor: 'pointer', color: 'rgba(255,255,255,0.35)', padding: 0,
                  display: 'flex', alignItems: 'center',
                }}
              >
                {showPwd ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
          </Field>
        </div>
      </div>

      {isConnected && (
        <div className="space-y-1 rounded-lg p-3" style={{ background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.25)' }}>
          <p className="text-xs font-semibold text-accent-light">Connection summary</p>
          <p className="font-mono text-xs text-accent-light/80">
            {dbType}://{d.username}@{d.host}:{d.port || defaultPort}/{d.database}
          </p>
        </div>
      )}

      {isConnected && !d.connection_id && (
        <button
          type="button"
          onClick={saveConnection}
          disabled={saving}
          className="void-focus flex w-full items-center justify-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-white hover:bg-accent-hover disabled:opacity-50"
        >
          {saving ? <Database size={14} className="animate-pulse" /> : <Save size={14} />}
          {saving ? 'Saving securely…' : 'Save Connection Securely'}
        </button>
      )}

      {d.connection_id && (
        <StatusBox tone="info" icon={Database}>
          Server-side connection #{d.connection_id}. This pipeline can run without storing a password in the canvas.
        </StatusBox>
      )}

      {saveError && <StatusBox tone="error" icon={AlertTriangle}>{saveError}</StatusBox>}

      <InfoBox>
        Select PostgreSQL, MySQL, or Redshift and fill in the connection fields. Use the Preview panel to check the connection.
      </InfoBox>
    </div>
  )
}

export const inputStyle = {
  background: 'rgba(255,255,255,0.04)',
  border: '1px solid rgba(255,255,255,0.12)',
  color: '#ffffff',
}

const TONE = {
  success: { bg: 'rgba(16,185,129,0.08)', border: 'rgba(16,185,129,0.25)', text: '#34d399' },
  error: { bg: 'rgba(239,68,68,0.08)', border: 'rgba(239,68,68,0.25)', text: '#f87171' },
  warning: { bg: 'rgba(245,158,11,0.08)', border: 'rgba(245,158,11,0.25)', text: '#fbbf24' },
  info: { bg: 'rgba(139,92,246,0.08)', border: 'rgba(139,92,246,0.25)', text: '#A78BFA' },
}

export function StatusBox({ tone = 'info', icon: Icon, children }) {
  const t = TONE[tone]
  return (
    <div className="flex items-start gap-2 rounded-lg p-2.5" style={{ background: t.bg, border: `1px solid ${t.border}` }}>
      {Icon && <Icon size={13} style={{ color: t.text, marginTop: 1, flexShrink: 0 }} aria-hidden="true" />}
      <span className="text-xs font-medium" style={{ color: t.text }}>{children}</span>
    </div>
  )
}

export function SectionHeader({ title, subtitle }) {
  return (
    <div className="border-b border-white/[0.07] pb-3">
      <p className="text-sm font-bold text-white">{title}</p>
      {subtitle && <p className="mt-0.5 text-xs text-white/40">{subtitle}</p>}
    </div>
  )
}

export function Field({ label, hint, required, children }) {
  return (
    <div className="space-y-1">
      <label className="text-xs font-medium text-white/60">
        {label}
        {required && <span style={{ color: '#f87171', marginLeft: 2 }}>*</span>}
      </label>
      {children}
      {hint && <p className="text-xs text-white/35">{hint}</p>}
    </div>
  )
}

export function TextInput({ value, onChange, mono = false, style, ...rest }) {
  return (
    <input
      className={`void-focus w-full rounded-lg px-3 py-2 text-sm outline-none transition-colors ${mono ? 'font-mono text-xs' : ''}`}
      style={{ ...inputStyle, ...style }}
      value={value ?? ''}
      onChange={e => onChange(e.target.value)}
      {...rest}
    />
  )
}

export function InfoBox({ children }) {
  return (
    <div className="rounded-lg p-3 text-xs leading-relaxed text-white/45" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.07)' }}>
      {children}
    </div>
  )
}
