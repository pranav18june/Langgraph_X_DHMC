/**
 * crypto.js — Browser-friendly hash utilities for the DHMC Dashboard.
 */

function fnvBlock(str, seed = 0x811c9dc5) {
  let h = seed;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return (h >>> 0).toString(16).padStart(8, '0');
}

export function hashPayload(data) {
  const str = typeof data === 'string' ? data : JSON.stringify(data);
  let result = '';
  let seed = 0x811c9dc5;
  for (let round = 0; round < 8; round++) {
    const block = fnvBlock(str + ':' + round, seed);
    result += block;
    seed = parseInt(block, 16) ^ 0x9e3779b9;
  }
  return result;
}

export function generateNonce() {
  let nonce = '';
  for (let i = 0; i < 16; i++) {
    nonce += Math.floor(Math.random() * 0xffffffff).toString(16).padStart(8, '0');
  }
  return nonce.slice(0, 64);
}

export function generateCASUri(data) {
  return `cas://sha256:${hashPayload(data)}`;
}

export function abbreviateHash(hash, length = 8) {
  if (!hash) return '';
  if (hash.length <= length) return hash;
  return hash.slice(0, length) + '…';
}

export function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
