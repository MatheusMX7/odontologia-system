from datetime import date

import pytest

from app.core.validators import calc_age, is_valid_cpf, validate_password


@pytest.mark.parametrize("cpf", ["529.982.247-25", "52998224725", "111.444.777-35"])
def test_cpf_valido(cpf):
    assert is_valid_cpf(cpf)


@pytest.mark.parametrize("cpf", ["111.111.111-11", "12345678900", "5299822472", "abc", "", "529.982.247-26"])
def test_cpf_invalido(cpf):
    assert not is_valid_cpf(cpf)


def test_idade_calculada_pela_data_de_nascimento():
    assert calc_age(date(2000, 6, 15), date(2024, 6, 14)) == 23
    assert calc_age(date(2000, 6, 15), date(2024, 6, 15)) == 24
    assert calc_age(date(2000, 2, 29), date(2023, 2, 28)) == 22


@pytest.mark.parametrize("pwd", ["curta1", "somenteletras", "12345678"])
def test_senha_fraca(pwd):
    with pytest.raises(ValueError):
        validate_password(pwd)


def test_senha_forte():
    assert validate_password("Senha1234") == "Senha1234"
