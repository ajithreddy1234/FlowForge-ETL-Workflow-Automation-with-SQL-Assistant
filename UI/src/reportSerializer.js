export function graphToReport(graph) {
  const ordered = topoSort(graph.nodes, graph.edges)
  const keyById = tableKeys(ordered)
  const credential = graph.nodes.find(n => n.type === 'credential')

  const report = {
    report_name: graph.pipeline_name || 'Untitled',
  }

  const referenceDate = firstReferenceDate(ordered)
  if (referenceDate) report.reference_date = referenceDate

  report.extract = {
    db_profile: dbProfile(credential),
    queries: ordered
      .filter(n => n.type === 'extract')
      .map(n => ({
        name: keyById[n.id],
        query: n.data?.sql || '',
        source_mode: n.data?.source_mode || 'query',
        table_name: n.data?.table_name || '',
        incremental_mode: n.data?.incremental_mode || 'none',
        checkpoint_column: n.data?.checkpoint_column || '',
        expected_columns: n.data?.expected_columns || [],
      })),
  }

  report.transform = ordered
    .filter(n => n.type === 'transform')
    .map(n => {
      const operation = cleanOperation(n.data?.operation || {})
      if (!Object.keys(operation).length) return null
      return {
        name: n.data?.label || keyById[n.id],
        input: firstInput(n.id, graph.edges, keyById),
        output: keyById[n.id],
        operations: [operation],
      }
    })
    .filter(Boolean)

  const loadNodes = ordered.filter(n => n.type === 'load')
  report.load = loadNodes.length
      ? loadNodes.map(node => ({
        google_sheet_id: extractSheetId(node.data?.google_sheet_url || ''),
        write_mode: node.data?.write_mode || 'overwrite',
        sheets: tabNames(node.data || {}).map(tab => ({
          name: tab,
          input: firstInput(node.id, graph.edges, keyById),
        })),
      }))
    : { google_sheet_id: '', sheets: [] }

  return report
}

function topoSort(nodes, edges) {
  const nodeIds = new Set(nodes.map(n => n.id))
  const byId = Object.fromEntries(nodes.map(n => [n.id, n]))
  const inDegree = Object.fromEntries(nodes.map(n => [n.id, 0]))
  const adj = Object.fromEntries(nodes.map(n => [n.id, []]))

  edges.forEach(e => {
    if (!nodeIds.has(e.source) || !nodeIds.has(e.target)) return
    adj[e.source].push(e.target)
    inDegree[e.target] += 1
  })

  const queue = nodes.filter(n => inDegree[n.id] === 0)
  const result = []
  while (queue.length) {
    const node = queue.shift()
    result.push(node)
    adj[node.id].forEach(id => {
      inDegree[id] -= 1
      if (inDegree[id] === 0) queue.push(byId[id])
    })
  }
  return result
}

function tableKeys(nodes) {
  const used = new Set()
  const keys = {}
  nodes.forEach(node => {
    if (!['extract', 'transform', 'load'].includes(node.type)) return
    const base = node.data?.label || node.id
    const initial = slug(base) || (node.type === 'load' ? 'sink' : node.id)
    let key = initial
    let i = 2
    while (used.has(key)) {
      key = `${initial}_${i}`
      i += 1
    }
    used.add(key)
    keys[node.id] = key
  })
  return keys
}

function dbProfile(node) {
  return node?.data?.db_profile || node?.data?.db_type || 'mysql'
}

function firstReferenceDate(nodes) {
  const node = nodes.find(n => n.type === 'extract')
  return node?.data?.reference_date || node?.data?.query_date || ''
}

function firstInput(nodeId, edges, keyById) {
  const edge = edges.find(e => e.target === nodeId)
  return edge ? (keyById[edge.source] || edge.source) : ''
}

function tabNames(data) {
  const names = data.tab_names?.length ? data.tab_names : [data.tab_name || '']
  return names.map(t => String(t).trim()).filter(Boolean)
}

function extractSheetId(value) {
  const match = String(value).match(/\/spreadsheets\/d\/([a-zA-Z0-9_-]+)/)
  return match ? match[1] : value
}

function cleanOperation(operation) {
  const copy = { ...operation }
  delete copy.right_input
  return dropEmpty(copy)
}

function dropEmpty(value) {
  if (Array.isArray(value)) {
    return value.map(dropEmpty).filter(v => !isEmpty(v))
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value)
        .map(([k, v]) => [k, dropEmpty(v)])
        .filter(([, v]) => !isEmpty(v))
    )
  }
  return value
}

function isEmpty(value) {
  return value === '' || value === undefined || value === null ||
    (Array.isArray(value) && value.length === 0) ||
    (value && typeof value === 'object' && Object.keys(value).length === 0)
}

function slug(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '')
}
