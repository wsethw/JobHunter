from __future__ import annotations

from decimal import Decimal

from app.parsers import (
    parse_contract_type,
    parse_location,
    parse_salary,
    parse_seniority,
    parse_stack,
)


def test_parse_salary_ranges_and_currency() -> None:
    salary = parse_salary("Salário: R$ 10.000,00 - R$ 15.500,00")
    assert salary.salary_currency == "BRL"
    assert salary.salary_min == Decimal("10000.00")
    assert salary.salary_max == Decimal("15500.00")


def test_parse_salary_single_usd_and_empty() -> None:
    salary = parse_salary("USD 9000")
    assert salary.salary_currency == "USD"
    assert salary.salary_min == Decimal("9000.00")
    assert parse_salary("").salary_min is None


def test_parse_location_remote_hybrid_onsite_and_city() -> None:
    remote = parse_location(None, "100% remoto para Brazil")
    assert remote.remote_type == "remote"
    assert remote.country == "Brazil"
    assert remote.normalized_location == "Remote"

    hybrid = parse_location("São Paulo, Brasil", "híbrido")
    assert hybrid.remote_type == "hybrid"
    assert hybrid.city == "São Paulo"

    onsite = parse_location("Lisbon, Portugal", "presencial")
    assert onsite.remote_type == "onsite"
    assert onsite.country == "Portugal"


def test_parse_contract_type() -> None:
    assert parse_contract_type(["Contrato PJ"]) == "pj"
    assert parse_contract_type(["CLT full-time"]) == "clt"
    assert parse_contract_type(["freelancer"]) == "freelancer"
    assert parse_contract_type(["estágio"]) == "internship"
    assert parse_contract_type(["sem informação"]) is None


def test_parse_seniority() -> None:
    assert parse_seniority(["Pessoa Desenvolvedora Sênior"]) == "senior"
    assert parse_seniority(["mid-level backend"]) == "pleno"
    assert parse_seniority(["trainee python"]) == "junior"
    assert parse_seniority(["backend"]) is None


def test_parse_stack() -> None:
    stack = parse_stack(["Python com Django Rest Framework, PostgreSQL e CI CD"], ["Django"])
    assert {"Python", "Django", "PostgreSQL", "CI/CD"}.issubset(set(stack))
