#!/usr/bin/env python3
"""Release discovery shared by the adult GUI and the privileged updater.

Only published GitHub Releases are valid update sources. No CI artifacts,
arbitrary links, temporary preview builds on stable channel, or unverified
checksums. Does not install software as part of checking.
"""
import hashlib
import json
import re
import subprocess
import urllib.parse
import urllib.request

API = 'https://api.github.com/repos/shrek1802/ParentPilot/releases?per_page=30'
RELEASE_PREFIX = 'https://github.com/shrek1802/ParentPilot/releases/download/'
TAG = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,89}$')
ASSET = re.compile(r'^parentpilot_([0-9][A-Za-z0-9.+~:-]{0,80})_all[.]deb$')
DIGEST = re.compile(r'^sha256:([0-9a-fA-F]{64})$')
MAX_DEB = 100 * 1024 * 1024
MAX_JSON = 2 * 1024 * 1024


def installed_version():
    cmd = ['dpkg-query', '--show', '--showformat=$' + '{Version}', 'parentpilot']
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    if proc.returncode != 0 or not proc.stdout.strip():
        raise RuntimeError('ParentPilot DEB is not installed.')
    return proc.stdout.strip()


def newer_version(candidate, current):
    # Let Debian compare epochs, release candidates and tilde correctly.
    proc = subprocess.run(
        ['dpkg', '--compare-versions', candidate, 'gt', current],
        capture_output=True, timeout=5)
    return proc.returncode == 0


def valid_release_asset(item, release, channel, current_version, compare=newer_version):
    if not isinstance(item, dict) or not isinstance(release, dict):
        return None
    if release.get('draft'):
        return None
    if channel == 'stable' and release.get('prerelease'):
        return None
    if channel not in ('stable', 'preview'):
        raise ValueError('Invalid update channel.')
    tag = str(release.get('tag_name') or '')
    if not TAG.fullmatch(tag):
        return None
    name = str(item.get('name') or '')
    match = ASSET.fullmatch(name)
    if match is None:
        return None
    # GitHub Release uploads normalise '~' to '.' in asset filenames.
    # Never treat a normalised filename as a Debian package version.
    # The version is derived from the publisher's strict version tag and
    # verified again from the DEB control metadata during installation.
    published_version = tag[1:] if tag.startswith('v') else tag
    published_version = published_version.replace('-preview', '~preview').replace('-rc', '~rc')
    asset_version = match.group(1)
    if asset_version not in (published_version, published_version.replace('~', '.')):
        return None
    version = published_version
    if not compare(version, current_version):
        return None
    digest_match = DIGEST.fullmatch(str(item.get('digest') or ''))
    if not digest_match:
        return None
    size = item.get('size')
    if not isinstance(size, int) or isinstance(size, bool) or not 1 <= size <= MAX_DEB:
        return None
    url = str(item.get('browser_download_url') or '')
    parsed = urllib.parse.urlparse(url)
    if (parsed.scheme != 'https' or parsed.netloc != 'github.com' or
            parsed.username or parsed.password or parsed.query or parsed.fragment or
            not url.startswith(RELEASE_PREFIX + tag + '/' + name)):
        return None
    notes = str(release.get('body') or '').strip()[:5000]
    return {
        'version': version, 'tag': tag, 'channel': channel,
        'changes': notes or 'Bug fixes and improvements.',
        'url': url, 'sha256': digest_match.group(1).lower(),
        'size': size, 'filename': name,
    }


def find_update(releases, current_version, channel='stable', compare=newer_version):
    if not isinstance(releases, list):
        raise ValueError('Unexpected GitHub Releases response.')
    best = None
    for release in releases[:30]:
        if not isinstance(release, dict):
            continue
        for asset in release.get('assets') or []:
            item = valid_release_asset(asset, release, channel, current_version, compare)
            if item and (best is None or compare(item['version'], best['version'])):
                best = item
    return best


def fetch_updates(channel='stable', current_version=None):
    if channel not in ('stable', 'preview'):
        raise ValueError('Unsupported update channel.')
    version = current_version or installed_version()
    request = urllib.request.Request(
        API, headers={'Accept': 'application/vnd.github+json',
                      'User-Agent': 'ParentPilot-Linux-Updater'})
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.geturl() != API:
            raise ValueError('Unexpected GitHub API redirect.')
        payload = response.read(MAX_JSON + 1)
        if len(payload) > MAX_JSON:
            raise ValueError('Update metadata is too large.')
    return find_update(json.loads(payload.decode('utf-8')), version, channel)


def hash_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        while True:
            chunk = handle.read(256 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()
