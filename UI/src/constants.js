// ── Node visual config (VOID dark theme) ─────────────────────────────────────
export const NODE_COLORS = {
  credential: {
    border: 'rgba(255,255,255,0.22)', bg: '#1C1C1C', header: 'rgba(255,255,255,0.06)',
    label: 'Credential', text: 'rgba(255,255,255,0.75)',
  },
  extract: {
    border: 'rgba(96,165,250,0.5)', bg: '#1C1C1C', header: 'rgba(96,165,250,0.12)',
    label: 'Extract', text: '#93c5fd',
  },
  transform: {
    border: 'rgba(251,146,60,0.5)', bg: '#1C1C1C', header: 'rgba(251,146,60,0.12)',
    label: 'Transform', text: '#fdba74',
  },
  load: {
    border: 'rgba(52,211,153,0.5)', bg: '#1C1C1C', header: 'rgba(52,211,153,0.12)',
    label: 'Sink', text: '#6ee7b7',
  },
}

// ── Single-table operations ────────────────────────────────────────────────────
const ALL_SINGLE_OPS = [
  { value: 'rename',           label: 'Rename Columns'         },
  { value: 'select_columns',   label: 'Select Columns'         },
  { value: 'drop_columns',     label: 'Drop Columns'           },
  { value: 'sort',             label: 'Sort Rows'              },
  { value: 'calculate',        label: 'Calculate (New Column)' },
  { value: 'filter',           label: 'Filter Rows'            },
  { value: 'fillna',           label: 'Fill Empty Values'      },
  { value: 'replace',          label: 'Find & Replace'         },
  { value: 'map',              label: 'Map Values'             },
  { value: 'abs',              label: 'Absolute Value'         },
  { value: 'astype',           label: 'Change Data Type'       },
  { value: 'drop_duplicates',  label: 'Drop Duplicates'        },
  { value: 'groupby',          label: 'Group By + Aggregate'   },
  { value: 'pivot',            label: 'Pivot Table'            },
  { value: 'format_date',      label: 'Format Date'            },
  { value: 'date_extract',     label: 'Extract Date Part'      },
  { value: 'rank',             label: 'Rank'                   },
  { value: 'cumsum',           label: 'Cumulative Sum'         },
  { value: 'pct_of_total',     label: 'Percent of Total'       },
  { value: 'add_total_column', label: 'Add Total Column (row-wise sum)' },
  { value: 'add_total_row',    label: 'Add Total Row (column sums)'    },
]

// ── Two-table operations (shown first when 2 inputs connected) ────────────────
export const TWO_TABLE_OPS = [
  { value: 'merge',  label: 'Merge (Join two tables)'   },
  { value: 'concat', label: 'Concat (Stack two tables)' },
]

// ── What each operation does — shown as a hint in the panel ──────────────────
export const OP_DESC = {
  rename:           'Give columns new names without changing their data.',
  select_columns:   'Keep only the columns you choose — drop the rest.',
  drop_columns:     'Remove specific columns from the table.',
  sort:             'Reorder rows from lowest to highest (or reverse) by one or more columns.',
  calculate:        'Create a brand-new column using a formula (e.g. price * qty).',
  filter:           'Keep only the rows where a condition is true (e.g. amount > 100).',
  fillna:           'Replace blank / null cells with a specific value.',
  replace:          'Find one specific value in a column and swap it for another.',
  map:              'Replace many values at once using a lookup table you define.',
  abs:              'Make every value in a column positive (remove the minus sign).',
  astype:           'Convert a column to a different data type, e.g. text → number.',
  drop_duplicates:  'Remove rows that are exact copies of an earlier row.',
  groupby:          'Collapse rows that share the same value(s) into one row, then calculate a summary (sum, count, average…) per group.',
  pivot:            'Turn unique values in one column into separate column headers (like a spreadsheet pivot table).',
  format_date:      'Change how a date looks, e.g. 2022-01-27 → Jan 27, 2022.',
  date_extract:     'Pull out just one part of a date (year, month, day, weekday…) into a new column.',
  rank:             'Add a rank number (1st, 2nd, 3rd…) based on values in a column.',
  cumsum:           'Add a running total column — each cell = sum of all rows above it.',
  pct_of_total:     "Express each value as a percentage of the column's grand total.",
  add_total_column: 'Add a new column whose value is the row-wise sum of selected numeric columns.',
  add_total_row:    'Append a final summary row at the bottom of the table with column totals.',
  merge:            'Join two tables side-by-side by matching a shared key column (like SQL JOIN).',
  concat:           'Stack two tables together — either add more rows (axis 0) or add more columns (axis 1).',
}

export const AGG_FUNCTIONS  = ['sum', 'count', 'mean', 'min', 'max', 'first', 'last']
export const JOIN_TYPES     = ['left', 'inner', 'right', 'outer']
export const CAST_TYPES     = ['str', 'int', 'float', 'bool']
export const FILTER_OPS     = ['==', '!=', '>', '>=', '<', '<=', 'in', 'not in']
export const DATE_PARTS     = ['year', 'month', 'day', 'day_name', 'week', 'quarter', 'hour', 'minute']

export const SINGLE_OPS = import.meta.env.VITE_PUBLIC_DEMO === 'true' ? ALL_SINGLE_OPS.filter(op => op.value !== 'calculate') : ALL_SINGLE_OPS
