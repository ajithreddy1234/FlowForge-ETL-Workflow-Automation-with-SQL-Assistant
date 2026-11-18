import assert from 'node:assert/strict';
import test from 'node:test';
const values = new Map();
Object.defineProperty(globalThis, 'localStorage', { configurable:true, value: { getItem:key => values.get(key) ?? null, setItem:(key,value) => values.set(key,value), removeItem:key => values.delete(key) } });
const { newId, useStore } = await import('../src/store.js');

test('restored pipeline IDs cannot collide with newly created nodes', () => {
  useStore.getState().loadGraph({ pipeline_name: 'Restored', nodes: [{ id: 'extract_500', type: 'extract', position: {x:0,y:0}, data: {label:'Orders'} }], edges: [] }, 'restored');
  const id = newId('extract');
  assert.ok(Number(id.split('_').at(-1)) > 500);
});

test('computed input counts do not mark a loaded pipeline as edited', () => {
  useStore.getState().loadGraph({ pipeline_name: 'Restored', nodes: [{ id:'transform_502', type:'transform', position:{x:0,y:0}, data:{label:'Group'} }], edges:[] }, 'restored');
  assert.equal(useStore.getState().dirty, false);
  useStore.getState().updateNodeData('transform_502', {_inputCount:1});
  assert.equal(useStore.getState().dirty, false);
  useStore.getState().updateNodeData('transform_502', {label:'Revenue'});
  assert.equal(useStore.getState().dirty, true);
});
