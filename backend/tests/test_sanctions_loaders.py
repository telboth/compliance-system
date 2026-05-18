"""Tester for parserne i sanctions/loaders."""

from __future__ import annotations

from app.sanctions.loaders.eu import parse_eu_count
from app.sanctions.loaders.ofac import parse_ofac_count
from app.sanctions.loaders.un import parse_un_count


def test_parse_un_count_handles_individual_and_entity() -> None:
    payload = b"""
    <CONSOLIDATED_LIST>
      <INDIVIDUAL />
      <ENTITY />
      <ENTITY />
    </CONSOLIDATED_LIST>
    """
    assert parse_un_count(payload) == 3


def test_parse_eu_count_handles_default_namespace() -> None:
    payload = b"""
    <export xmlns="http://eu.europa.ec/fpi/fsd/export">
      <sanctionEntity logicalId="1" />
      <sanctionEntity logicalId="2" />
    </export>
    """
    assert parse_eu_count(payload) == 2


def test_parse_eu_count_fallback_for_generic_tags() -> None:
    payload = b"""
    <root>
      <entity />
      <person />
      <person />
    </root>
    """
    assert parse_eu_count(payload) == 3


def test_parse_ofac_count_excludes_header() -> None:
    payload = b"id,name\n1,ACME\n2,FOO\n"
    assert parse_ofac_count(payload) == 2
