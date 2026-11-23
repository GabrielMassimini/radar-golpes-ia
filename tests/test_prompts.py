"""Testes do carregador de prompts (radar/prompts.py). Não usam API nenhuma."""

import pytest

from radar.prompts import (
    VERSAO_PADRAO,
    Prompt,
    carregar_prompt,
    montar_mensagem,
    versoes_disponiveis,
)

TEMPLATE = Prompt("v9", "sistema", "Pistas:\n{sinais}\n\n<conteudo>\n{conteudo}\n</conteudo>")


def _criar_versao(pasta, nome, system, user):
    (pasta / nome).mkdir()
    (pasta / nome / "system.md").write_text(system, encoding="utf-8")
    (pasta / nome / "user.md").write_text(user, encoding="utf-8")


def test_versao_padrao_existe_no_projeto():
    prompt = carregar_prompt(VERSAO_PADRAO)
    assert prompt.system
    assert "<conteudo_analisado>\n{conteudo}\n</conteudo_analisado>" in prompt.user


def test_lista_versoes_em_ordem_numerica(tmp_path):
    for nome in ("v10", "v2", "v1"):
        _criar_versao(tmp_path, nome, "s", "{conteudo}")
    (tmp_path / "rascunho").mkdir()  # pasta fora do padrão é ignorada
    assert versoes_disponiveis(tmp_path) == ["v1", "v2", "v10"]


def test_monta_conteudo_e_sinais():
    mensagem = montar_mensagem(TEMPLATE, "Pix antes do envio", "- pagamento_antecipado")
    assert mensagem == "Pistas:\n- pagamento_antecipado\n\n<conteudo>\nPix antes do envio\n</conteudo>"


def test_conteudo_com_chaves_nao_quebra():
    conteudo = 'Olá {nome}, seu código é {}. JSON: {"a": 1}'
    assert conteudo in montar_mensagem(TEMPLATE, conteudo)


def test_conteudo_que_imita_os_espacos_nao_e_substituido_de_novo():
    # Quem escreve "{sinais}" no próprio texto não consegue injetar nada.
    mensagem = montar_mensagem(TEMPLATE, "texto com {sinais} e {conteudo}", "PISTA")
    assert "texto com {sinais} e {conteudo}" in mensagem
    assert mensagem.count("PISTA") == 1


def test_sinais_com_chaves_nao_puxam_o_conteudo():
    mensagem = montar_mensagem(TEMPLATE, "CONTEUDO", 'Trecho: "{conteudo}"')
    assert mensagem.count("CONTEUDO") == 1


def test_template_sem_sinais_funciona():
    prompt = Prompt("v1", "s", "Isso é golpe?\n\n{conteudo}")
    assert montar_mensagem(prompt, "oi", "ignorado") == "Isso é golpe?\n\noi"


@pytest.mark.parametrize("versao", ["../../.env", "v1/../v2", "V1", "1", ""])
def test_recusa_versao_fora_do_formato(versao):
    with pytest.raises(ValueError, match="inválida"):
        carregar_prompt(versao)


def test_versao_inexistente_lista_as_disponiveis(tmp_path):
    _criar_versao(tmp_path, "v1", "s", "{conteudo}")
    with pytest.raises(ValueError, match="Disponíveis: v1"):
        carregar_prompt("v99", tmp_path)


def test_user_sem_espaco_de_conteudo_da_erro(tmp_path):
    _criar_versao(tmp_path, "v1", "s", "Isso é golpe?")
    with pytest.raises(ValueError, match="conteudo"):
        carregar_prompt("v1", tmp_path)


def test_conteudo_fora_das_marcacoes_da_erro(tmp_path):
    # Sem as marcações, o modelo (e o mock) não sabe onde o texto do usuário começa.
    _criar_versao(tmp_path, "v1", "s", "Isso é golpe?\n\n{conteudo}")
    with pytest.raises(ValueError, match="conteudo_analisado"):
        carregar_prompt("v1", tmp_path)


def test_marcacoes_aceitam_espacos_em_volta(tmp_path):
    _criar_versao(tmp_path, "v1", "s", "<conteudo_analisado>{conteudo}</conteudo_analisado>")
    assert carregar_prompt("v1", tmp_path).versao == "v1"