import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle } from 'lucide-react'
import { useStore } from '../../store'
import * as connectionApi from '../../services/connectionApi'
import { SectionHeader, Field, TextInput, InfoBox, StatusBox } from './CredentialPanel'
import SqlAssistantPanel from './SqlAssistantPanel'

export default function ExtractPanel({ node }) {
  const updateNodeData         = useStore(s => s.updateNodeData)
  const getConnectedCredential = useStore(s => s.getConnectedCredential)
  const d = node.data
  const [catalogTables, setCatalogTables] = useState([])
  const [catalogBusy, setCatalogBusy] = useState(false)
  const [catalogError, setCatalogError] = useState('')

  const credential   = getConnectedCredential(node.id)
  const hasCredential = !!credential
  const credReady     = hasCredential && credential.data?.connectionStatus === 'connected'
  const sourceMode = d.source_mode || 'query'
  const sqlMissing = !(sourceMode === 'table' ? d.table_name : d.sql || '').trim()
  const connectionId = credential?.data?.connection_id

  useEffect(() => {
    setCatalogTables([])
    if (!connectionId) return
    let active = true
    connectionApi.getCatalog(connectionId)
      .then(catalog => { if (active) setCatalogTables(catalog.tables || []) })
      .catch(() => {})
    return () => { active = false }
  }, [connectionId])

  const scanTables = async () => {
    if (!connectionId) return
    setCatalogBusy(true)
    setCatalogError('')
    try {
      const catalog = await connectionApi.syncCatalog(connectionId)
      setCatalogTables(catalog.tables || [])
    } catch (error) {
      setCatalogError(error?.message || 'Could not scan tables')
    } finally {
      setCatalogBusy(false)
    }
  }

  return (
    <div className="p-4 space-y-4">
      <SectionHeader title="Extract" subtitle="Select a table or run a read-only SQL query" />

      {!hasCredential ? (
        <StatusBox tone="warning" icon={AlertTriangle}>
          <span className="block font-semibold">No Credential connected</span>
          <span className="mt-0.5 block font-normal opacity-90">
            Drag a Credential node onto the canvas, configure it, then connect its right handle to this node's left handle.
          </span>
        </StatusBox>
      ) : !credReady ? (
        <StatusBox tone="warning" icon={AlertTriangle}>
          <span className="block font-semibold">Credential incomplete</span>
          <span className="mt-0.5 block font-normal opacity-90">
            Open the connected Credential node and click Check Connection.
          </span>
        </StatusBox>
      ) : (
        <StatusBox tone="success" icon={CheckCircle}>
          Using: {credential.data.username}@{credential.data.host}/{credential.data.database}
        </StatusBox>
      )}

      <Field label="Node Label" hint="A short name to identify this step">
        <TextInput
          value={d.label || ''}
          onChange={v => updateNodeData(node.id, { label: v })}
          placeholder="e.g. Raw Sales Data"
        />
      </Field>

      <Field label="Query Date" hint="Use :date or {date} in SQL to apply this selected value.">
        <TextInput
          type="date"
          value={d.query_date || ''}
          onChange={v => updateNodeData(node.id, { query_date: v })}
        />
      </Field>

      <Field label="Source Mode">
        <select className="void-focus w-full rounded-lg px-3 py-2 text-sm outline-none" value={sourceMode}
          onChange={e => updateNodeData(node.id, { source_mode: e.target.value })}>
          <option value="query">Custom query</option>
          <option value="table">Selected table</option>
        </select>
      </Field>

      {sourceMode === 'table' ? (
        <Field label="Table" hint="Enter table or schema.table." required>
          {connectionId && <div className="mb-2 flex gap-2">
            <select className="void-focus min-w-0 flex-1 rounded-lg px-3 py-2 text-sm outline-none"
              value={catalogTables.some(t => `${t.schema}.${t.name}` === d.table_name) ? d.table_name : ''}
              onChange={e => updateNodeData(node.id, { table_name: e.target.value })}>
              <option value="">Select a scanned table…</option>
              {catalogTables.filter(t => /^[A-Za-z_][A-Za-z0-9_]*$/.test(t.schema) && /^[A-Za-z_][A-Za-z0-9_]*$/.test(t.name))
                .map(t => <option key={`${t.schema}.${t.name}`} value={`${t.schema}.${t.name}`}>{t.schema}.{t.name}</option>)}
            </select>
            <button type="button" onClick={scanTables} disabled={catalogBusy}
              className="void-focus rounded-lg border border-white/10 px-3 text-xs text-white/70 disabled:opacity-40">
              {catalogBusy ? 'Scanning…' : 'Scan'}
            </button>
          </div>}
          <TextInput value={d.table_name || ''} onChange={v => updateNodeData(node.id, { table_name: v })}
            placeholder="public.orders" mono />
          {catalogError && <p className="mt-1 text-xs text-red-300">{catalogError}</p>}
        </Field>
      ) : <>
        {import.meta.env.VITE_PUBLIC_DEMO !== 'true' && <SqlAssistantPanel credential={credential} onUseSql={sql => updateNodeData(node.id, { sql })} />}

      <Field label="SQL Query" required>
        <textarea
          rows={9}
          className="void-focus w-full resize-none rounded-lg px-3 py-2 font-mono text-xs leading-relaxed outline-none"
          style={{
            background: hasCredential ? 'rgba(139,92,246,0.06)' : 'rgba(255,255,255,0.02)',
            border: `1px solid ${sqlMissing ? 'rgba(239,68,68,0.4)' : (hasCredential ? 'rgba(139,92,246,0.25)' : 'rgba(255,255,255,0.1)')}`,
            color: hasCredential ? '#e9e4ff' : 'rgba(255,255,255,0.3)',
          }}
          placeholder={hasCredential
            ? "SELECT *\nFROM sale_distribution_detail\nWHERE DATE(created_date) = :date"
            : "Connect a Credential node first…"
          }
          value={d.sql || ''}
          onChange={e => updateNodeData(node.id, { sql: e.target.value })}
          disabled={!hasCredential}
        />
        {sqlMissing && (
          <StatusBox tone="error" icon={AlertTriangle}>
            SQL query is required before previewing or running this Extract node.
          </StatusBox>
        )}
      </Field>
      </>}

      <Field label="Expected Columns" hint="Comma-separated column names. Missing columns stop the run before loading.">
        <TextInput value={(d.expected_columns || []).join(', ')}
          onChange={v => updateNodeData(node.id, { expected_columns: v.split(',').map(s => s.trim()).filter(Boolean) })}
          placeholder="id, created_at, amount" mono />
      </Field>

      <Field label="Incremental Extraction" hint="Checkpoints are stored per saved schedule after all Load nodes succeed.">
        <select className="void-focus w-full rounded-lg px-3 py-2 text-sm outline-none"
          value={d.incremental_mode || 'none'}
          onChange={e => updateNodeData(node.id, { incremental_mode: e.target.value })}>
          <option value="none">Full extract</option>
          <option value="primary_key">Integer primary key</option>
          <option value="timestamp">Unique timestamp</option>
        </select>
      </Field>
      {(d.incremental_mode || 'none') !== 'none' && (
        <Field label="Checkpoint Column" hint="This column must be present in the result and increase for every new row.">
          <TextInput value={d.checkpoint_column || ''}
            onChange={v => updateNodeData(node.id, { checkpoint_column: v })}
            placeholder={d.incremental_mode === 'timestamp' ? 'updated_at' : 'id'} mono />
        </Field>
      )}

      <InfoBox>
        {hasCredential
          ? 'Queries must be read-only. Incremental runs require a saved schedule and an append-mode Sheet sink.'
          : 'You must connect a Credential node before writing SQL or previewing data.'
        }
      </InfoBox>
    </div>
  )
}
