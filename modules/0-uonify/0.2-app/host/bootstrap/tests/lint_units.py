#!/usr/bin/env python3
"""Comprobación LOCAL de las unidades systemd y ficheros de configuración del host.

No sustituye a `systemd-analyze verify` (no existe en macOS; bootstrap.sh lo ejecuta en el host):
comprueba secciones y directivas conocidas, rutas absolutas en Exec*, invariantes de diseño
(uonify-secrets sin aislamiento de montajes, Before/RequiredBy docker) y la sintaxis de
OnCalendar, del daemon.json de Docker y de las fuentes deb822 de apt.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
KNOWN = {
    'Unit': {'Description', 'Documentation', 'Wants', 'Requires', 'Requisite', 'BindsTo', 'PartOf',
             'Upholds', 'Conflicts', 'Before', 'After', 'OnFailure', 'OnSuccess', 'RequiresMountsFor',
             'WantsMountsFor', 'DefaultDependencies', 'StartLimitIntervalSec', 'StartLimitBurst',
             'JobTimeoutSec', 'RefuseManualStart', 'RefuseManualStop', 'StopWhenUnneeded'},
    'Service': {'Type', 'RemainAfterExit', 'ExecStart', 'ExecStartPre', 'ExecStartPost', 'ExecStop',
                'ExecReload', 'TimeoutStartSec', 'TimeoutStopSec', 'TimeoutSec', 'Restart', 'RestartSec',
                'Environment', 'EnvironmentFile', 'UMask', 'NoNewPrivileges', 'LockPersonality',
                'RestrictRealtime', 'CapabilityBoundingSet', 'SyslogIdentifier', 'Nice',
                'IOSchedulingClass', 'IOSchedulingPriority', 'PrivateTmp', 'ProtectSystem',
                'ProtectHome', 'User', 'Group', 'WorkingDirectory', 'StandardOutput', 'StandardError'},
    'Timer': {'OnCalendar', 'RandomizedDelaySec', 'AccuracySec', 'Persistent', 'OnBootSec',
              'OnUnitActiveSec', 'Unit', 'WakeSystem', 'FixedRandomDelay'},
    'Install': {'WantedBy', 'RequiredBy', 'Also', 'Alias', 'UpheldBy'},
}
NAMESPACING = {'PrivateTmp', 'ProtectSystem', 'ProtectHome', 'PrivateDevices', 'ReadOnlyPaths',
               'ReadWritePaths', 'InaccessiblePaths', 'TemporaryFileSystem', 'BindPaths',
               'BindReadOnlyPaths', 'ProtectKernelTunables', 'ProtectKernelModules',
               'ProtectKernelLogs', 'ProtectControlGroups', 'PrivateMounts', 'MountFlags',
               'RootDirectory', 'RootImage', 'ProtectClock', 'ProtectProc', 'ProcSubset'}
BOOL = {'yes', 'no', 'true', 'false', 'on', 'off', '1', '0'}
errors = []


def parse(path):
    sections, current = {}, None
    for number, raw in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(('#', ';')):
            continue
        header = re.fullmatch(r'\[([A-Za-z]+)\]', line)
        if header:
            current = sections.setdefault(header.group(1), [])
            continue
        if current is None or '=' not in line:
            errors.append(f'{path.name}:{number}: línea fuera de sección o sin "="')
            continue
        key, value = line.split('=', 1)
        current.append((key.strip(), value.strip(), number))
    return sections


def values(sections, section, key):
    return [value for k, value, _ in sections.get(section, []) if k == key]


def lint_unit(path):
    sections = parse(path)
    for section, items in sections.items():
        if section not in KNOWN:
            errors.append(f'{path.name}: sección desconocida [{section}]')
            continue
        for key, value, number in items:
            if key not in KNOWN[section]:
                errors.append(f'{path.name}:{number}: directiva desconocida {key}= en [{section}]')
            if key.startswith('Exec') and not value.lstrip('-@:+!').startswith('/'):
                errors.append(f'{path.name}:{number}: {key} debe usar una ruta absoluta')
            if key in {'RemainAfterExit', 'NoNewPrivileges', 'LockPersonality', 'RestrictRealtime',
                       'PrivateTmp', 'Persistent'} and value not in BOOL:
                errors.append(f'{path.name}:{number}: {key} espera un booleano')
            if key == 'Environment' and not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*=.*', value):
                errors.append(f'{path.name}:{number}: Environment mal formado')
    return sections


def check(condition, message):
    if not condition:
        errors.append(message)


secrets = lint_unit(ROOT / 'secrets/uonify-secrets.service')
check(values(secrets, 'Service', 'Type') == ['oneshot'], 'uonify-secrets: Type=oneshot')
check(values(secrets, 'Service', 'RemainAfterExit') == ['yes'], 'uonify-secrets: RemainAfterExit=yes')
check('docker.service' in ' '.join(values(secrets, 'Unit', 'Before')), 'uonify-secrets: Before=docker.service')
check(values(secrets, 'Install', 'RequiredBy') == ['docker.service'], 'uonify-secrets: RequiredBy=docker.service')
check(values(secrets, 'Service', 'ExecStart') == ['/usr/local/sbin/uonify-secrets-sync'], 'uonify-secrets: ExecStart')
check(not any(k in NAMESPACING for k, _, _ in secrets.get('Service', [])),
      'uonify-secrets: no puede usar opciones que creen un espacio de montaje propio')
caps = ' '.join(values(secrets, 'Service', 'CapabilityBoundingSet')).split()
check({'CAP_SYS_ADMIN', 'CAP_CHOWN', 'CAP_FOWNER', 'CAP_DAC_OVERRIDE'} <= set(caps),
      'uonify-secrets: faltan capacidades para montar/chown')

backup = lint_unit(ROOT / 'bootstrap/files/uonify-pg-backup.service')
check(values(backup, 'Service', 'ExecStart') == ['/usr/local/sbin/uonify-pg-backup'], 'pg-backup: ExecStart')
timer = lint_unit(ROOT / 'bootstrap/files/uonify-pg-backup.timer')
calendar = values(timer, 'Timer', 'OnCalendar')
check(len(calendar) == 1 and re.fullmatch(r'\*-\*-\* ([01]\d|2[0-3]):[0-5]\d:[0-5]\d UTC', calendar[0]),
      'pg-backup.timer: OnCalendar diario en UTC')
check(values(timer, 'Install', 'WantedBy') == ['timers.target'], 'pg-backup.timer: WantedBy=timers.target')
dropin = lint_unit(ROOT / 'bootstrap/files/docker-10-uonify.conf')
check(set(dropin) == {'Unit'} and values(dropin, 'Unit', 'RequiresMountsFor') == ['/data']
      and values(dropin, 'Unit', 'After') == ['uonify-secrets.service'], 'drop-in de docker inesperado')

daemon = json.loads((ROOT / 'bootstrap/files/docker-daemon.json').read_text())
check(daemon.get('features', {}).get('containerd-snapshotter') is True, 'daemon.json: containerd-snapshotter')
check(daemon.get('log-driver') == 'local', 'daemon.json: log-driver local')

for name in ('ubuntu.sources', 'docker.sources'):
    text = (ROOT / 'bootstrap/files' / name).read_text()
    stanzas = [s for s in re.split(r'\n\s*\n', '\n'.join(l for l in text.splitlines() if not l.startswith('#'))) if s.strip()]
    for stanza in stanzas:
        fields = dict(line.split(':', 1) for line in stanza.strip().splitlines())
        check({'Types', 'URIs', 'Suites', 'Components', 'Signed-By'} <= set(fields), f'{name}: faltan campos deb822')
        check(all(uri.startswith('https://') for uri in fields.get('URIs', '').split()), f'{name}: URIs solo https')

chrony = [l for l in (ROOT / 'bootstrap/files/uonify-amazon-time-sync.sources').read_text().splitlines()
          if l and not l.startswith('#')]
check(chrony == ['server 169.254.169.123 prefer iburst minpoll 4 maxpoll 4'], 'chrony: fuente Amazon Time Sync')

if errors:
    print('\n'.join('  FAIL ' + e for e in errors))
    sys.exit(1)
print('  ok   unidades, drop-in, timer, daemon.json, fuentes deb822 y chrony')
