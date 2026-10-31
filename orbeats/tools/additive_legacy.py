"""Compatibility metadata for the two pre-manifest native library entries.

These descriptors mirror the already-public include/additive_library_profile.h;
no song, game asset or development fixture is distributed. They are NOT proof
of installation: callers must verify every remote bundle/cover/preview before
migrating. Return fresh objects so management cannot mutate shared defaults.
"""


def migration_songs():
    return [
        {
            "id": "bsd_additive_e3195d81452f3550696b607c",
            "title": "Wake Me Up",
            "author": "Avicii",
            "sha256": "305d527c61902fb069f37e63b2223ef74ada5cf65cac1636f1c502e543741fa6",
            "bytes": 44181622,
            "fnv": 0x48C20BF1C7FB2BE,
            "bpm": 124.0,
            "duration": 249.43249433106575,
            "preview_duration": 10,
            "mask": 31,
            "stats": [
                [312, 0, 15, 11, 1],
                [438, 12, 3, 10, 0],
                [709, 108, 13, 12, 0],
                [1118, 0, 0, 14, 0],
                [1311, 120, 14, 18, 0],
            ],
            "cover": {"bytes": 617420, "fnv": 0x1AB799B728D9A5D5},
            "preview": {"bytes": 1764078, "fnv": 0xBB80CD0DA9FCC60E},
        },
        {
            "id": "bsd_additive_376607927402e50fcf6ab89f",
            "title": "Cities",
            "author": "Throttle",
            "sha256": "5a25da74a66eacd36bb2f50546c24e29f49e703684ae417b32957e80d17f2d01",
            "bytes": 32237054,
            "fnv": 0xD0C45C91C5E83670,
            "bpm": 114.0,
            "duration": 181.81086167800453,
            "preview_duration": 20,
            "mask": 28,
            "stats": [
                [0, 0, 0, 0, 0],
                [0, 0, 0, 0, 0],
                [189, 0, 289, 11, -0.532],
                [350, 0, 311, 12.5, -0.784],
                [414, 0, 331, 14, -0.982],
            ],
            "cover": {"bytes": 127966, "fnv": 0x7EA22112FD1F6520},
            "preview": {"bytes": 3528078, "fnv": 0x77C08E480E6E56E8},
        },
    ]
