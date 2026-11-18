import { useStore } from '../../store'
import { useUpstreamColumns, useRightUpstreamColumns } from '../../hooks/useUpstreamColumns'
import {
  SINGLE_OPS, TWO_TABLE_OPS, OP_DESC,
  AGG_FUNCTIONS, JOIN_TYPES, CAST_TYPES, FILTER_OPS, DATE_PARTS,
} from '../../constants'
import { SectionHeader, Field, TextInput, inputStyle } from './CredentialPanel'

// ── Shared micro-components ───────────────────────────────────────────────────

function Sel({ value, onChange, options, placeholder }) {
  return (
    <select
      className="w-full text-sm rounded-lg px-3 py-2 outline-none"
      style={inputStyle}
      value={value ?? ''}
      onChange={e => onChange(e.target.value)}
    >
      {placeholder && <option value="">{placeholder}</option>}
      {options.map(o =>
        typeof o === 'string'
          ? <option key={o} value={o}>{o}</option>
          : <option key={o.value} value={o.value}>{o.label}</option>
      )}
    </select>
  )
}

function ColSel({ value, onChange, columns, placeholder = 'Select column…' }) {
  return (
    <select
      className="w-full text-sm rounded-lg px-3 py-2 outline-none"
      style={inputStyle}
      value={value ?? ''}
      onChange={e => onChange(e.target.value)}
    >
      <option value="">{placeholder}</option>
      {columns.map(c => <option key={c} value={c}>{c}</option>)}
    </select>
  )
}

function ColChecks({ value = [], onChange, columns, emptyMsg }) {
  if (columns.length === 0) {
    return (
      <p className="text-xs py-1" style={{ color: 'rgba(255,255,255,0.35)' }}>
        {emptyMsg || 'Connect an upstream node first to see columns.'}
      </p>
    )
  }
  return (
    <div
      className="rounded-lg border overflow-y-auto"
      style={{ maxHeight: 140, background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.12)' }}
    >
      {columns.map(c => (
        <label
          key={c}
          className="flex items-center gap-2.5 px-3 py-1.5 hover:bg-white/5 cursor-pointer select-none"
          style={{ borderBottom: '1px solid rgba(255,255,255,0.06)' }}
        >
          <input
            type="checkbox"
            className="accent-[#8B5CF6] w-3.5 h-3.5"
            checked={value.includes(c)}
            onChange={e =>
              e.target.checked
                ? onChange([...value, c])
                : onChange(value.filter(v => v !== c))
            }
          />
          <span className="text-xs font-mono" style={{ color: 'rgba(255,255,255,0.7)' }}>{c}</span>
        </label>
      ))}
    </div>
  )
}

// ── Pair editors ──────────────────────────────────────────────────────────────

function PairEditor({ pairs, onChange, leftCols, lPlaceholder = 'key', rPlaceholder = 'value' }) {
  const entries = Object.entries(pairs)

  const update = (i, k, v) =>
    onChange(Object.fromEntries(entries.map(([ek, ev], j) => j === i ? [k, v] : [ek, ev])))

  const remove = (i) =>
    onChange(Object.fromEntries(entries.filter((_, j) => j !== i)))

  return (
    <div className="space-y-1.5">
      {entries.map(([k, v], i) => (
        <div key={i} className="flex items-center gap-1.5">
          {leftCols
            ? <select className="flex-1 text-xs rounded-lg px-2 py-1.5 outline-none" style={inputStyle}
                value={k} onChange={e => update(i, e.target.value, v)}>
                <option value="">{lPlaceholder}…</option>
                {leftCols.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            : <input className="flex-1 text-xs rounded-lg px-2 py-1.5 outline-none" style={inputStyle}
                value={k} placeholder={lPlaceholder} onChange={e => update(i, e.target.value, v)} />
          }
          <span className="text-white/30 text-xs shrink-0">→</span>
          <input className="flex-1 text-xs rounded-lg px-2 py-1.5 outline-none" style={inputStyle}
            value={v} placeholder={rPlaceholder} onChange={e => update(i, k, e.target.value)} />
          <button className="text-xs shrink-0 px-1 rounded hover:bg-red-500/10"
            style={{ color: '#f87171' }} onClick={() => remove(i)}>×</button>
        </div>
      ))}
      <button
        className="text-xs font-medium px-2 py-1 rounded-md transition-colors hover:bg-white/5"
        style={{ color: '#A78BFA' }}
        onClick={() => onChange({ ...pairs, '': '' })}
      >
        + Add pair
      </button>
    </div>
  )
}

// ── Aggregation editor ────────────────────────────────────────────────────────
// Uses an array of {id, col, func} internally to allow multiple entries per column.

function AggEditor({ aggs, onChange, columns }) {
  // Convert dict → array on every render (stable with ids via index)
  const rows = Object.entries(aggs)

  const update = (i, col, func) => {
    const next = [...rows]
    next[i] = [col, func]
    onChange(Object.fromEntries(next))
  }

  const remove = (i) => {
    const next = rows.filter((_, j) => j !== i)
    onChange(Object.fromEntries(next))
  }

  const addRow = () => {
    // Use a unique placeholder to avoid collapsing with existing empty keys
    const placeholder = `__new${rows.length}_${Date.now()}`
    onChange({ ...aggs, [placeholder]: 'sum' })
  }

  return (
    <div className="space-y-1.5">
      {rows.length === 0 && (
        <p className="text-xs" style={{ color: 'rgba(255,255,255,0.35)' }}>No aggregations added yet.</p>
      )}
      {rows.map(([col, func], i) => {
        const isPlaceholder = col.startsWith('__new')
        return (
          <div key={i} className="flex items-center gap-1.5">
            <select className="flex-1 text-xs rounded-lg px-2 py-1.5 outline-none" style={inputStyle}
              value={isPlaceholder ? '' : col}
              onChange={e => update(i, e.target.value, func)}>
              <option value="">column…</option>
              {columns.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
            <span className="text-white/30 text-xs shrink-0">→</span>
            <select className="flex-1 text-xs rounded-lg px-2 py-1.5 outline-none" style={inputStyle}
              value={func} onChange={e => update(i, col, e.target.value)}>
              {AGG_FUNCTIONS.map(f => <option key={f} value={f}>{f}</option>)}
            </select>
            <button className="text-xs shrink-0 px-1 rounded hover:bg-red-500/10"
              style={{ color: '#f87171' }} onClick={() => remove(i)}>×</button>
          </div>
        )
      })}
      <button
        className="text-xs font-medium px-2 py-1 rounded-md transition-colors hover:bg-white/5"
        style={{ color: '#A78BFA' }}
        onClick={addRow}
      >
        + Add aggregation
      </button>
    </div>
  )
}

// ── Operation-specific field sets ─────────────────────────────────────────────

function OperationFields({ op, setOp, columns, rightColumns }) {
  const t   = op?.type || ''
  const upd = patch => setOp({ ...op, type: t, ...patch })

  switch (t) {

    case 'rename':
      return (
        <>
          <p className="text-xs leading-relaxed" style={{ color: 'rgba(255,255,255,0.45)' }}>
            Rename columns by mapping old name → new name.
          </p>
          <Field label="Column Rename Pairs">
            <PairEditor
              pairs={op?.mapping || {}}
              onChange={m => upd({ mapping: m })}
              leftCols={columns}
              lPlaceholder="old column name"
              rPlaceholder="new name"
            />
          </Field>
        </>
      )

    case 'select_columns':
    case 'drop_columns':
      return (
        <Field label={t === 'select_columns' ? 'Columns to keep' : 'Columns to remove'}>
          <ColChecks value={op?.columns || []} onChange={v => upd({ columns: v })} columns={columns} />
        </Field>
      )

    case 'sort':
      return (
        <>
          <Field label="Sort by these columns">
            <ColChecks value={op?.by || []} onChange={v => upd({ by: v })} columns={columns} />
          </Field>
          <label className="flex items-center gap-2 text-sm cursor-pointer" style={{ color: 'rgba(255,255,255,0.7)' }}>
            <input type="checkbox" className="accent-[#8B5CF6]"
              checked={op?.ascending !== false}
              onChange={e => upd({ ascending: e.target.checked })} />
            Ascending order (A → Z, lowest → highest)
          </label>
        </>
      )

    case 'calculate':
      return (
        <>
          <Field label="New Column Name" hint="The name for your new column">
            <TextInput mono value={op?.target} onChange={v => upd({ target: v })} placeholder="result_column" />
          </Field>
          <Field label="Formula" hint="Use column names directly, e.g: price * quantity  or  1 - delivered">
            <TextInput mono value={op?.expression} onChange={v => upd({ expression: v })} placeholder="col_a * col_b" />
          </Field>
          <Field label="Fill empty results with">
            <TextInput value={op?.fillna ?? ''} onChange={v => upd({ fillna: v === '' ? undefined : Number(v) })} placeholder="0" type="number" />
          </Field>
        </>
      )

    case 'filter':
      return (
        <>
          <Field label="Column to filter on">
            <ColSel value={op?.column} onChange={v => upd({ column: v })} columns={columns} />
          </Field>
          <Field label="Condition">
            <Sel value={op?.operator} onChange={v => upd({ operator: v })} options={FILTER_OPS} placeholder="Select…" />
          </Field>
          <Field label="Value" hint="For 'in / not in', separate values with commas: a,b,c">
            <TextInput value={op?.value} onChange={v => upd({ value: v })} placeholder="e.g. 100" />
          </Field>
        </>
      )

    case 'fillna':
      return (
        <>
          <Field label="Column with empty values">
            <ColSel
              value={op?.columns?.[0] || ''}
              onChange={v => upd({ columns: v ? [v] : [] })}
              columns={columns}
            />
          </Field>
          <Field label="Replace empty cells with">
            <TextInput value={op?.value} onChange={v => upd({ value: v })} placeholder="0" />
          </Field>
        </>
      )

    case 'replace':
      return (
        <>
          <Field label="Column">
            <ColSel value={op?.column} onChange={v => upd({ column: v })} columns={columns} />
          </Field>
          <Field label="Find this value">
            <TextInput value={op?.to_replace} onChange={v => upd({ to_replace: v })} placeholder="old value" />
          </Field>
          <Field label="Replace with">
            <TextInput value={op?.value} onChange={v => upd({ value: v })} placeholder="new value" />
          </Field>
        </>
      )

    case 'map':
      return (
        <>
          <Field label="Column to map">
            <ColSel value={op?.column} onChange={v => upd({ column: v })} columns={columns} />
          </Field>
          <Field label="Value mapping  (old → new)">
            <PairEditor
              pairs={op?.mapping || {}}
              onChange={m => upd({ mapping: m })}
              lPlaceholder="old value"
              rPlaceholder="new value"
            />
          </Field>
        </>
      )

    // abs takes a LIST of columns
    case 'abs':
      return (
        <Field label="Columns to apply absolute value">
          <ColChecks value={op?.columns || []} onChange={v => upd({ columns: v })} columns={columns} />
        </Field>
      )

    case 'cumsum':
      return (
        <>
          <Field label="Column to accumulate">
            <ColSel value={op?.column} onChange={v => upd({ column: v })} columns={columns} />
          </Field>
          <Field label="Output column name" hint="Defaults to '<column> Cumulative'">
            <TextInput mono value={op?.output_column ?? ''} onChange={v => upd({ output_column: v || undefined })} placeholder="Running Total" />
          </Field>
          <Field label="Sort by before accumulating (optional)">
            <ColSel value={op?.sort_by ?? ''} onChange={v => upd({ sort_by: v || undefined })} columns={columns} placeholder="No sort" />
          </Field>
          <label className="flex items-center gap-2 text-sm cursor-pointer" style={{ color: 'rgba(255,255,255,0.7)' }}>
            <input type="checkbox" className="accent-[#8B5CF6]"
              checked={op?.ascending !== false}
              onChange={e => upd({ ascending: e.target.checked })} />
            Sort ascending
          </label>
        </>
      )

    case 'pct_of_total':
      return (
        <>
          <Field label="Column to compute % of">
            <ColSel value={op?.column} onChange={v => upd({ column: v })} columns={columns} />
          </Field>
          <Field label="Output column name" hint="Defaults to '<column> %'">
            <TextInput mono value={op?.output_column ?? ''} onChange={v => upd({ output_column: v || undefined })} placeholder="Share %" />
          </Field>
          <Field label="Group by (optional — % will be within each group)">
            <ColChecks value={op?.group_by || []} onChange={v => upd({ group_by: v.length ? v : undefined })} columns={columns} />
          </Field>
          <Field label="Decimal places">
            <TextInput type="number" value={op?.decimals ?? 1} onChange={v => upd({ decimals: Number(v) })} placeholder="1" />
          </Field>
        </>
      )

    // add_total_column: label = new column name, exclude_columns = skip these from sum
    case 'add_total_column':
      return (
        <>
          <div className="rounded-lg p-3 text-xs" style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.25)', color: '#34d399' }}>
            Sums all numeric columns row-by-row and writes the total into a new column.
            Non-numeric columns are skipped automatically; use "Exclude" to also skip specific numeric ones.
          </div>
          <Field label="New column name" hint="Name for the row-total column">
            <TextInput value={op?.label ?? 'Total'} onChange={v => upd({ label: v })} placeholder="Total" />
          </Field>
          <Field label="Exclude these columns from the sum" hint="Non-numeric columns are always excluded automatically">
            <ColChecks value={op?.exclude_columns || []} onChange={v => upd({ exclude_columns: v })} columns={columns} />
          </Field>
        </>
      )

    // add_total_row: appends a summary row at the bottom
    case 'add_total_row':
      return (
        <>
          <div className="rounded-lg p-3 text-xs" style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.25)', color: '#34d399' }}>
            Appends one summary row at the bottom of the table. Each numeric column gets
            its column total; you choose which column shows the label text.
          </div>
          <Field label="Label column" hint="This column will show the label text (e.g. 'Total')">
            <ColSel
              value={op?.label_column ?? ''}
              onChange={v => upd({ label_column: v || undefined })}
              columns={columns}
              placeholder="None"
            />
          </Field>
          <Field label="Label text">
            <TextInput
              value={op?.label ?? 'Total'}
              onChange={v => upd({ label: v })}
              placeholder="Total"
            />
          </Field>
          <Field label="Columns to sum" hint="Leave all unchecked to sum every numeric column">
            <ColChecks
              value={op?.columns || []}
              onChange={v => upd({ columns: v })}
              columns={columns}
            />
          </Field>
        </>
      )

    case 'astype':
      return (
        <>
          <Field label="Column">
            <ColSel value={op?.column} onChange={v => upd({ column: v })} columns={columns} />
          </Field>
          <Field label="Convert to type">
            <Sel value={op?.dtype} onChange={v => upd({ dtype: v })} options={CAST_TYPES} placeholder="Select type…" />
          </Field>
        </>
      )

    case 'drop_duplicates':
      return (
        <Field label="Check these columns for duplicates" hint="Leave all unchecked to check every column">
          <ColChecks value={op?.subset || []} onChange={v => upd({ subset: v })} columns={columns} />
        </Field>
      )

    case 'groupby':
      return (
        <>
          <div className="rounded-lg p-3 text-xs space-y-2" style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.25)' }}>
            <p className="font-semibold" style={{ color: '#fbbf24' }}>How Group By works:</p>
            <div className="space-y-1" style={{ color: 'rgba(251,191,36,0.85)' }}>
              <p>1. Rows sharing the same value(s) in the "Group by" columns collapse into one row.</p>
              <p>2. For each group, calculate a summary (sum, count, mean…) for other columns.</p>
            </div>
          </div>

          <Field label="Step 1 — Group by these columns">
            <ColChecks value={op?.group_by || []} onChange={v => upd({ group_by: v })} columns={columns} />
          </Field>

          <Field
            label="Step 2 — For each group, calculate:"
            hint="Column → function (sum=total, count=rows, mean=average)"
          >
            <AggEditor aggs={op?.aggregations || {}} onChange={a => upd({ aggregations: a })} columns={columns} />
          </Field>
        </>
      )

    case 'pivot':
      return (
        <>
          <Field label="Index column(s)" hint="Becomes the row labels — select one or more">
            <ColChecks value={Array.isArray(op?.index) ? op.index : (op?.index ? [op.index] : [])}
              onChange={v => upd({ index: v })} columns={columns} />
          </Field>
          <Field label="Columns column" hint="Unique values in this column become new headers">
            <ColSel value={op?.columns} onChange={v => upd({ columns: v })} columns={columns} />
          </Field>
          <Field label="Values column" hint="Numbers to fill the pivot table">
            <ColSel value={op?.values} onChange={v => upd({ values: v })} columns={columns} />
          </Field>
          <Field label="Aggregation function">
            <Sel value={op?.aggfunc || 'sum'} onChange={v => upd({ aggfunc: v })} options={AGG_FUNCTIONS} />
          </Field>
          <div className="rounded-lg p-2.5 text-xs" style={{ background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)', color: 'rgba(255,255,255,0.45)' }}>
            Tip: to add a totals row after pivoting, connect this node's output to an <strong>Add Total Row</strong> transform.
          </div>
        </>
      )

    // format_date takes a LIST of columns
    case 'format_date':
      return (
        <>
          <Field label="Date column(s)" hint="Select one or more columns to reformat">
            <ColChecks value={op?.columns || []} onChange={v => upd({ columns: v })} columns={columns} />
          </Field>
          <Field label="Output format" hint="Python strftime — e.g. %d %b %Y → 27 Jan 2022">
            <TextInput mono value={op?.format} onChange={v => upd({ format: v })} placeholder="%Y-%m-%d" />
          </Field>
        </>
      )

    case 'date_extract':
      return (
        <>
          <Field label="Date column">
            <ColSel value={op?.column} onChange={v => upd({ column: v })} columns={columns} />
          </Field>
          <Field label="Part to extract">
            <Sel value={op?.parts?.[0] || ''} onChange={v => upd({ parts: v ? [v] : [] })} options={DATE_PARTS} placeholder="Select part…" />
          </Field>
          <Field label="New column name">
            <TextInput mono value={op?.output_columns?.[0] || ''} onChange={v => upd({ output_columns: v ? [v] : [] })} placeholder="year_col" />
          </Field>
        </>
      )

    case 'rank':
      return (
        <>
          <Field label="Rank this column">
            <ColSel value={op?.rank_by} onChange={v => upd({ rank_by: v })} columns={columns} />
          </Field>
          <Field label="Store rank in new column">
            <TextInput mono value={op?.output_column} onChange={v => upd({ output_column: v })} placeholder="rank" />
          </Field>
          <label className="flex items-center gap-2 text-sm cursor-pointer" style={{ color: 'rgba(255,255,255,0.7)' }}>
            <input type="checkbox" className="accent-[#8B5CF6]"
              checked={op?.ascending !== false}
              onChange={e => upd({ ascending: e.target.checked })} />
            Rank 1 = lowest value (ascending)
          </label>
        </>
      )

    case 'merge':
      return (
        <>
          <div className="rounded-lg p-3 text-xs" style={{ background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.25)', color: '#A78BFA' }}>
            <p className="font-semibold mb-1">Merge = SQL JOIN</p>
            <p>Left input (first connection) is the main table. Right input (second connection) is the table to join in.</p>
          </div>
          <Field label="Left join key" hint="Column in the left (primary) table">
            <ColSel value={op?.left_on} onChange={v => upd({ left_on: v })} columns={columns} />
          </Field>
          <Field label="Right join key" hint="Column in the right (secondary) table">
            {rightColumns.length > 0
              ? <ColSel value={op?.right_on} onChange={v => upd({ right_on: v })} columns={rightColumns} />
              : <TextInput mono value={op?.right_on} onChange={v => upd({ right_on: v })}
                  placeholder="Connect 2nd input to see columns" />
            }
          </Field>
          <Field label="Join type">
            <Sel value={op?.how || 'left'} onChange={v => upd({ how: v })} options={JOIN_TYPES} />
          </Field>
        </>
      )

    case 'concat':
      return (
        <>
          <div className="rounded-lg p-3 text-xs" style={{ background: 'rgba(139,92,246,0.08)', border: '1px solid rgba(139,92,246,0.25)', color: '#A78BFA' }}>
            <p><strong>Axis 0 (stack rows):</strong> Appends rows from right table below the left table. Columns must match.</p>
            <p className="mt-1"><strong>Axis 1 (stack columns):</strong> Places the two tables side by side. Row count must match.</p>
          </div>
          <Field label="Direction">
            <Sel
              value={String(op?.axis ?? '0')}
              onChange={v => upd({ axis: Number(v) })}
              options={[
                { value: '0', label: 'Stack rows (axis = 0)' },
                { value: '1', label: 'Stack columns (axis = 1)' },
              ]}
            />
          </Field>
        </>
      )

    default:
      return null
  }
}

// ── Main export ───────────────────────────────────────────────────────────────

export default function TransformPanel({ node }) {
  const updateNodeData = useStore(s => s.updateNodeData)
  const getInputCount  = useStore(s => s.getInputCount)
  const d = node.data

  const inputCount              = getInputCount(node.id)
  const { columns }             = useUpstreamColumns(node.id, null)
  const { columns: rightColumns } = useRightUpstreamColumns(node.id)
  const availableOps            = inputCount >= 2 && import.meta.env.VITE_PUBLIC_DEMO !== 'true' ? [...TWO_TABLE_OPS, ...SINGLE_OPS] : SINGLE_OPS

  const op    = d.operation || {}
  const setOp = newOp => updateNodeData(node.id, { operation: newOp })

  return (
    <div className="p-4 space-y-4">
      <SectionHeader
        title="Transform"
        subtitle="Apply one operation to the incoming data"
      />

      <Field label="Node Label">
        <input
          className="w-full text-sm rounded-lg px-3 py-2 outline-none"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.12)', color: '#ffffff' }}
          value={d.label || ''}
          onChange={e => updateNodeData(node.id, { label: e.target.value })}
        />
      </Field>

      <Field label="Operation">
        <select
          className="w-full text-sm rounded-lg px-3 py-2 outline-none font-medium"
          style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid rgba(255,255,255,0.12)', color: '#ffffff' }}
          value={op.type || ''}
          onChange={e => setOp({ type: e.target.value })}
        >
          <option value="">Select an operation…</option>
          {inputCount >= 2 && import.meta.env.VITE_PUBLIC_DEMO !== 'true' && (
            <optgroup label="─ Two-table operations ─">
              {TWO_TABLE_OPS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
            </optgroup>
          )}
          <optgroup label="─ Single-table operations ─">
            {SINGLE_OPS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </optgroup>
        </select>
        {inputCount === 0 && (
          <p className="text-xs mt-1" style={{ color: 'rgba(255,255,255,0.35)' }}>
            Connect an input to this node to enable operations.
          </p>
        )}
      </Field>

      {/* Operation description */}
      {op.type && OP_DESC[op.type] && (
        <div
          className="rounded-lg px-3 py-2 text-xs leading-relaxed"
          style={{ background: 'rgba(16,185,129,0.08)', border: '1px solid rgba(16,185,129,0.25)', color: '#34d399' }}
        >
          {OP_DESC[op.type]}
        </div>
      )}

      {/* Dynamic fields */}
      {op.type && (
        <div className="space-y-4 pt-2" style={{ borderTop: '1px solid rgba(255,255,255,0.07)' }}>
          <OperationFields op={op} setOp={setOp} columns={columns} rightColumns={rightColumns} />
        </div>
      )}
    </div>
  )
}
