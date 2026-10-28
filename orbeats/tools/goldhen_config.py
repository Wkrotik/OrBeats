"""Byte-preserving OrBeats GoldHEN registration and legacy-path migration."""

import re
import uuid


def ensure_remote_ini(config, path):
    """Legacy CLI registration uses the same byte-preserving merge and rollback."""
    import additive_companion as core

    p = config["ps4"]
    title = config.get("title", {}).get("id", "CUSA12878")
    f = core.FTP()
    f.connect(p["ip"], int(p.get("ftp_port", 2121)), timeout=30)
    f.login(p.get("ftp_user", "anonymous"), p.get("ftp_password", ""))
    target = "/data/GoldHEN/plugins.ini"
    run = uuid.uuid4().hex
    from console_transaction import Transaction
    transaction = Transaction(core, f, run)
    try:
        core.closed(f)
        old = core.read(f, target, 2000000, missing=True)
        new = merge_ini(old or b"", title, path)
        try:
            transaction.publish(target, new, old)
        except Exception:
            transaction.rollback()
            raise
        transaction.finish()
    finally:
        f.close()


def merge_ini(original, title="CUSA12878", path="/data/GoldHEN/plugins/orbeats.prx"):
    if not re.fullmatch(r"CUSA[0-9]{5}", title) or not re.fullmatch(
        r"/data/GoldHEN/plugins/[A-Za-z0-9_.-]+\.prx", path
    ):
        raise ValueError("Invalid title or plugin path")
    if b"\x00" in original:
        raise ValueError("Invalid plugins.ini")
    # Migrate only exact owned legacy registration in the title section. Keep
    # comments/newlines/unrelated plugins byte-identical; never accept duplicates.
    lines = original.splitlines(keepends=True)
    owned = {'/data/GoldHEN/plugins/orbeats.prx',
             '/data/GoldHEN/plugins/beat_saber_deluxe.prx'}
    scan_section = ''
    registrations = []
    for i, raw in enumerate(lines):
        text = raw.decode('utf-8-sig').strip()
        if text.startswith('[') and text.endswith(']'):
            scan_section = text[1:-1]
        elif text in owned and scan_section not in ('default', title):
            raise ValueError('Owned plugin is registered for another title; review before migration.')
        elif text in owned and scan_section in ('default', title):
            if scan_section == 'default':
                raise ValueError('Plugin is configured globally; review plugins.ini to prevent loading twice.')
            registrations.append(i)
    if len(registrations) > 1:
        raise ValueError('Duplicate OrBeats registrations in plugins.ini; review before updating. No entries changed.')
    if registrations:
        i = registrations[0]
        # Replace path token only, keeping surrounding whitespace and CRLF.
        lines[i] = lines[i].replace(lines[i].strip().lstrip(b'\xef\xbb\xbf'), path.encode())

    section = ""
    present = 0
    insert_at = None
    for i, raw in enumerate(lines):
        line = raw.decode("utf-8-sig").strip()
        if line.startswith("[") and line.endswith("]"):
            if section == title:
                insert_at = i
            section = line[1:-1]
        if section == "default" and line == path:
            raise ValueError("Plugin is configured globally; review plugins.ini to prevent loading twice.")
        if section == title and line == path:
            present += 1
        if (
            section in ("default", title)
            and (line.startswith("/data/GoldHEN/plugins/beat_saber_deluxe") or line.startswith("/data/GoldHEN/plugins/orbeats"))
            and line.endswith(".prx")
            and line != path
            and line != "/data/GoldHEN/plugins/orbeats_extras.prx"
        ):
            raise ValueError("Another variant of this plugin is enabled; review plugins.ini to prevent loading twice.")
    if present > 1:
        raise ValueError("Duplicate OrBeats registrations in plugins.ini; review before updating. No entries changed.")
    if present:
        return b"".join(lines)
    newline = b"\r\n" if b"\r\n" in original else b"\n"
    if section == title:
        insert_at = len(lines)
    if insert_at is not None:
        before = b"".join(lines[:insert_at])
        after = b"".join(lines[insert_at:])
        return before + (newline if before and not before.endswith(b"\n") else b"") + path.encode() + newline + after
    return (
        original
        + (newline if original and not original.endswith(b"\n") else b"")
        + newline
        + ("[" + title + "]").encode()
        + newline
        + path.encode()
        + newline
    )
