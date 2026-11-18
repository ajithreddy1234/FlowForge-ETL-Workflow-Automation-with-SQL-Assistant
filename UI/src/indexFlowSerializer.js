const asList = (value) => value == null ? [] : Array.isArray(value) ? value : [value]

function slug(value) {
  return String(value || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_+|_+$/g, '') || 'output'
}

function label(node, fallback) {
  return node?.data?.label || fallback
}

function cleanOperation(operation = {}) {
  const { index, right_input, right_input_index, ...rest } = operation
  return dropEmpty(rest)
}

function dropEmpty(value) {
  if (Array.isArray(value)) {
    return value.map(dropEmpty).filter(v => !isEmpty(v))
  }
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value)
        .map(([key, item]) => [key, dropEmpty(item)])
        .filter(([, item]) => !isEmpty(item))
    )
  }
  return value
}

function isEmpty(value) {
  return value === '' || value == null ||
    (Array.isArray(value) && value.length === 0) ||
    (value && typeof value === 'object' && Object.keys(value).length === 0)
}

function extractSheetId(value) {
  const match = String(value || '').match(/\/spreadsheets\/d\/([a-zA-Z0-9_-]+)/)
  return match ? match[1] : value
}

function topoSort(nodes, edges) {
  const ids = new Set(nodes.map(n => n.id))
  const byId = Object.fromEntries(nodes.map(n => [n.id, n]))
  const inDegree = Object.fromEntries(nodes.map(n => [n.id, 0]))
  const adj = Object.fromEntries(nodes.map(n => [n.id, []]))

  edges.forEach(edge => {
    if (!ids.has(edge.source) || !ids.has(edge.target)) return
    adj[edge.source].push(edge.target)
    inDegree[edge.target] += 1
  })

  const queue = nodes.filter(node => inDegree[node.id] === 0)
  const ordered = []
  while (queue.length) {
    const node = queue.shift()
    ordered.push(node)
    adj[node.id].forEach(id => {
      inDegree[id] -= 1
      if (inDegree[id] === 0) queue.push(byId[id])
    })
  }

  return ordered.length === nodes.length ? ordered : nodes
}

export function graphToIndexFlow(graph) {
  const nodes = graph.nodes || []
  const edges = graph.edges || []
  const ordered = topoSort(nodes, edges)
  const indexById = Object.fromEntries(ordered.map((node, index) => [node.id, index + 1]))
  const incoming = Object.fromEntries(nodes.map(node => [node.id, []]))
  const outgoing = Object.fromEntries(nodes.map(node => [node.id, []]))

  edges.forEach(edge => {
    if (indexById[edge.source] && indexById[edge.target]) {
      incoming[edge.target].push(edge)
      outgoing[edge.source].push(edge)
    }
  })

  const inIndexes = (nodeId) => {
    const all = incoming[nodeId] || []
    const left = all.filter(edge => edge.targetHandle !== 'right')
    const right = all.filter(edge => edge.targetHandle === 'right')
    return [...left, ...right].map(edge => indexById[edge.source]).filter(Boolean)
  }

  const outIndexes = (nodeId) =>
    (outgoing[nodeId] || []).map(edge => indexById[edge.target]).filter(Boolean)

  const report = {
    report_name: graph.pipeline_name || 'Untitled Pipeline',
  }

  const credential = ordered.find(node => node.type === 'credential')
  if (credential) {
    report.credential = dropEmpty({
      index: indexById[credential.id],
      out: outIndexes(credential.id),
      connection_id: credential.data?.connection_id,
      connection_name: credential.data?.connection_name,
      db_type: credential.data?.db_type || 'mysql',
      host: credential.data?.host || '',
      port: credential.data?.port || '',
      database: credential.data?.database || '',
      username: credential.data?.username || '',
      password: credential.data?.connection_id ? '' : (credential.data?.password || ''),
      connectionStatus: credential.data?.connectionStatus || 'idle',
    })
  }

  const extracts = ordered.filter(node => node.type === 'extract')
  if (extracts.length) {
    report.extract = {
      queries: extracts.map(node => dropEmpty({
        index: indexById[node.id],
        name: label(node, node.id),
        out: outIndexes(node.id),
        query: node.data?.sql || '',
        source_mode: node.data?.source_mode || 'query',
        table_name: node.data?.table_name || '',
        incremental_mode: node.data?.incremental_mode || 'none',
        checkpoint_column: node.data?.checkpoint_column || '',
        expected_columns: node.data?.expected_columns || [],
      })),
    }
  }

  const transforms = ordered.filter(node => node.type === 'transform')
  if (transforms.length) {
    report.transform = transforms.map(node => dropEmpty({
      index: indexById[node.id],
      name: label(node, 'Transform'),
      in: inIndexes(node.id),
      out: outIndexes(node.id),
      output: slug(label(node, node.id)),
      operations: [cleanOperation(node.data?.operation || {})],
    }))
  }

  const loads = ordered.filter(node => node.type === 'load')
  if (loads.length) {
    report.load = loads.map(node => dropEmpty({
      index: indexById[node.id],
      name: label(node, 'Sink'),
      write_mode: node.data?.write_mode || 'overwrite',
      google_sheet_id: extractSheetId(node.data?.google_sheet_url || ''),
      sheets: asList(node.data?.tab_names?.length ? node.data.tab_names : node.data?.tab_name || '')
        .map(name => String(name).trim())
        .filter(Boolean)
        .map(name => ({ name })),
    }))
  }

  return report
}
