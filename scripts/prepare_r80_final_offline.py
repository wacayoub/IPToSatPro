#!/usr/bin/env python3
"""Offline, fail-closed R80 final packaging from the exact tested RC1 IPK.

No receiver access, no network, no opkg, no mutation of source input or production
GitHub manifest. Default is --check; --build creates an UNPUBLISHED output.
"""
import argparse
import copy
import gzip
import hashlib
import io
import json
import re
import sys
import tarfile
from pathlib import Path

TESTED_SIZE = 461250
TESTED_SHA = 'b6b1fe72ffbcbfaa398bd261c000f9361159a9e08f606a0af9d6da3d5ef04e5e'
TESTED_CORE = '74cd89b8c6a41b4537fd758cedb3a07b2bc0f9a5c215063e4c45b99e5d92cd2a'
OLD = '1.0.46-r80.1-indexfocus-hotpath-rc1'
FINAL = '1.0.46-r80.2-final'
PREFIX = 'usr/lib/enigma2/python/Plugins/Extensions/SatIPTVBridge/'
EXTERNAL = {'etc/init.d/iptosat-tsbridge', 'usr/bin/iptosat-tsbridge'}
RELEASE_MANIFEST_URL = ('https://raw.githubusercontent.com/wacayoub/IPToSatPro/'
                        'release/r80-indexfocus-final-20261017/staging/r80-final.update.json')
UPDATER_URL_RE = re.compile(r'https://raw\.githubusercontent\.com/wacayoub/IPToSatPro/[\w./-]+?\.json')


def must(test, reason):
    if not test:
        raise ValueError(reason)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def normalize(name):
    while name.startswith('./'):
        name = name[2:]
    must(name and not name.startswith('/') and '..' not in Path(name).parts,
         'UNSAFE_ARCHIVE_PATH')
    return name


def get_ar(blob):
    must(blob.startswith(b'!<arch>\n'), 'NOT_IPK')
    pos, entries, order = 8, {}, []
    while pos < len(blob):
        must(pos + 60 <= len(blob), 'TRUNCATED_AR')
        h = blob[pos:pos+60]
        must(h[58:60] == b'\x60\n', 'BAD_AR_HEADER')
        name = h[:16].decode('ascii').strip().rstrip('/')
        count = int(h[48:58].strip())
        must(count >= 0 and pos + 60 + count <= len(blob), 'BAD_AR_SIZE')
        must(name not in entries, 'DUPLICATE_AR_FILE')
        entries[name] = (h, blob[pos+60:pos+60+count])
        order.append(name)
        pos += 60 + count + count % 2
    must(set(entries) == {'debian-binary','data.tar.gz','control.tar.gz'},
         'UNEXPECTED_AR_FILES')
    return entries, order


def pack_ar(entries, order):
    out = bytearray(b'!<arch>\n')
    for name in order:
        head, body = entries[name]
        out += head[:48] + str(len(body)).encode('ascii').ljust(10) + b'\x60\n'
        out += body
        if len(body) % 2:
            out += b'\n'
    return bytes(out)


def unpack_tar(blob):
    with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as tar:
        members = tar.getmembers()
        files = {}
        for entry in members:
            must(entry.isfile() or entry.isdir(), 'UNSUPPORTED_TAR_ENTRY')
            if entry.isfile():
                name = normalize(entry.name)
                must(name not in files, 'DUPLICATE_TAR_FILE')
                files[name] = tar.extractfile(entry).read()
        return members, files


def repack_tar(members, initial, replacements):
    output = io.BytesIO()
    with gzip.GzipFile(fileobj=output, mode='wb', filename='', mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode='w', format=tarfile.GNU_FORMAT) as tar:
            for entry in members:
                copy_entry = copy.copy(entry)
                if entry.isfile():
                    key = normalize(entry.name)
                    data = replacements.get(key, initial[key])
                    copy_entry.size = len(data)
                    tar.addfile(copy_entry, io.BytesIO(data))
                else:
                    tar.addfile(copy_entry)
    return output.getvalue()


def version_only(blob, variable):
    old = (variable + ' = "' + OLD + '"').encode()
    new = (variable + ' = "' + FINAL + '"').encode()
    must(blob.count(old) == 1, 'VERSION_ANCHOR_MISMATCH:' + variable)
    return blob.replace(old, new, 1)


def transform_updater(blob):
    rewritten = version_only(blob,'CURRENT_VERSION')
    text = rewritten.decode('utf8')
    urls = UPDATER_URL_RE.findall(text)
    must(len(urls) == 1, 'UPDATER_SOURCE_URL_AMBIGUOUS')
    must('/release/r80-indexfocus-final-20261017/staging/r80-final.update.json' in
         RELEASE_MANIFEST_URL, 'RELEASE_MANIFEST_NOT_ISOLATED')
    if urls[0] != RELEASE_MANIFEST_URL:
        text = text.replace(urls[0], RELEASE_MANIFEST_URL, 1)
    must('/main/update.json' not in text, 'UPDATER_MAIN_R70_REFERENCE_REMAINS')
    return text.encode('utf8')


def transform(blob, expected_size=TESTED_SIZE, expected_sha=TESTED_SHA,
              expected_core=TESTED_CORE, require_full_asset_count=True):
    must(len(blob) == expected_size and digest(blob) == expected_sha,
         'TESTED_INPUT_PACKAGE_MISSING_OR_SHA_MISMATCH')
    ar, order = get_ar(blob)
    datamembers, data = unpack_tar(ar['data.tar.gz'][1])
    ctrlmembers, control = unpack_tar(ar['control.tar.gz'][1])
    plugin = {p[len(PREFIX):] for p in data if p.startswith(PREFIX)}
    outside = set(data) - {PREFIX + n for n in plugin}
    must(outside == EXTERNAL, 'OUTSIDE_FILES_NOT_EXPECTED')
    if require_full_asset_count:
        must(len(plugin) == 87, 'PLUGIN_ASSET_COUNT_DIFFERS')
    required = {PREFIX+x for x in ('core.py','plugin.py','updater.py')}
    must(required <= set(data), 'PLUGIN_RUNTIME_FILES_MISSING')
    must(digest(data[PREFIX+'core.py']) == expected_core,
         'CORE_NOT_EXACT_HARDWARE_VALIDATED_CODE')
    must('control' in control and 'postinst' in control,
         'PACKAGE_MAINTAINER_FILES_MISSING')
    must(not (set(control)&{'preinst','prerm','postrm'}),
         'UNEXPECTED_MAINTAINER_SCRIPT')
    # Match the exact passive postinst from the hardware-tested staging builder.
    known_postinst = (
        "#!/bin/sh\n"
        "printf '%s\\n' 'IPToSatPro Index Focus Preview hot-path RC staged; restart GUI manually.'\n"
        "exit 0\n"
    ).encode('utf-8')
    must(control['postinst'] == known_postinst, 'UNEXPECTED_POSTINST')
    old_version = 'Version: '+OLD
    must(control['control'].decode('utf8').count(old_version) == 1,
         'CONTROL_VERSION_MISMATCH')
    replacements = {
        PREFIX+'plugin.py': version_only(data[PREFIX+'plugin.py'],'PLUGIN_VERSION'),
        PREFIX+'updater.py': transform_updater(data[PREFIX+'updater.py']),
    }
    new_control = control['control'].decode('utf8').replace(old_version,'Version: '+FINAL,1).encode('utf8')
    ar['data.tar.gz'] = (ar['data.tar.gz'][0], repack_tar(datamembers,data,replacements))
    ar['control.tar.gz'] = (ar['control.tar.gz'][0], repack_tar(ctrlmembers,control,{'control':new_control}))
    result = pack_ar(ar,order)
    _, output_files = unpack_tar(get_ar(result)[0]['data.tar.gz'][1])
    _, output_control = unpack_tar(get_ar(result)[0]['control.tar.gz'][1])
    must(set(output_files) == set(data), 'OUTPUT_FILES_CHANGED')
    for name in data:
        must(output_files[name] == replacements.get(name,data[name]),
             'UNEXPECTED_EXECUTABLE_OR_RESOURCE_CHANGE:'+name)
    must(output_files[PREFIX+'core.py'] == data[PREFIX+'core.py'], 'CORE_CHANGED')
    must(output_control['postinst'] == control['postinst'], 'POSTINST_CHANGED')
    must(output_control['control'] == new_control, 'CONTROL_DIFFERS')
    summary = {
        'status':'OFFLINE_FINAL_BUILD_VERIFIED_UNPUBLISHED',
        'source_hardware_tested_version':OLD,
        'final_version':FINAL,
        'source_sha256':digest(blob),
        'final_sha256':digest(result),
        'final_bytes':len(result),
        'core_sha256_unchanged':digest(output_files[PREFIX+'core.py']),
        'changed_only':['control:Version','plugin.py:PLUGIN_VERSION',
                        'updater.py:CURRENT_VERSION','updater.py:isolated R80 final update manifest'],
        'unchanged_operational_payload':True,
        'published':False,
        'receiver_or_configuration_touched':False,
        'cold_preview_speed_certified':False,
    }
    return result, summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',type=Path,required=True,help='Verified receiver R80.1 RC1 IPK')
    p.add_argument('--output',type=Path,default=Path('iptosatpro-r80-final-UNPUBLISHED.ipk'))
    p.add_argument('--build',action='store_true',help='Write the final candidate IPK; never publish')
    a=p.parse_args()
    try:
        source=a.input.read_bytes()
        out,report=transform(source)
        if a.build:
            must(not a.output.exists(), 'REFUSE_OVERWRITE')
            a.output.write_bytes(out)
            must(digest(a.output.read_bytes())==report['final_sha256'],'WRITE_HASH_MISMATCH')
            report['output_path']=str(a.output)
        else:
            report['status']='OFFLINE_FINAL_DRY_RUN_PASS_NO_OUTPUT'
        print(json.dumps(report,indent=2,sort_keys=True))
    except (OSError,ValueError,tarfile.TarError,UnicodeError) as e:
        print(json.dumps({'status':'FINAL_BUILD_BLOCKED','reason':str(e)[:240],
                          'published':False},indent=2))
        return 2
    return 0


if __name__=='__main__':
    sys.exit(main())
