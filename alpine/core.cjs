const srp = require('tssrp6a');
const { randomBytes, hkdfSync, createHmac, timingSafeEqual } = require('node:crypto');
const params = new srp.SRPParameters(srp.SRPParameters.PrimeGroup[2048], srp.SRPParameters.H.SHA256);
const routines = new srp.SRPRoutines(params);
const hex = n => n.toString(16);
function integer(s) {
  if (typeof s !== 'string' || !/^[0-9a-f]{1,512}$/.test(s)) throw Error('Invalid protocol integer');
  return BigInt('0x' + s);
}
function derive(S, sid) {
  return Buffer.from(hkdfSync('sha256', Buffer.from(hex(S)), Buffer.from(sid), Buffer.from('peostectica-browser-v1'), 32));
}
function mac(key, path, counter, body) {
  return createHmac('sha256', key).update(`${path}\n${counter}\n${body}`).digest('hex');
}
class Bridge {
  constructor(record, now = () => Date.now()) {
    this.record = record; this.now = now; this.challenges = new Map(); this.sessions = new Map();
    this.queue = new Map(); this.results = new Map(); this.attempts = [];
  }
  cleanup() {
    for (const [id, v] of this.challenges) if (v.expires < this.now()) this.challenges.delete(id);
    for (const [id, v] of this.sessions) if (v.expires < this.now()) this.sessions.delete(id);
    for (const [id, v] of this.results) if (v.expires < this.now()) this.results.delete(id);
    for (const [id, v] of this.queue) if (v.expires < this.now()) this.queue.delete(id);
  }
  async start(identity) {
    this.cleanup(); this.attempts = this.attempts.filter(t => t > this.now() - 60000);
    if (this.attempts.length >= 5 || this.challenges.size >= 5) throw Error('Authentication rate limit');
    this.attempts.push(this.now());
    if (identity !== this.record.identity) throw Error('Authentication failed');
    const state = await new srp.SRPServerSession(routines).step1(identity, integer(this.record.salt), integer(this.record.verifier));
    const id = randomBytes(24).toString('hex');
    this.challenges.set(id, {state, expires: this.now() + 60000});
    return {challenge: id, salt: this.record.salt, B: hex(state.B)};
  }
  async finish(id, A, M1) {
    this.cleanup(); const challenge = this.challenges.get(id); this.challenges.delete(id);
    if (!challenge) throw Error('Authentication failed');
    const publicA = integer(A), proof = integer(M1);
    const M2 = await challenge.state.step2(publicA, proof);
    const S = await challenge.state.sessionKey(publicA);
    const sid = randomBytes(24).toString('hex');
    this.sessions.set(sid, {key: derive(S, sid), counter: 0, expires: this.now() + 3600000, tabs: []});
    return {sid, M2: hex(M2), expires_seconds: 3600};
  }
  authenticate(sid, path, counter, body, signature) {
    this.cleanup(); const session = this.sessions.get(sid);
    if (!session || !Number.isSafeInteger(counter) || counter <= session.counter || typeof signature !== 'string' || !/^[0-9a-f]{64}$/.test(signature)) throw Error('Unauthorized');
    const wanted = Buffer.from(mac(session.key, path, counter, body), 'hex');
    if (!timingSafeEqual(wanted, Buffer.from(signature, 'hex'))) throw Error('Unauthorized');
    session.counter = counter; return session;
  }
  revoke(sid) {
    this.sessions.delete(sid);
    for (const [id, v] of this.queue) if (v.sid === sid) this.queue.delete(id);
    for (const [id, v] of this.results) if (v.sid === sid) this.results.delete(id);
  }
  enqueue(sid, tabId) {
    this.cleanup(); const s = this.sessions.get(sid);
    if (!s || !s.tabs.some(t => t.id === tabId)) throw Error('Tab not enabled');
    if (this.queue.size >= 20) throw Error('Queue full');
    const id = randomBytes(16).toString('hex');
    this.queue.set(id, {id, sid, op: 'read', tabId, expires: this.now() + 60000}); return {id};
  }
}
module.exports = {srp, routines, hex, integer, derive, mac, Bridge};
