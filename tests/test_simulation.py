"""Chaque scénario de simulation.py est aussi un test de bout en bout (vrai code, fausses API)."""
import pytest

import simulation


@pytest.fixture(autouse=True)
def no_real_position():
    """Remplace celui de conftest.py : la simulation fournit déjà ses fausses positions."""


@pytest.mark.parametrize("scenario", simulation.SCENARIOS, ids=lambda s: s.title)
def test_scenario(scenario):
    answer = simulation.run_scenario(scenario)
    for expected in scenario.expect:
        assert expected in answer


def test_simulation_leaves_nothing_patched():
    """Après un scénario, les vraies fonctions sont remises en place."""
    real_get = simulation.transport._get
    simulation.run_scenario(simulation.SCENARIOS[0])
    assert simulation.transport._get is real_get


def test_simulation_command_reports_success(capsys):
    assert simulation.simulate() == 0
    assert f"{len(simulation.SCENARIOS)}/{len(simulation.SCENARIOS)} scénarios conformes" in capsys.readouterr().out
