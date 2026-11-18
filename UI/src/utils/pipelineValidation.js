// Client-side pre-flight checks. The backend is the real source of truth
// (executor.py / pipeline_storage.py) — this only catches obvious problems
// early so users get instant feedback instead of a round trip.

export function validatePipeline(nodes, edges) {
  const issues = []

  const credential = nodes.find(n => n.type === 'credential')
  const extracts = nodes.filter(n => n.type === 'extract')
  const transforms = nodes.filter(n => n.type === 'transform')
  const loads = nodes.filter(n => n.type === 'load')

  if (nodes.length === 0) {
    issues.push({ message: 'The canvas is empty. Add a Credential, Extract, and Sink node to build a pipeline.' })
    return issues
  }

  if (!credential) {
    issues.push({ message: 'A Credential node is required to connect to your source database.' })
  } else if (!credential.data?.connection_id && !(credential.data?.host && credential.data?.database && credential.data?.username)) {
    issues.push({ nodeId: credential.id, nodeLabel: 'Credential', message: 'Fill in Host, Database, and Username on the Credential node.' })
  } else if (credential.data?.connectionStatus !== 'connected') {
    issues.push({ nodeId: credential.id, nodeLabel: 'Credential', message: 'Check the database connection on the Credential node before running.' })
  }

  if (extracts.length === 0) {
    issues.push({ message: 'At least one Extract node is required as a data source.' })
  }
  extracts.forEach(node => {
    const source = node.data?.source_mode === 'table' ? node.data?.table_name : node.data?.sql
    if (!(source || '').trim()) {
      issues.push({ nodeId: node.id, nodeLabel: node.data?.label || 'Extract', message: node.data?.source_mode === 'table' ? 'Table name is required.' : 'SQL query is required.' })
    }
    if (node.data?.incremental_mode && node.data.incremental_mode !== 'none' && !(node.data?.checkpoint_column || '').trim()) {
      issues.push({ nodeId: node.id, nodeLabel: node.data?.label || 'Extract', message: 'Checkpoint column is required.' })
    }
    if (!edges.some(e => e.target === node.id)) {
      issues.push({ nodeId: node.id, nodeLabel: node.data?.label || 'Extract', message: 'Connect a Credential node to this Extract node.' })
    }
  })

  if (extracts.some(node => node.data?.incremental_mode && node.data.incremental_mode !== 'none') && loads.some(node => node.data?.write_mode !== 'append')) {
    issues.push({ message: 'Incremental extraction requires append mode on every Sink node.' })
  }

  transforms.forEach(node => {
    if (!edges.some(e => e.target === node.id)) {
      issues.push({ nodeId: node.id, nodeLabel: node.data?.label || 'Transform', message: 'This Transform node has no input connection.' })
    }
  })

  if (loads.length === 0) {
    issues.push({ message: 'At least one Sink node is required as a destination.' })
  }
  loads.forEach(node => {
    if (!(node.data?.google_sheet_url || '').trim()) {
      issues.push({ nodeId: node.id, nodeLabel: node.data?.label || 'Sink', message: 'Google Sheet URL or ID is required.' })
    }
    const tabs = (node.data?.tab_names?.length ? node.data.tab_names : [node.data?.tab_name]).filter(t => String(t || '').trim())
    if (tabs.length === 0) {
      issues.push({ nodeId: node.id, nodeLabel: node.data?.label || 'Sink', message: 'At least one tab name is required.' })
    }
    if (!edges.some(e => e.target === node.id)) {
      issues.push({ nodeId: node.id, nodeLabel: node.data?.label || 'Sink', message: 'Connect an upstream node to this Sink node.' })
    }
  })

  return issues
}
