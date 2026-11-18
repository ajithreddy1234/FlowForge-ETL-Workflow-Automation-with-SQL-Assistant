const X = {
  credential: 80,
  extract: 330,
  transform: 590,
  load: 880,
}

const START_Y = 120
const GAP_Y = 150

function asArray(value) {
  if (value == null) return []
  return Array.isArray(value) ? value : [value]
}

function hasIndexFlow(value) {
  if (!value || typeof value !== 'object') return false
  if (
    value.in != null ||
    value.out != null ||
    value.inputs != null ||
    value.outputs != null ||
    value.input_index != null ||
    value.input_indices != null ||
    value.right_input_index != null ||
    value.output_index != null ||
    value.output_indices != null
  ) return true

  return Object.values(value).some(child =>
    Array.isArray(child)
      ? child.some(hasIndexFlow)
      : hasIndexFlow(child)
  )
}

function hasIncomingIndexFlow(value) {
  if (!value || typeof value !== 'object') return false
  const firstOperation = value.operations?.[0] || {}
  return value.in != null ||
    value.inputs != null ||
    value.input_index != null ||
    value.input_indices != null ||
    value.right_input_index != null ||
    firstOperation.right_input_index != null
}

export function reportToGraph(report) {
  const nodes = []
  const edges = []
  const tableToNode = new Map()
  const indexToNode = new Map()
  const indexToDefinition = new Map()
  const nodeDefs = []
  const useIndexFlow = hasIndexFlow(report)
  let idSeq = 1

  const nextId = (type) => `${type}_${idSeq++}`
  const addEdge = (source, target, targetHandle = null) => {
    if (!source || !target) return
    const exists = edges.some(edge =>
      edge.source === source &&
      edge.target === target &&
      (edge.targetHandle || null) === (targetHandle || null)
    )
    if (exists) return
    edges.push({
      id: `edge_${source}_${target}_${edges.length + 1}`,
      source,
      target,
      targetHandle,
      animated: true,
      type: 'deletable',
    })
  }
  const registerNode = (definition, nodeId) => {
    nodeDefs.push({ definition, nodeId })
    if (definition?.index != null) {
      indexToNode.set(String(definition.index), nodeId)
      indexToDefinition.set(String(definition.index), definition)
    }
  }

  let credentialId = null
  if (report.credential) {
    credentialId = nextId('credential')
    nodes.push({
      id: credentialId,
      type: 'credential',
      position: { x: X.credential, y: START_Y },
      data: {
        label: 'Credential',
        connection_id: report.credential.connection_id || null,
        connection_name: report.credential.connection_name || '',
        db_profile: report.credential.db_profile || report.extract?.db_profile || 'mysql',
        db_type: report.credential.db_type || report.credential.db_profile || report.extract?.db_profile || 'mysql',
        host: report.credential.host || '',
        port: report.credential.port || '',
        database: report.credential.database || '',
        username: report.credential.username || '',
        password: report.credential.password || '',
        connectionStatus: report.credential.connection_id ? 'connected' : 'idle',
        runStatus: 'idle',
      },
    })
    registerNode(report.credential, credentialId)
  }

  const queries = report.extract?.queries || []
  queries.forEach((query, index) => {
    const id = nextId('extract')
    const name = query.name || `extract_${index + 1}`
    nodes.push({
      id,
      type: 'extract',
      position: { x: X.extract, y: START_Y + index * GAP_Y },
      data: {
        label: name,
        sql: query.query || '',
        source_mode: query.source_mode || 'query',
        table_name: query.table_name || '',
        incremental_mode: query.incremental_mode || 'none',
        checkpoint_column: query.checkpoint_column || '',
        expected_columns: query.expected_columns || [],
        query_date: report.reference_date || '',
        reference_date: report.reference_date || '',
        runStatus: 'idle',
      },
    })
    registerNode(query, id)
    tableToNode.set(name, id)
    if (!useIndexFlow) addEdge(credentialId, id)
  })

  let transformIndex = 0
  ;(report.transform || []).forEach((step) => {
    let inputNodeId = tableToNode.get(step.input)
    const operations = step.operations?.length ? step.operations : [{}]

    operations.forEach((operation, opIndex) => {
      const id = nextId('transform')
      const isLastOperation = opIndex === operations.length - 1
      const outputName = isLastOperation
        ? (step.output || `${step.name || 'transform'}_output`)
        : `${step.output || step.name || 'transform'}_${opIndex + 1}`

      nodes.push({
        id,
        type: 'transform',
        position: { x: X.transform + opIndex * 230, y: START_Y + transformIndex * GAP_Y },
        data: {
          label: operations.length > 1 ? `${step.name || 'Transform'} ${opIndex + 1}` : (step.name || 'Transform'),
          operation: { ...operation },
          runStatus: 'idle',
        },
      })
      registerNode(step, id)

      if (!useIndexFlow) addEdge(inputNodeId, id)

      if (!useIndexFlow && operation?.right_input && tableToNode.has(operation.right_input)) {
        addEdge(tableToNode.get(operation.right_input), id, 'right')
      }

      tableToNode.set(outputName, id)
      if (isLastOperation && step.output) tableToNode.set(step.output, id)
      inputNodeId = id
      transformIndex += 1
    })
  })

  const loadBlocks = Array.isArray(report.load)
    ? report.load
    : report.load
      ? [report.load]
      : []

  loadBlocks.forEach((loadBlock, index) => {
    const sheets = loadBlock.sheets || []
    const id = nextId('load')
    const firstInput = sheets[0]?.input
    nodes.push({
      id,
      type: 'load',
      position: { x: X.load, y: START_Y + index * GAP_Y },
      data: {
        label: loadBlock.name || 'Sink',
        write_mode: loadBlock.write_mode || 'overwrite',
        google_sheet_url: loadBlock.google_sheet_id || '',
        tab_names: sheets.map(s => s.name).filter(Boolean),
        tab_name: sheets[0]?.name || '',
        runStatus: 'idle',
      },
    })
    registerNode(loadBlock, id)
    if (!useIndexFlow) addEdge(tableToNode.get(firstInput), id)
  })

  if (useIndexFlow) {
    nodeDefs.forEach(({ definition, nodeId }) => {
      asArray(definition.out ?? definition.outputs ?? definition.output_indices ?? definition.output_index)
        .forEach(targetIndex => {
          const targetDefinition = indexToDefinition.get(String(targetIndex))
          if (!hasIncomingIndexFlow(targetDefinition)) {
            addEdge(nodeId, indexToNode.get(String(targetIndex)))
          }
        })

      if (definition.inputs && typeof definition.inputs === 'object' && !Array.isArray(definition.inputs)) {
        addEdge(indexToNode.get(String(definition.inputs.left)), nodeId)
        addEdge(indexToNode.get(String(definition.inputs.right)), nodeId, 'right')
      }

      asArray(definition.in ?? definition.input_indices ?? definition.input_index)
        .forEach((sourceIndex, i) => addEdge(indexToNode.get(String(sourceIndex)), nodeId, i === 0 ? null : 'right'))

      const firstOperation = definition.operations?.[0] || {}
      const rightInputIndex = definition.right_input_index ?? firstOperation.right_input_index
      if (rightInputIndex != null) {
        addEdge(indexToNode.get(String(rightInputIndex)), nodeId, 'right')
      }
    })
  }

  return {
    pipeline_name: report.report_name || 'Untitled Pipeline',
    nodes,
    edges,
  }
}
