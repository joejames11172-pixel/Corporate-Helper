#!/usr/bin/env python3
"""Install the Alpine browser-broker replacement, with automatic service rollback."""
import datetime, hashlib, json, os, pathlib, shutil, socket, ssl, subprocess, time, urllib.request
HERE = pathlib.Path(__file__).resolve().parent
BASE = pathlib.Path('/opt/corporate-helper')
OLD = pathlib.Path('/opt/peostectica-browser-diagnostics')
CONFIG = OLD / 'private/config.json'
OLD_SERVICE = 'peostectica-browser-diagnostics'
SERVICE = pathlib.Path('/etc/init.d/corporate-helper')
def call(*args):
    return subprocess.run(list(args), check=True, capture_output=True, timeout=30)
def main():
    if os.geteuid() != 0:
        raise SystemExit('Run: doas python3 -I ' + str(HERE / 'install.py'))
    if BASE.exists() or SERVICE.exists():
        raise SystemExit('Existing Corporate Helper deployment found; inspect before upgrading.')
    manifest = json.loads((HERE / 'SHA256SUMS.json').read_text())
    for name, wanted in manifest.items():
        p = HERE / name
        if p.is_symlink() or name not in ('server.cjs','transport.cjs','core.cjs','test.cjs','https-test.cjs','package.json','install.py','README.md','browser-rpc.cjs','browser-rpc.test.cjs','peer-relay.cjs','peer-relay.test.cjs'):
            raise SystemExit('Unexpected package file')
        if hashlib.sha256(p.read_bytes()).hexdigest() != wanted:
            raise SystemExit('Package hash mismatch: ' + name)
    cfg = json.loads(CONFIG.read_text())
    if CONFIG.is_symlink() or CONFIG.stat().st_mode & 0o077:
        raise SystemExit('Unsafe existing configuration')
    if cfg.get('bind', '127.0.0.1') != '127.0.0.1' or cfg.get('port') != 18766:
        raise SystemExit('Existing endpoint differs; explicit migration required')
    # Existing enrollment stays private, in place; do not export secrets to staging.
    tls = ssl.create_default_context(cafile=cfg['tlsCert'])
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), urllib.request.HTTPSHandler(context=tls))
    def health():
        with opener.open('https://localhost:18766/health', timeout=4) as response:
            return json.load(response)
    before = health()
    if before.get('service') == 'corporate-helper':
        raise SystemExit('Corporate Helper already owns endpoint; reconcile deployment')
    old_enabled = pathlib.Path('/etc/runlevels/default/' + OLD_SERVICE).exists()
    obsolete_enabled = pathlib.Path('/etc/runlevels/default/supermium_bridge').exists()
    obsolete_running = subprocess.run(['/sbin/rc-service','supermium_bridge','status'], capture_output=True, timeout=10).returncode == 0
    stopped = False
    try:
        BASE.mkdir(mode=0o755)
        app = BASE / 'app'; app.mkdir()
        for name in manifest:
            shutil.copyfile(HERE / name, app / name); os.chmod(app / name, 0o644)
        shutil.copyfile(HERE / 'SHA256SUMS.json', app / 'SHA256SUMS.json')
        shutil.copytree(OLD / 'app/node_modules', app / 'node_modules')
        # Run existing SRP and HTTPS round-trip tests as the existing unprivileged service user.
        import pwd
        user = pwd.getpwnam('peosrp')
        for test in ('test.cjs', 'https-test.cjs', 'browser-rpc.test.cjs','peer-relay.cjs','peer-relay.test.cjs'):
            p = subprocess.run(['/usr/bin/node', '--test', test], cwd=app,
                user=user.pw_uid, group=user.pw_gid, extra_groups=[], capture_output=True, timeout=90)
            if p.returncode:
                raise RuntimeError('Pre-install test failed: ' + test)
        SERVICE.write_text('#!/sbin/openrc-run\n'
            'description="Corporate Helper browser broker, HTTPS loopback only"\n'
            'supervisor="supervise-daemon"\n'
            'command="/usr/bin/node"\n'
            'command_args="/opt/corporate-helper/app/server.cjs /opt/peostectica-browser-diagnostics/private/config.json"\n'
            'command_user="peosrp:peosrp"\n'
            'pidfile="/run/corporate-helper.pid"\n'
            'respawn_delay=30\nrespawn_max=0\nrespawn_period=0\n'
            'output_log="/opt/peostectica-browser-diagnostics/logs/corporate-helper.log"\n'
            'error_log="/opt/peostectica-browser-diagnostics/logs/corporate-helper-error.log"\n'
            'depend() {\n need localmount\n use net\n}\n')
        os.chmod(SERVICE, 0o755)
        call('/sbin/rc-service', OLD_SERVICE, 'stop'); stopped = True
        call('/sbin/rc-service', 'corporate-helper', 'start')
        for attempt in range(10):
            try:
                if health().get('service') == 'corporate-helper': break
            except (OSError, ValueError): pass
            if attempt == 9: raise RuntimeError('New service health check failed')
            time.sleep(1)
        call('/sbin/rc-update', 'add', 'corporate-helper', 'default')
        if old_enabled: call('/sbin/rc-update', 'del', OLD_SERVICE, 'default')
        if obsolete_running: call('/sbin/rc-service', 'supermium_bridge', 'stop')
        if obsolete_enabled: call('/sbin/rc-update', 'del', 'supermium_bridge', 'default')
        report = {'installed_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='milliseconds'),
            'service': 'corporate-helper', 'endpoint': 'https://127.0.0.1:18766',
            'tests': ['SRP unit tests', 'verified HTTPS/SRP/MCP snapshot round-trip'],
            'preserved': ['pairing enrollment', 'TLS certificate', 'operator API', 'Gateway tunnel', 'old service files'],
            'retired_from_startup': ['supermium_bridge'] if obsolete_enabled else [],
            'pending': ['Windows helper and tunnels', 'automatic browser enrollment/reconnect', 'firewall controls', 'LAN discovery'],
            'rollback': 'stop corporate-helper; remove its default runlevel entry; start and re-enable peostectica-browser-diagnostics'}
        (BASE / 'installation.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
    except BaseException:
        if SERVICE.exists():
            subprocess.run(['/sbin/rc-service', 'corporate-helper', 'stop'], capture_output=True, timeout=30)
            subprocess.run(['/sbin/rc-update', 'del', 'corporate-helper', 'default'], capture_output=True, timeout=30)
        if stopped:
            if old_enabled: call('/sbin/rc-update', 'add', OLD_SERVICE, 'default')
            call('/sbin/rc-service', OLD_SERVICE, 'start')
        if obsolete_enabled: call('/sbin/rc-update', 'add', 'supermium_bridge', 'default')
        if obsolete_running: call('/sbin/rc-service', 'supermium_bridge', 'start')
        # Leave a failed candidate for inspection; never delete prior service files.
        raise
if __name__ == '__main__': main()
