"""Local Code native attachment adapter: exact project-staged files, no search."""
from pathlib import Path
import re
import unicodedata


def candidates(label):
    """Only canonical Unicode and the macOS timestamp space serialization differ."""
    if not isinstance(label,str) or not label or '\x00' in label:
        raise ValueError('ACTUAL_ATTACHMENT_NAME_REQUIRED')
    value=Path(label)
    if '..' in value.parts or (not value.is_absolute() and len(value.parts)!=1):
        raise ValueError('ATTACHMENT_NAME_OR_ORIGINAL_ABSOLUTE_LABEL_REQUIRED')
    name=value.name
    if name in ('','.','..'):
        raise ValueError('ACTUAL_ATTACHMENT_NAME_REQUIRED')
    names=[]
    for form in ('NFC','NFD'):
        normalized=unicodedata.normalize(form,name)
        for item in (normalized,
                     re.sub(r' (?=(?:AM|PM)\.[^.]+$)','\u202f',normalized),
                     re.sub(r'\u202f(?=(?:AM|PM)\.[^.]+$)',' ',normalized)):
            if item not in names:names.append(item)
    return names


def ingest(label, root, read_attachment, expected_sha256=None):
    """Bind current-request attachment label to Local Code's project-root copy.

    This is same-user file custody, not authenticated proof of chat membership.
    No original source path is opened, no directory is enumerated, no prior run
    supplies a fallback. Metadata hashes, when supplied by a client, are binding.
    """
    root=Path(root)
    matches=[]
    for name in candidates(label):
        path=root/name
        if path.is_symlink():raise ValueError('ATTACHMENT_STAGED_SYMLINK_REJECTED')
        if path.exists():
            row,blob=read_attachment(path)
            matches.append((row,blob))
    if not matches:
        raise ValueError('ATTACHMENT_BYTES_UNAVAILABLE: native attachment must be staged by Local Code in this project; no Desktop access or file search attempted')
    if len({row['sha256'] for row,_ in matches})!=1:
        raise ValueError('ATTACHMENT_NAME_AMBIGUOUS: staged filename variants contain different bytes')
    row,blob=matches[0]
    if expected_sha256 is not None and row['sha256']!=expected_sha256:
        raise ValueError('ATTACHMENT_METADATA_HASH_MISMATCH')
    row.update(ingestion=dict(adapter='local-code-project-attachment/1',requested_label=label,
        staged_name=Path(row['path']).name,source='native-client-project-staged-copy',
        original_path_opened=False,directory_search=False,
        name_resolution='exact-or-canonical-unicode-or-macOS-timestamp-space',
        metadata_hash_verified=expected_sha256 is not None,
        association='Current attachment label supplied by operator; not authenticated chat membership'))
    return row,blob
