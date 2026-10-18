# Entre Terras

<img src="entre_terras/assets/entre-terras.png" alt="Ícone Entre Terras" width="96">

Contador visual de mortes para **Elden Ring no Windows**, com histórico de chefes, atalhos globais e contador sobreposto no jogo pelo RivaTuner Statistics Server (RTSS).

O reconhecimento compara a mensagem vermelha de morte com uma imagem de referência. Não utiliza OCR, Tesseract ou um modelo de IA treinado.

## Recursos

- Contador geral e sessões independentes por chefe.
- Histórico com datas, resultado, edição e exportação CSV.
- Até seis chefes do histórico fixados no contador do jogo.
- Texto personalizável com prévia.
- Atalhos globais configuráveis, sem hook de teclado.
- Ícone na bandeja e execução em segundo plano.
- Inicialização do RTSS antes do contador e encerramento conjunto.
- Salvamento automático com backup e recuperação.

## Requisitos

- Windows 10 ou 11 de 64 bits.
- RTSS instalado, normalmente junto com o MSI Afterburner.
- Python 3.11 ou superior para executar o código ou gerar o executável.

O executável não requer Python instalado. O Windows solicita permissão de administrador para iniciar e encerrar o RTSS. Abra o contador antes do jogo para permitir que o RTSS detecte o processo.

## Como executar

### Executável

Depois de gerar o aplicativo, abra `dist/EntreTerras/EntreTerras.exe`. Mantenha a pasta `_internal` junto dele. Os dados ficam em `data/` ao lado do executável.

Na pasta do projeto, `iniciar.bat` usa o executável existente quando disponível e mantém os dados em `data/` na raiz. O atalho local **Entre Terras**, quando presente, também usa esse histórico.

### Código-fonte

Dê dois cliques em `iniciar.bat`. Sem executável, ele cria o ambiente virtual e instala as dependências ausentes. Para configurar manualmente no PowerShell:

```powershell
python -m venv venv_eldenring
.\venv_eldenring\Scripts\python.exe -m pip install -r requirements.txt
.\venv_eldenring\Scripts\python.exe -m entre_terras
```

Esse comando usa `data/` na raiz do checkout. Para escolher outra pasta, passe `--data-dir caminho`.

## Bandeja e encerramento

O aplicativo começa na bandeja, nos ícones perto do relógio. O Windows pode colocá-lo dentro da setinha de ícones ocultos.

- **Duplo clique** ou **Abrir painel** mostra a janela.
- **Minimizar** ou **X** esconde a janela, mantendo o contador ativo.
- **Pausar / retomar detecção** suspende ou retoma captura e reconhecimento.
- **Encerrar contador e RTSS** salva os dados, remove o texto do jogo e fecha os dois.

O botão **Encerrar** do painel também fecha o RTSS, inclusive se ele já estava aberto antes do contador. Apenas uma instância pode usar a mesma pasta de dados. Use `--show` para iniciar com o painel visível.

## Contagens e chefes

Uma morte detectada aumenta o total geral e o chefe ativo. Correções manuais alteram somente o contador selecionado. Encerrar uma sessão não recalcula o total geral.

Inicie uma sessão pelo nome do chefe e finalize com **Chefe vencido • salvar** ou **Arquivar sem vitória**. A vitória é informada manualmente; não há reconhecimento automático da derrota do chefe.

Em **Texto no jogo**, personalize as linhas com `{total}`, `{nome}` e `{mortes}`:

```text
Jornada = {total}
{nome} = {mortes}
```

## Atalhos padrão

| Ação | Atalho |
| --- | --- |
| Geral: aumentar / diminuir / zerar | Ctrl+Alt+PageUp / PageDown / Home |
| Chefe: aumentar / diminuir / zerar | Ctrl+Shift+PageUp / PageDown / Home |
| Pausar / retomar | Ctrl+Alt+P |
| Chefe vencido | Ctrl+Alt+End |

Configure os atalhos no painel; deixe um campo vazio para desativá-lo. Zerar e encerrar chefe pelos atalhos executam imediatamente. Atalhos são ignorados durante diálogos de edição.

## Captura e desempenho

O backend padrão solicita screenshots BMP pelo protocolo de memória compartilhada do RTSS. As imagens temporárias são lidas, recortadas e descartadas. Não há gravação de vídeo.

O padrão é **duas consultas por segundo**. Depois de confirmar uma morte, cai para uma consulta por segundo até a mensagem desaparecer. O reconhecimento trabalha em imagens reduzidas para 320 pixels de largura e usa uma thread do OpenCV. Pausar suspende novas capturas; uma captura já solicitada ainda pode terminar.

Duas imagens positivas confirmam uma morte. São necessários dois segundos sem a mensagem para rearmar o contador. A frequência pode ser ajustada entre 1 e 15. O impacto depende da resolução, do hardware e do RTSS; não há garantia de ausência de travadas.

O backend alternativo `dxgi` evita arquivos BMP temporários, mas pode falhar em tela cheia exclusiva. Nesta versão, o texto no jogo está vinculado ao backend RTSS.

A referência incluída reconhece a mensagem em português. Outro idioma exige uma referência recortada da mensagem vermelha. Precisão em partidas, HDR e diferentes configurações de vídeo precisam ser validados no jogo.

## Diagnóstico

```powershell
.\iniciar.bat --show
.\iniciar.bat --check
.\iniciar.bat --debug
.\iniciar.bat --fps 2
.\iniciar.bat --threshold 0.75
.\iniciar.bat --capture dxgi --monitor 0
.\iniciar.bat --reference caminho\mensagem.png
.\iniciar.bat --data-dir caminho\dados
```

`--check` tenta receber uma imagem por até oito segundos, sem alterar os dados; abra o RTSS antes desse diagnóstico. `--debug` mostra a região analisada. `--monitor` só se aplica ao DXGI e começa em zero. Aumentar `--threshold` reduz falsos positivos, mas pode perder detecções.

Os argumentos substituem os valores carregados e, na execução normal, podem ser persistidos pelo salvamento automático.

Se aparecer **Aguardando jogo no RTSS**, confira o perfil do jogo e reinicie o Elden Ring com o RTSS aberto. O OSD deve estar ativado no RTSS.

## Dados e privacidade

| Arquivo | Conteúdo |
| --- | --- |
| `data/state.json` | Contagens, sessões, configurações e atalhos |
| `data/state.json.bak` | Versão anterior válida |
| `data/app.log` | Erros quando executado sem terminal |

Use **Abrir pasta dos dados** para localizar seu histórico e fazer uma cópia. Arquivos pessoais, ambientes virtuais e builds são ignorados pelo Git.

O código acessa a memória compartilhada do RTSS e imagens capturadas; não abre a memória do jogo nem modifica seus arquivos. O RTSS usa seu próprio hook de renderização. Isso não garante aceitação por sistemas anticheat.

## Desenvolvimento

```powershell
.\venv_eldenring\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv_eldenring\Scripts\python.exe -m unittest discover -s tests -v
.\gerar_executavel.bat
```

O build é definido em `EntreTerras.spec`. Os testes de interface simulam os serviços de captura e atalhos; a suíte não substitui validação durante uma partida. O GitHub Actions executa os testes no Windows.

```text
entre_terras/
  app.py                  Entrada e inicialização
  desktop_integration.py  Bandeja e ciclo de vida do RTSS
  global_hotkeys.py       Atalhos globais
  rtss_capture.py         Captura e OSD
  tracker_runtime.py      Worker de captura e detecção
  tracker_state.py        Contagens e persistência
  tracker_ui.py           Painel Tkinter
  vision.py               Reconhecimento visual
  assets/                 Ícones e referência da mensagem
tests/                    Testes automatizados
.github/workflows/        Integração contínua
EntreTerras.spec           Empacotamento Windows
elden_ring_tracker.py      Inicializador de compatibilidade
iniciar.bat               Inicialização local
gerar_executavel.bat       Geração do executável
```

## Licença

O código deste projeto é distribuído sob a [licença MIT](LICENSE). Elden Ring e RivaTuner Statistics Server pertencem aos respectivos titulares; a licença do projeto não concede direitos sobre conteúdo de terceiros. Este é um projeto independente, sem afiliação oficial.
