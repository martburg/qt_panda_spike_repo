from __future__ import annotations

from dataclasses import dataclass

from steuerung3d.core.joy_facts import JoyFacts, extract_joy_facts


@dataclass
class JoyLike:
    deadman: bool = False
    select_hip: bool = False
    soll_speed: float = 0.0


@dataclass
class JoyLegacy:
    deadman: bool = False
    select: bool = False
    soll_speed: float = 0.0


def test_extract_joy_facts_none() -> None:
    assert extract_joy_facts(None) == JoyFacts()


def test_extract_joy_facts_select_hip() -> None:
    jf = extract_joy_facts(JoyLike(deadman=True, select_hip=True, soll_speed=0.25))
    assert jf.deadman is True
    assert jf.select_hip is True
    assert abs(jf.soll_speed - 0.25) < 1e-12


def test_extract_joy_facts_legacy_select() -> None:
    jf = extract_joy_facts(JoyLegacy(deadman=True, select=True, soll_speed=1.0))
    assert jf.deadman is True
    assert jf.select_hip is True
    assert abs(jf.soll_speed - 1.0) < 1e-12
