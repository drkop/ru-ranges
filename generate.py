#!/usr/bin/env python3
"""Generate ru_ranges.rsc from RIPE NCC country resource data.

Security: every prefix is validated as a strict IPv4 network before
being written to the .rsc file, preventing command injection via
compromised API responses.
"""

import ipaddress
import json
import sys
import time
import urllib.request

RIPE_URL = "https://stat.ripe.net/data/country-resource-list/data.json?resource=RU&v4_format=prefix"
OUTPUT = "ru_ranges.rsc"
OUTPUT_TIMEOUT = "ru_ranges_timeout.rsc"
TIMEOUT = 60
RETRIES = 3
RETRY_DELAY = 10

# Sanity bounds — RIPE RU typically returns ~11,000 prefixes
MIN_PREFIXES = 1000
MAX_PREFIXES = 50000


def validate_prefix(raw):
    """Validate and normalize a single IPv4 prefix.

    Returns the normalized prefix string (e.g. '1.2.3.0/24') or None if invalid.
    """
    if not isinstance(raw, str):
        return None

    # Reject anything with characters that can't be in a CIDR notation
    if any(c not in "0123456789./" for c in raw):
        return None

    try:
        net = ipaddress.IPv4Network(raw, strict=False)
    except (ipaddress.AddressValueError, ValueError):
        return None

    # Reject private/reserved ranges — RIPE should not return these
    if net.is_private or net.is_reserved or net.is_loopback or net.is_link_local:
        return None

    return str(net)


def main():
    # Fetch with retries
    req = urllib.request.Request(RIPE_URL, headers={"User-Agent": "ru-ranges/1.0 (GitHub Actions)"})
    raw = None
    for attempt in range(1, RETRIES + 1):
        try:
            resp = urllib.request.urlopen(req, timeout=TIMEOUT)
            if resp.status != 200:
                raise Exception(f"HTTP {resp.status}")
            raw = resp.read()
            break
        except Exception as e:
            print(f"Attempt {attempt}/{RETRIES} failed: {e}", file=sys.stderr)
            if attempt < RETRIES:
                time.sleep(RETRY_DELAY)
    if raw is None:
        print("Failed to fetch RIPE data after all retries", file=sys.stderr)
        sys.exit(1)

    # Parse JSON
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON from RIPE: {e}", file=sys.stderr)
        sys.exit(1)

    # Validate JSON structure
    try:
        raw_prefixes = data["data"]["resources"]["ipv4"]
    except (KeyError, TypeError):
        print("Unexpected JSON structure from RIPE", file=sys.stderr)
        sys.exit(1)

    if not isinstance(raw_prefixes, list):
        print("RIPE ipv4 field is not a list", file=sys.stderr)
        sys.exit(1)

    # Validate every prefix
    skipped = []
    prefixes = []
    for raw_p in raw_prefixes:
        validated = validate_prefix(raw_p)
        if validated:
            prefixes.append(validated)
        else:
            skipped.append(repr(raw_p))

    if skipped:
        print(f"Skipped {len(skipped)} invalid entries: {', '.join(skipped[:10])}", file=sys.stderr)

    # Sanity check on count
    count = len(prefixes)
    if count < MIN_PREFIXES:
        print(f"Too few prefixes ({count} < {MIN_PREFIXES}) — aborting", file=sys.stderr)
        sys.exit(1)
    if count > MAX_PREFIXES:
        print(f"Too many prefixes ({count} > {MAX_PREFIXES}) — aborting", file=sys.stderr)
        sys.exit(1)

    # Generate .rsc — ONLY address-list add commands, nothing else.
    # The remove/log steps are handled by the MikroTik update script,
    # so even a compromised .rsc can only add address-list entries.
    prefixes.sort(key=lambda p: ipaddress.IPv4Network(p))

    with open(OUTPUT, "w") as f:
        for p in prefixes:
            f.write(f"/ip firewall address-list add list=RU address={p} comment=RIPE-RU\n")

    with open(OUTPUT_TIMEOUT, "w") as f:
        for p in prefixes:
            f.write(f"/ip firewall address-list add list=RU address={p} comment=RIPE-RU timeout=2592000\n")

    print(f"Generated {count} prefixes -> {OUTPUT}, {OUTPUT_TIMEOUT}")


if __name__ == "__main__":
    main()
