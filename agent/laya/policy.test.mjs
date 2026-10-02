import test from 'node:test';
import assert from 'node:assert/strict';
import { proposal } from './policy.mjs';

test('confident classification remains advisory, never approval', () => {
  assert.deepEqual(proposal('oi', {choice:'social', probabilities:{social:0.99, email:0.01}}),
    {route:'social', advisory:true, execute:false});
});
test('abstains on low confidence and malformed probabilities', () => {
  for (const probabilities of [{social:0.7,email:0.3}, {social:NaN}, {social:1.2}, {social:0.99,email:0.5}]) {
    assert.equal(proposal('oi', {choice:'social', probabilities}).route, 'hermes');
  }
});
test('never shortcuts ambiguity, too-long input or unknown routes', () => {
  for (const choice of ['mixed','context','other','invented']) {
    assert.equal(proposal('pedido', {choice,probabilities:{[choice]:1}}).route,'hermes');
  }
  assert.equal(proposal('x'.repeat(801), {choice:'social',probabilities:{social:1}}).route,'hermes');
});
