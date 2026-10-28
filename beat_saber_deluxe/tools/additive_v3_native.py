"""Lossless supported V3 -> native V4 indexed chart/lightshow representation.

Keep beat-domain distributions and sample BPM regions; never retime only a box
start under changing tempo. No inferred light-group membership or mod support.
"""

from additive_v4_native import audio, chart, lighting, obj, rows


def convert(data, audio_data, njs):
    keys = (
        "version",
        "colorNotes",
        "bombNotes",
        "obstacles",
        "sliders",
        "burstSliders",
        "bpmEvents",
        "basicBeatmapEvents",
        "colorBoostBeatmapEvents",
        "lightColorEventBoxGroups",
        "lightRotationEventBoxGroups",
        "lightTranslationEventBoxGroups",
        "vfxEventBoxGroups",
        "_fxEventsCollection",
        "basicEventTypesWithKeywords",
        "useNormalEventsAsCompatibleEvents",
        "customData",
        "_customData",
        "rotationEvents",
        "waypoints",
    )
    obj(data, keys, "V3 source")
    if (
        not str(data.get("version", "")).startswith("3.")
        or data.get("_customData")
        or data.get("rotationEvents")
        or data.get("waypoints")
    ):
        raise ValueError("native conversion requires unrotated vanilla V3 source")
    custom = data.get("customData", {})
    obj(custom, ("lighter", "time", "bookmarks", "bookmarksUseOfficialBpmEvents"), "editor metadata")
    out, light = {"version": "4.1.0"}, {"version": "4.0.0"}
    if data.get("basicEventTypesWithKeywords", {}) not in ({}, {"d": []}):
        raise ValueError("native conversion does not yet support light keywords")
    light["useNormalEventsAsCompatibleEvents"] = data.get("useNormalEventsAsCompatibleEvents", False)

    def add(target, key, value):
        table = target.setdefault(key, [])
        table.append(value)
        return len(table) - 1

    for key, fields in [
        ("colorNotes", ("x", "y", "c", "d", "a")),
        ("bombNotes", ("x", "y")),
        ("obstacles", ("x", "y", "d", "w", "h")),
    ]:
        for event in rows(data.get(key, []), key):
            obj(event, ("b", *fields), key)
            idx = add(out, key + "Data", {k: event.get(k, 0) for k in fields})
            add(out, key, {"b": event.get("b", 0), "i": idx})
    for event in rows(data.get("sliders", []), "V3 arcs"):
        obj(event, ("b", "c", "x", "y", "d", "mu", "tb", "tx", "ty", "tc", "tmu", "m"), "V3 arc")
        hi = add(out, "colorNotesData", {k: event.get(k, 0) for k in ("x", "y", "c", "d")})
        ti = add(
            out,
            "colorNotesData",
            dict(x=event.get("tx", 0), y=event.get("ty", 0), c=event.get("c", 0), d=event.get("tc", 0)),
        )
        ai = add(out, "arcsData", dict(m=event.get("mu", 0), tm=event.get("tmu", 0), a=event.get("m", 0)))
        add(out, "arcs", dict(hb=event.get("b", 0), tb=event.get("tb", 0), hi=hi, ti=ti, ai=ai))
    for event in rows(data.get("burstSliders", []), "V3 chains"):
        obj(event, ("b", "c", "x", "y", "d", "tb", "tx", "ty", "sc", "s"), "V3 chain")
        i = add(out, "colorNotesData", {k: event.get(k, 0) for k in ("x", "y", "c", "d")})
        ci = add(
            out,
            "chainsData",
            dict(tx=event.get("tx", 0), ty=event.get("ty", 0), c=event.get("sc", 0), s=event.get("s", 0)),
        )
        add(out, "chains", dict(hb=event.get("b", 0), tb=event.get("tb", 0), i=i, ci=ci))
    for key, table, fields in [
        ("basicBeatmapEvents", "basicEvents", ("et", "i", "f")),
        ("colorBoostBeatmapEvents", "colorBoostEvents", ("o",)),
    ]:
        for event in rows(data.get(key, []), key):
            obj(event, ("b", *fields), key)
            if key == "colorBoostBeatmapEvents":
                if type(event.get("o", False)) is not bool:
                    raise ValueError("invalid V3 boost boolean")
                metadata = {"b": int(event.get("o", False))}
            else:
                metadata = dict(t=event.get("et", 0), i=event.get("i", 0), f=event.get("f", 0))
            idx = add(light, table + "Data", metadata)
            add(light, table, dict(b=event.get("b", 0), i=idx))
    fx = data.get("_fxEventsCollection", {})
    obj(fx, ("_fl", "_il"), "V3 FX collection")
    if fx.get("_il"):
        raise ValueError("integer FX has no reviewed V4 target; refusing loss")
    for kind, key in enumerate(
        (
            "lightColorEventBoxGroups",
            "lightRotationEventBoxGroups",
            "lightTranslationEventBoxGroups",
            "vfxEventBoxGroups",
        ),
        1,
    ):
        box_key, event_key = {
            1: ("lightColorEventBoxes", "lightColorEvents"),
            2: ("lightRotationEventBoxes", "lightRotationEvents"),
            3: ("lightTranslationEventBoxes", "lightTranslationEvents"),
            4: ("fxEventBoxes", "floatFxEvents"),
        }[kind]
        for group in rows(data.get(key, []), key, 20000):
            obj(group, ("b", "g", "e", "t") if kind == 4 else ("b", "g", "e"), "V3 group")
            if kind == 4 and group.get("t", 0) != 1:
                raise ValueError("nonfloat V3 FX requires native V3 preservation")
            event_boxes = []
            converted = dict(b=group.get("b", 0), g=group.get("g", 0), t=kind, e=event_boxes)
            for box in rows(group.get("e", []), "V3 boxes", 1024):
                fields = (
                    ("f", "w", "d", "t", "b", "i", "r", "e")
                    if kind == 1
                    else ("f", "w", "d", "s", "t", "b", "i", "a", "r", "l")
                    if kind in (2, 3)
                    else ("f", "w", "d", "s", "t", "b", "i", "l")
                )
                obj(box, fields, "V3 box")
                filter_id = add(light, "indexFilters", box.get("f", {}))
                metadata = {k: box.get(k, 0) for k in ("w", "d", "t", "b")}
                metadata.update(s=box.get("r" if kind == 1 else "s", 0), e=box.get("i", 0))
                if kind in (2, 3):
                    metadata.update(a=box.get("a", 0), f=box.get("r", 0))
                box_id = add(light, box_key, metadata)
                events = []
                for event in rows(box.get("e" if kind == 1 else "l", []), "V3 box events", 20000):
                    if kind == 4:
                        from additive_v4_native import index

                        event = index(event, fx.get("_fl", []), "V3 float FX")
                    allowed = (
                        ("b", "i", "c", "s", "f", "sb", "sf")
                        if kind == 1
                        else ("b", "p", "e", "l", "r", "o")
                        if kind == 2
                        else ("b", "p", "e", "t")
                        if kind == 3
                        else ("b", "p", "i", "v")
                    )
                    obj(event, allowed, "V3 base event")
                    if kind == 1:
                        transition = event.get("i", 0)
                        if type(transition) is not int or transition not in (0, 1, 2):
                            raise ValueError("invalid V3 color transition")
                        record = {k: event.get(k, 0) for k in ("c", "f", "sb", "sf")}
                        record.update(p=int(transition == 2), e=-1 if transition == 0 else 0, b=event.get("s", 0))
                    else:
                        record = {k: v for k, v in event.items() if k != "b"}
                        if kind == 2:
                            record["d"] = record.pop("o", 0)
                        if kind == 4:
                            record["e"] = record.pop("i", 0)
                    idx = add(light, event_key, record)
                    events.append(dict(b=event.get("b", 0), i=idx))
                event_boxes.append(dict(f=filter_id, e=box_id, l=events))
            add(light, "eventBoxGroups", converted)
    maxbeat = audio(audio_data)
    chart(out, maxbeat, njs)
    lighting(light, maxbeat)
    return out, light


def audio_from_tempo(tempo, samples, rate=44100):
    duration = samples / rate
    regions = []
    for i, (beat, sec, bpm) in enumerate(zip(tempo.beats, tempo.seconds, tempo.bpms)):
        if sec >= duration:
            break
        end_sec = min(duration, tempo.seconds[i + 1] if i + 1 < len(tempo.seconds) else duration)
        regions.append(
            dict(si=round(sec * rate), ei=round(end_sec * rate), sb=beat, eb=beat + (end_sec - sec) * bpm / 60)
        )
    result = dict(version="4.0.0", songSampleCount=samples, songFrequency=rate, bpmData=regions)
    audio(result)
    return result


def validate_preserved(data, audio_data, njs):
    """Native V3 rotation events keep their own early/late execution semantics."""
    import copy

    from additive_v4_native import number

    maxbeat = audio(audio_data)
    for event in rows(data.get("rotationEvents", []), "rotation events", 20000):
        obj(event, ("b", "e", "r"), "rotation event")
        number(event.get("b", 0), "rotation beat", 0, maxbeat)
        number(event.get("e", 0), "rotation execution time", 0, 1, True)
        number(event.get("r", 0), "rotation angle", -360, 360)
    from additive_v4_native import index, scalar_record

    effects = data.get("_fxEventsCollection", {})
    obj(effects, ("_il", "_fl"), "V3 FX collection")
    total = 0
    for table in ("_il", "_fl"):
        schema = dict(b=(0, maxbeat, False), p=(0, 1, True), v=(-100000, 100000, table == "_il"))
        if table == "_fl":
            schema["i"] = (-1, 102, True)
        for event in rows(effects.get(table, []), table):
            scalar_record(event, schema, table)
        total += len(effects.get(table, []))
    for group in rows(data.get("vfxEventBoxGroups", []), "V3 FX groups", 20000):
        obj(group, ("b", "g", "e", "t"), "V3 FX group")
        scalar_record(
            {k: v for k, v in group.items() if k != "e"},
            dict(b=(0, maxbeat, False), g=(0, 1023, True), t=(0, 2, True)),
            "V3 FX group",
        )
        kind = group.get("t", 0)
        table = effects.get("_fl" if kind == 1 else "_il", [])
        for box in rows(group.get("e", []), "V3 FX boxes", 1024):
            obj(box, ("f", "w", "d", "s", "t", "b", "i", "l"), "V3 FX box")
            scalar_record(
                {k: v for k, v in box.items() if k not in ("f", "l")},
                dict(
                    w=(0, maxbeat, False),
                    d=(0, 2, True),
                    s=(-10000, 10000, False),
                    t=(0, 2, True),
                    b=(0, 1, True),
                    i=(-1, 102, True),
                ),
                "V3 FX box",
            )
            scalar_record(
                box.get("f", {}),
                dict(
                    f=(0, 2, True),
                    p=(0, 100000, True),
                    t=(0, 100000, True),
                    r=(0, 1, True),
                    c=(0, 100000, True),
                    n=(0, 3, True),
                    s=(-2147483648, 2147483647, True),
                    l=(0, 1, False),
                    d=(0, 3, True),
                ),
                "V3 FX filter",
            )
            for ref in rows(box.get("l", []), "V3 FX references", 20000):
                event = index(ref, table, "V3 FX")
                number(group.get("b", 0) + event.get("b", 0), "absolute FX beat", 0, maxbeat)
                if kind == 2:
                    number(event.get("v", 0), "boolean FX value", 0, 1, True)
                total += 1
            total += 1
        total += 1
    if total > 400000:
        raise ValueError("native V3 FX budget exceeded")
    checked = copy.deepcopy(data)
    checked.pop("vfxEventBoxGroups", None)
    checked.pop("_fxEventsCollection", None)
    checked.pop("rotationEvents", None)
    converted, converted_light = convert(checked, audio_data, njs)
    return chart(converted, maxbeat, njs), bool(converted_light.get("eventBoxGroups") or data.get("vfxEventBoxGroups"))


def lightshow_preserved(data):
    keys = (
        "basicBeatmapEvents",
        "colorBoostBeatmapEvents",
        "lightColorEventBoxGroups",
        "lightRotationEventBoxGroups",
        "lightTranslationEventBoxGroups",
        "vfxEventBoxGroups",
        "_fxEventsCollection",
        "basicEventTypesWithKeywords",
        "useNormalEventsAsCompatibleEvents",
    )
    return dict(version=data["version"], **{k: data[k] for k in keys if k in data})
