'use strict';
// Legacy exports retain the source quality family while keeping their schema.
// No source quality field means the older simulator's explicit badPv contract.
function sourceQuality(point) {
  if (point.badPv || !Number.isFinite(point.pv)) return 'bad';
  if (point.quality == null) return 'good';
  const quality = String(point.quality).toUpperCase();
  if (quality === 'GOOD') return 'good';
  if (quality === 'BAD' || quality === 'ERROR') return 'bad';
  return 'uncertain';
}
module.exports = {sourceQuality};
