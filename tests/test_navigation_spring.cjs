const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

// Execute the shipped controller with a test-owned frame clock. Browser frame counts cannot
// establish momentum: a slower frame may consume the entire coast before the next observation.
module.exports = (source = fs.readFileSync(path.join(__dirname, '../beeloft/static/app.mjs'), 'utf8')) => {
  const begin = source.indexOf('let navigationLensSyncFrame');
  const end = source.indexOf('// Preferensi yang berubah', begin);
  assert.ok(begin >= 0 && end > begin, 'the production lens controller is present');
  const controller = source.slice(begin, end);
  const axes = [['cx', 'vx', 'targetCx'], ['cy', 'vy', 'targetCy'],
    ['width', 'vWidth', 'targetWidth'], ['height', 'vHeight', 'targetHeight']];
  const close = (actual, expected, message) => assert.ok(Math.abs(actual - expected) < 1e-8,
    `${message}: ${actual} vs ${expected}`);

  for (const gaps of [[1000/144,1000/144,1000/144,1000/144],
    [1000/60,1000/60,1000/60,1000/60], [7,33,18,80]]) {
    const surface = {classList:{add(){},remove(){}}};
    const lens = {isConnected:true, hidden:false, parentElement:surface, style:{cssText:''}};
    const pending = new Map();
    let serial = 0, time = 1000;
    const {state, retarget} = vm.runInNewContext(controller
      + '\n;({state:navigationLensMotion, retarget:retargetNavigationLens})', {
      navigationSurface:surface, navigationLens:lens, reducedMotion:()=>false,
      requestAnimationFrame:callback => { pending.set(++serial, callback); return serial; },
      cancelAnimationFrame:id => pending.delete(id)
    });
    const frame = dt => {
      time += dt;
      const callbacks = [...pending.values()];
      pending.clear();
      callbacks.forEach(callback => callback(time));
    };
    const origin = {context:surface, x:16, y:20, width:223, height:40};
    // Exercise every velocity component, including a size change, through real integration.
    const destination = {...origin, x:64, y:650, width:196, height:34};
    retarget(origin, 'command-center');
    retarget(destination, 'replenishment');
    frame(0);
    gaps.forEach(frame);
    assert.ok(state.vy > 100 && state.vx > 0, 'the reversal starts with meaningful forward momentum');
    const before = {...state}, handle = [...pending.keys()];
    retarget(origin, 'command-center');
    for (const [value, velocity] of axes) {
      assert.equal(state[value], before[value], `${value}: retarget cannot teleport or restart position`);
      assert.equal(state[velocity], before[velocity], `${velocity}: retarget must preserve live velocity`);
    }
    assert.equal(state.targetId, 'command-center', 'the new destination replaces the old one');
    for (const [key, expected] of Object.entries({targetCx:127.5, targetCy:40, targetWidth:223, targetHeight:40})) {
      assert.equal(state[key], expected, `${key}: the new geometry is installed`);
    }
    assert.equal(state.lastTimestamp, before.lastTimestamp, 'retarget does not restart the clock');
    assert.deepEqual([...pending.keys()], handle, 'retarget retains the existing frame');

    // An independently calculated semi-implicit Euler substep proves the next frame consumes
    // the preserved state and the NEW target. This also catches a reset deferred until the RAF.
    const h = 1/240, expected = axes.map(([value, velocity, target]) => {
      const speed = before[velocity] + (-520 * (before[value] - state[target]) - 40 * before[velocity]) * h;
      return [before[value] + speed * h, speed];
    });
    frame(h * 1000);
    axes.forEach(([value, velocity], index) => {
      close(state[value], expected[index][0], `${value}: next step position`);
      close(state[velocity], expected[index][1], `${velocity}: next step velocity`);
    });
    for (let frames = 0; pending.size && frames < 200; frames++) frame(1000/60);
    assert.equal(pending.size, 0, 'the reversed spring settles and stops scheduling');
    for (const [value, velocity, target] of axes) {
      assert.equal(state[value], state[target], `${value}: exact arrival at the latest destination`);
      assert.equal(state[velocity], 0, `${velocity}: no momentum remains at rest`);
    }
    assert.equal(state.targetId, 'command-center', 'no stale destination wins the final write');
    assert.equal(lens.style.cssText, 'transform:translate(16px,20px);width:223px;height:40px',
      'the renderer writes the latest destination exactly');
  }
};

if (require.main === module) {
  module.exports();
  console.log('Navigation spring physics PASS: velocity and position survive retarget, force-law continuation, latest destination, exact settle.');
}
