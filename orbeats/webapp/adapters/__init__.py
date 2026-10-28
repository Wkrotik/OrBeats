# Web app adapters — ONE module per pipeline subsystem (plan §3).
# Thin-layer rule (plan §9.4 invariant 1): read-only helpers may be imported;
# anything that deploys, mutates PS4 state, or runs long = subprocess.
