const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

module.exports = (source = fs.readFileSync(path.join(__dirname, '../beeloft/static/app.mjs'), 'utf8')) => {
  const begin = source.indexOf('function navigationLensOptics(');
  const end = source.indexOf('function renderNavigationLensMotion()', begin);
  assert.ok(begin >= 0 && end > begin);
  const optics = vm.runInNewContext(source.slice(begin, end) + ';navigationLensOptics');
  const rest = {stretch:0, bulge:0, offset:0, taper:0, rim:0, leading:50};
  const plain = value => JSON.parse(JSON.stringify(value));
  assert.deepEqual(plain(optics(0, true)), rest, 'zero velocity is canonical rest');
  for (const vy of [400, -400, 1e10, -1e10, NaN, Infinity, -Infinity]) {
    assert.deepEqual(plain(optics(vy, false)), rest, 'settled state removes all dynamic optics');
  }
  for (const vy of [NaN, Infinity, -Infinity]) assert.deepEqual(plain(optics(vy, true)), rest);
  let previous = rest;
  for (let speed = 1; speed <= 4000; speed++) {
    const down = optics(speed, true), up = optics(-speed, true);
    for (const value of Object.values(down)) assert.ok(Number.isFinite(value));
    for (const key of ['stretch','bulge','rim']) {
      assert.ok(down[key] >= previous[key], `${key} grows monotonically until bounded`);
      assert.equal(down[key], up[key], `${key} is independent of direction`);
    }
    assert.ok(down.stretch > 0 && down.stretch <= .35);
    assert.ok(down.bulge > 0 && down.bulge <= .09);
    assert.ok(down.rim > 0 && down.rim <= .80);
    assert.ok(down.offset > 0 && down.offset <= .085 && down.taper > 0 && down.taper <= .25,
      'leading offset and unequal end curvature are both present');
    assert.equal(up.offset, -down.offset); assert.equal(up.taper, -down.taper);
    assert.ok(down.leading > 50 && down.leading <= 100 && up.leading < 50 && up.leading >= 0);
    previous = down;
  }
  assert.deepEqual(plain(optics(400, true)), plain(optics(1e9, true)), 'cap does not grow with a long jump');
  for (let vy = 4; vy > -4; vy -= .01) {
    const a = optics(vy, true), b = optics(vy - .01, true);
    for (const key of Object.keys(a)) assert.ok(Math.abs(a[key] - b[key]) < .002,
      `${key} crosses zero continuously instead of flipping on the new target`);
  }
  // Execute the production renderer too: a correct mapper cannot excuse a stuck inline rim.
  const controller = source.slice(source.indexOf('let navigationLensSyncFrame'), source.indexOf('// Preferensi yang berubah'));
  const surface = {classList:{add(){},remove(){}}};
  const lens = {style:{cssText:''}, hidden:false, isConnected:true, parentElement:surface};
  const api = vm.runInNewContext(controller + ';({state:navigationLensMotion,render:renderNavigationLensMotion})', {
    navigationSurface:surface, navigationLens:lens,
  });
  Object.assign(api.state, {cx:100, cy:200, width:180, height:36, vy:400, running:true});
  api.render(); assert.match(lens.style.cssText, /--liquid-stretch:1\.35/);
  api.state.running = false; api.state.vy = 0; api.render();
  assert.equal(lens.style.cssText, 'transform:translate(10px,182px);width:180px;height:36px',
    'the final write restores exact A5.2 geometry and removes all optical properties');
};

if (require.main === module) {
  module.exports();
  console.log('Liquid lens mapping PASS: canonical rest, direction, monotonic caps, asymmetric ends, finite reversal, exact renderer reset.');
}
