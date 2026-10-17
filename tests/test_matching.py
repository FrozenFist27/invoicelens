"""Matching + P/R maths tests."""

from eval.matching import (
    match_currency,
    match_date,
    match_doc_number,
    match_line_items,
    match_money,
    match_supplier,
    normalize_string,
    norm_doc_number,
    prf,
)


def test_normalize_string():
    assert normalize_string("  ACME, Ltd. ") == "acme ltd"


def test_norm_doc_number():
    assert norm_doc_number("INV #1001") == "INV1001"


def test_match_supplier_fuzzy():
    assert match_supplier("ACME Supplies Ltd", "acme supplies ltd")
    assert not match_supplier("ACME", "Globex")


def test_match_doc_number():
    # strips spaces and # (not dashes), case-insensitive
    assert match_doc_number("INV #1001", "inv #1001")
    assert match_doc_number("INV1001", "inv1001")
    assert not match_doc_number("INV-1001", "INV-1002")


def test_match_date():
    assert match_date("2026-03-04", "2026-03-04")
    assert not match_date("2026-03-04", "2026-03-05")


def test_match_money():
    assert match_money("22.00", 22.0)
    assert match_money(22.001, 22.0)  # within 0.01
    assert not match_money(22.03, 22.0)


def test_match_currency():
    assert match_currency("usd", "USD")
    assert not match_currency("eur", "USD")


def test_line_items_perfect():
    pred = [{"description": {"value": "Widget"}, "quantity": {"value": 2}, "unit_price": {"value": 10.0}, "amount": {"value": 20.0}}]
    label = [{"description": "Widget", "quantity": 2, "unit_price": 10.0, "amount": 20.0}]
    r = match_line_items(pred, label)
    assert r["tp"] == 4 and r["fp"] == 0 and r["fn"] == 0


def test_line_items_wrong_amount():
    pred = [{"description": {"value": "Widget"}, "quantity": {"value": 2}, "unit_price": {"value": 10.0}, "amount": {"value": 99.0}}]
    label = [{"description": "Widget", "quantity": 2, "unit_price": 10.0, "amount": 20.0}]
    r = match_line_items(pred, label)
    assert r["sub"]["amount"]["fp"] == 1
    assert r["sub"]["amount"]["fn"] == 1


def test_line_items_missing():
    pred = []
    label = [{"description": "Widget", "quantity": 2, "unit_price": 10.0, "amount": 20.0}]
    r = match_line_items(pred, label)
    assert r["fn"] == 4


def test_prf_maths():
    r = prf(8, 2, 2)
    assert r["precision"] == 0.8
    assert r["recall"] == 0.8
    assert abs(r["f1"] - 0.8) < 1e-9


def test_prf_zero():
    assert prf(0, 0, 0)["precision"] == 0.0
