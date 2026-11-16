#!/usr/bin/env python3
"""Six-gate native qualification on official signed Core v0.1.13 (macOS ARM64).

Developer harness only (never packaged). One NEW disposable REGTEST profile and
a disposable keychain under ./.wam-regtest-temp; public test password; no seed
is printed or stored. Drives the real WalletExecutor -> Bip39ReadOnlyBackend ->
Q06OwnedSpendSession path (the same backend the GUI uses), against real Core:

  TX-03  sign, Lock before Broadcast (crash-equivalent: signed + evidence),
         reopen, read-only status = SIGNED_NOT_SUBMITTED_RESUMABLE, explicit
         resume of the EXACT signed tx, real confirmation, status cleared.
  CUR-004 real Core policy rejection (fee 1 atom < min relay): definitive
         REJECTED before submission, durable 'signed', not in mempool, no fault,
         Lock/reopen still possible, resume is rejected again and sends nothing.

Optional RSS sampling of this process and the owned wamd (Q18 evidence only).
"""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time


def _rss_kib(pid):
    out = subprocess.run(['ps', '-o', 'rss=', '-p', str(pid)], capture_output=True, text=True)
    return int(out.stdout.strip()) if out.returncode == 0 and out.stdout.strip() else None


class Sampler(threading.Thread):
    def __init__(self, root, interval=0.5):
        super().__init__(daemon=True)
        self.root, self.interval, self.samples, self.stop_event = root, interval, [], threading.Event()
        self.phase = 'init'

    def run(self):
        import os
        while not self.stop_event.is_set():
            pids = subprocess.run(['pgrep', '-f', 'wamd.*' + str(self.root)],
                                  capture_output=True, text=True).stdout.split()
            core = sum(filter(None, (_rss_kib(p) for p in pids))) if pids else None
            self.samples.append(dict(t=time.time(), phase=self.phase,
                                     fusion_rss_kib=_rss_kib(os.getpid()), core_rss_kib=core))
            self.stop_event.wait(self.interval)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--core-dir', type=Path, required=True)
    parser.add_argument('--wsp-source', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--confirm-disposable-regtest', action='store_true')
    parser.add_argument('--lock-cycles', type=int, default=0,
                        help='Q18 evidence only: bounded extra Lock/reopen cycles (max 20)')
    a = parser.parse_args()
    if not 0 <= a.lock_cycles <= 20:
        raise SystemExit('SIX_GATE_LOCK_CYCLES_BOUND')
    if not a.confirm_disposable_regtest or a.report.exists():
        raise SystemExit('SIX_GATE_NATIVE_CONSENT_OR_NEW_REPORT_REQUIRED')
    from mnemonic import Mnemonic
    from wam_regtest import custody
    from wam_regtest.bip39_12 import Bip39Regtest12Keys
    from wam_regtest.bip39_owner_backend import Bip39ReadOnlyBackend
    from wam_regtest.q05_platforms import DarwinArm64Adapter
    from wam_regtest.wallet_executor import WalletExecutor
    from wam_regtest.core import verified_core_paths
    adapter = DarwinArm64Adapter()
    adapter.enforce_host()
    _, _, receipt = verified_core_paths(a.core_dir.resolve())
    record = dict(status='FAIL', network='regtest', mainnet_allowed=False,
                  source_sha=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  core_sha256={'wamd': receipt['wamd_sha256'], 'wam-cli': receipt['wam_cli_sha256']},
                  wsp_source_commit='ac55f13423620252bdbf848c7e8a280c3b84721e', steps=[])

    def step(name, **facts):
        record['steps'].append(dict(step=name, utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), **facts))
        print('SIX_GATE_NATIVE_STEP=' + name, flush=True)

    def denied(callable_, label):
        try:
            callable_()
        except Exception as error:  # Public fixed codes only.
            code = error.args[0] if len(error.args) == 1 and type(error.args[0]) is str else type(error).__name__
            return code
        raise SystemExit('SIX_GATE_EXPECTED_DENIAL_NOT_RAISED_' + label)

    parent = Path.cwd() / '.wam-regtest-temp'
    if not parent.exists():
        custody.create_directory(parent)
    root = Path(tempfile.mkdtemp(prefix='six-gate-native-', dir=parent)).resolve() / (
        'wam-fusion-core-' + secrets.token_hex(8))
    custody.create_directory(root)
    record['disposable_profile'] = str(root)
    sampler = Sampler(root)
    sampler.start()
    recipient = Bip39Regtest12Keys(Mnemonic('english').to_mnemonic(bytes([7] * 16)),
                                   source=a.wsp_source, authorized_disposable=True)
    destination = recipient.accounts()[0].payment_code()
    recipient.close()
    password = b'public-disposable-six-gate-native-only'
    executor = WalletExecutor(lambda: Bip39ReadOnlyBackend(
        root, a.core_dir.resolve(), a.wsp_source, _anchor_factory=adapter.make_anchor))
    request = lambda action, *args, timeout=240: executor.request(action, *args, timeout=timeout)
    try:
        sampler.phase = 'create'
        opened = request('open', password, 'create', '', timeout=180)
        if len(opened['mnemonic_once'].split()) != 12:
            raise SystemExit('SIX_GATE_CREATE_DENIED')
        opened = None  # never retain or print the phrase
        step('CREATE_PASS')
        sampler.phase = 'fund'
        funded = request('mine')
        step('FUND_PASS', atoms=funded['atoms'])
        sampler.phase = 'activate'
        active = request('activate')
        assert active['signer_allowed'] is True and active['mainnet_allowed'] is False
        step('ACTIVATE_PASS', confirmed_atoms=active['confirmed_atoms'])

        # ---- TX-03: signed, evidence persisted, never broadcast; Lock = crash-equivalent.
        sampler.phase = 'sign'
        draft = request('prepare', destination, 100_000, 10_000)
        request('sign', draft.commitment)
        step('TX03_SIGNED_NOT_BROADCAST', commitment=draft.commitment)
        sampler.phase = 'lock_reopen'
        request('lock', timeout=120)
        request('open', password, 'reopen', '', timeout=180)
        request('activate')
        status = request('intent_status')
        [item] = status['intents']
        assert item['classification'] == 'SIGNED_NOT_SUBMITTED_RESUMABLE', item
        assert status['write_attempted'] is False and status['abandon_available'] is False
        step('TX03_STATUS_AFTER_REOPEN', classification=item['classification'],
             state=item['state'], atoms=item['atoms'], fee=item['fee'])
        code = denied(lambda: request('resume_intent', item['token'], 'f' * 64, True), 'WRONG_TXID')
        step('TX03_WRONG_TXID_REFUSED', code=code)
        sampler.phase = 'resume'
        resumed = request('resume_intent', item['token'], item['txid'], True)
        assert resumed['txid'] == item['txid'] and resumed['resigned'] is False
        step('TX03_EXACT_RESUME_SUBMITTED', txid_matches_signed_evidence=True)
        code = denied(lambda: request('resume_intent', item['token'], item['txid'], True), 'REPEAT')
        step('TX03_REPEAT_RESUME_REFUSED', code=code)
        sampler.phase = 'confirm'
        confirmed = request('confirm', resumed['txid'])
        assert confirmed['status'] == 'Q06_REGTEST_EXACT_SEND_CONFIRMED'
        observed = request('inspect_confirmed', resumed['txid'])
        assert observed['status'] == 'Q06_CONFIRMED_IN_VERIFIED_HISTORY'
        after = request('intent_status')['intents']
        record['tx03_status_after_confirm'] = [
            {k: i.get(k) for k in ('state', 'classification', 'evidence')} for i in after]
        assert all(i['classification'] == 'CONFIRMED_IN_VERIFIED_HISTORY' for i in after), after
        step('TX03_CONFIRMED_IN_VERIFIED_HISTORY', height=confirmed['height'],
             remaining=[(i['state'], i['classification']) for i in after])

        # ---- CUR-004 real Core rejection: fee of 1 atom is below min relay fee.
        sampler.phase = 'reject'
        low = request('prepare', destination, 50_000, 1)
        request('sign', low.commitment)
        code = denied(lambda: request('broadcast', low.commitment), 'REJECT')
        assert code == 'WALLET_BROADCAST_REJECTED_LOCK_RETAINED', code
        state = executor.state
        step('CUR004_REAL_CORE_REJECTION', code=code, faulted=state.faulted)
        assert state.faulted is False
        status = request('intent_status')
        [rejected] = status['intents']
        assert (rejected['state'], rejected['classification']) == ('signed', 'SIGNED_NOT_SUBMITTED_RESUMABLE')
        step('CUR004_DURABLE_SIGNED_NOT_IN_MEMPOOL', classification=rejected['classification'])
        request('lock', timeout=120)
        request('open', password, 'reopen', '', timeout=180)
        request('activate')
        [again] = request('intent_status')['intents']
        assert again['state'] == 'signed' and again['token'] == rejected['token']
        code = denied(lambda: request('resume_intent', again['token'], again['txid'], True), 'RESUME_REJECT')
        assert code == 'WALLET_BROADCAST_REJECTED_LOCK_RETAINED', code
        [still] = request('intent_status')['intents']
        assert still['state'] == 'signed' and still['classification'] == 'SIGNED_NOT_SUBMITTED_RESUMABLE'
        step('CUR004_REOPEN_AND_RESUME_REJECTED_AGAIN_SIGNED_RETAINED', code=code)
        for cycle in range(a.lock_cycles):
            sampler.phase = 'lock_cycle_%02d' % cycle
            request('lock', timeout=120)
            request('open', password, 'reopen', '', timeout=180)
            request('activate')
            request('snapshot')
        if a.lock_cycles:
            step('Q18_LOCK_REOPEN_CYCLES', cycles=a.lock_cycles)
        sampler.phase = 'idle'
        time.sleep(15)
        sampler.phase = 'quit'
        request('quit', timeout=120)
        if not executor.join(30) or not executor.closed:
            raise SystemExit('SIX_GATE_OWNER_STILL_LIVE')
        step('CLEAN_SHUTDOWN')
        record['status'] = 'SIX_GATE_NATIVE_REAL_CORE_PASS'
    finally:
        sampler.stop_event.set()
        sampler.join(5)
        record['rss_samples'] = sampler.samples
        if not executor.closed:
            try:
                executor.request('quit', timeout=120)
            except Exception:
                record['quit_after_failure'] = 'NOT_CONFIRMED'
        with a.report.open('x') as handle:
            json.dump(record, handle, indent=2)
            handle.write('\n')
    return 0 if record['status'] == 'SIX_GATE_NATIVE_REAL_CORE_PASS' else 2


if __name__ == '__main__':
    sys.exit(main())
