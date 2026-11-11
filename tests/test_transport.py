from datetime import datetime

from deplacements import transport

LINE = "line:IDFM:C01742"


def disruption(text, kind, begin, end, obj_id=LINE):
    return {"messages": [{"text": text}],
            "application_periods": [{"begin": begin, "end": end}],
            "impacted_objects": [{"pt_object": {"embedded_type": kind, "id": obj_id, "name": "RER A"}}]}


def test_get_disruptions_keeps_only_active_line_level(monkeypatch):
    reports = {"disruptions": [
        disruption("Trafic interrompu", "line", "20261127T060000", "20261127T120000"),
        disruption("Ascenseur en panne", "stop_area", "20261127T060000", "20261127T120000", "sa:1"),
        disruption("Travaux terminés", "line", "20261101T000000", "20261102T000000"),
    ]}
    monkeypatch.setattr(transport, "_get", lambda path, params=None: reports)
    found = transport.get_disruptions(LINE, datetime(2026, 11, 27, 9, 0))
    assert [d["message"] for d in found] == ["Trafic interrompu"]
