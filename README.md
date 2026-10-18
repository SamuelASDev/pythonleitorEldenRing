# Entre Terras — contador de mortes do Elden Ring

No Windows, dê dois cliques em **iniciar.bat**. O inicializador cria o ambiente virtual e instala dependências que estiverem faltando. Depois inicia o RTSS e coloca o contador na bandeja do Windows, sem manter uma janela de terminal. O Windows solicita permiss?o de administrador para gerenciar o RTSS. Requer Python; não precisa de Tesseract.

## Painel de controle

- **Jornada:** contador geral independente; botões para aumentar, diminuir, zerar ou definir um valor. Inicie uma sessão pelo nome do chefe e marque **Chefe vencido • salvar** ao terminar, ou arquive sem vitória.
- **Chefes e histórico:** registros com mortes, datas e resultado. Edite nomes e contagens, fixe até 6 registros no jogo e exporte o histórico em CSV.
- **Texto no jogo:** personalize o texto com prévia. O geral sempre aparece primeiro; chefe ativo e chefes fixados vêm abaixo. Exemplos: `Jornada = {total}` e `{nome} = {mortes}`. Um nome literal, como `Margit = {mortes}`, também funciona.
- **Atalhos e detecção:** configure atalhos globais, frequência, sensibilidade e confirmação da mensagem. Deixe um atalho vazio para desativá-lo. Se a combinação já estiver em uso, o programa avisa e mantém as configurações anteriores.

Uma morte detectada aumenta o geral e o chefe ativo. Edições manuais alteram **somente o contador selecionado**. Encerrar um chefe não zera nem corrige o geral. O total geral não é recalculado como a soma do histórico.

**Pausar detecção** suspende novas capturas, o reconhecimento e os incrementos automáticos; as correções manuais continuam disponíveis. A vitória é marcada manualmente pelo botão ou atalho; esta versão não reconhece a derrota do chefe automaticamente.

Minimize pelo botão ou pela barra do Windows: captura, OSD e atalhos continuam ativos. Fechar a janela ou clicar em **Encerrar** salva os dados, desregistra os atalhos e remove o texto do jogo. A janela pode ser restaurada pela barra de tarefas. Apenas uma instância por pasta de dados pode ser aberta.

## Atalhos iniciais

| Ação | Atalho |
| --- | --- |
| Geral: +1 / −1 / zerar | Ctrl+Alt+PageUp / PageDown / Home |
| Chefe ativo: +1 / −1 / zerar | Ctrl+Shift+PageUp / PageDown / Home |
| Pausar / retomar detecção | Ctrl+Alt+P |
| Chefe vencido: salvar e encerrar sessão | Ctrl+Alt+End |

Os atalhos funcionam com o jogo em foco, via `RegisterHotKey` do Windows, sem hook de teclado. Os atalhos de zerar e encerrar chefe executam imediatamente. Atalhos globais são ignorados enquanto há um diálogo de edição aberto no painel.

## Dados salvos

Contagens, chefe ativo, histórico, configurações e atalhos ficam em `data/state.json`. O salvamento é automático a cada mudança, com substituição do arquivo e backup da versão anterior em `state.json.bak`. Ao reiniciar, a jornada e a sessão ativa são restauradas. O botão **Abrir pasta dos dados** facilita fazer uma cópia manual. No modo sem terminal, erros são registrados em `data/app.log`.

Se uma versão antiga ainda estiver aberta, encerre-a antes de iniciar o novo painel. Valores de versões anteriores, que existiam apenas na memória, precisam ser informados pelo botão **Editar** na primeira execução.

## Captura e reconhecimento

O programa compara o formato das letras vermelhas com a imagem `3.png`, em vários tamanhos, sem OCR ou modelo de IA treinado. Consulta a captura 2 vezes por segundo por padrão; a frequência efetiva depende do RTSS e do jogo. Confirma a mensagem em dois quadros e exige 2 segundos sem ela para permitir outra contagem.

A captura padrão usa o **RivaTuner Statistics Server (RTSS)** instalado com o MSI Afterburner. O programa solicita screenshots pelo protocolo oficial do SDK do RTSS (`RTSSSharedMemoryV2`, campos `dwScreenCaptureFlags` e `szScreenCapturePath`). Isso permite receber imagens pelo hook de renderização do RTSS, inclusive quando a captura externa DXGI falha em tela cheia exclusiva. Screenshots BMP são criadas em uma pasta temporária, lidas e substituídas; a pasta é removida ao encerrar. Não é gravado vídeo. Essa alternativa envolve mais transferência de imagem e escrita temporária que a captura DXGI.

Abra o RTSS antes de iniciar o jogo. Caso o jogo já estivesse aberto e o contador mostre “Aguardando jogo no RTSS”, reinicie o jogo com o RTSS aberto. O perfil do Elden Ring no RTSS precisa permitir a detecção do aplicativo. Se o RTSS exigir elevação, abra-o normalmente pelo menu Iniciar; o contador usa a memória compartilhada dele.

No modo RTSS, o contador aparece também no **OSD do próprio RTSS**, sobre a imagem do jogo, inclusive em tela cheia exclusiva. A janela do Windows serve como controle e pode ser minimizada pelo botão “Minimizar”; o contador continua funcionando. O RTSS precisa estar com a exibição do OSD ativada. A integração preserva o espaço usado pelo Afterburner e remove seu próprio texto ao encerrar normalmente.

O texto “Monitorando” indica imagens recentes. “Sem imagem do jogo” indica uma interrupção da captura; “Aguardando imagem do jogo” aparece antes do primeiro quadro. Você pode ocultar os avisos no OSD em **Texto no jogo**. A captura real e o OSD sobre o Elden Ring foram verificados; precisão na tela de morte e comportamento com HDR ainda dependem de validação durante uma partida.

O código Python acessa apenas a memória compartilhada do RTSS e as imagens temporárias; não abre a memória do jogo nem altera seus arquivos. O RTSS, por sua vez, usa seu próprio hook no processo do jogo, como no Afterburner. Isso não representa garantia de aceitação por anticheat.

Pelo PowerShell:

```powershell
.\iniciar.bat
.\iniciar.bat --check
.\iniciar.bat --debug
.\iniciar.bat --capture dxgi
.\iniciar.bat --monitor 1
.\iniciar.bat --fps 3
.\iniciar.bat --threshold 0.75
```

`--check` tenta receber um quadro do jogo pelo RTSS em até 8 segundos. `--debug` mostra a área analisada e a pontuação de semelhança. `--capture dxgi` seleciona a captura externa anterior; só nesse modo `--monitor` seleciona a saída de vídeo, começando em 0. `--fps` aceita de 1 a 15, com padrão 2. `--threshold` define a semelhança mínima (padrão 0.70): aumentar reduz falsos positivos, mas pode perder detecções.

A referência incluída reconhece a mensagem em português. Para outro idioma ou aparência, use `--reference caminho.png` com uma imagem recortada da mensagem vermelha. A detecção pode precisar de ajustes em cenários reais; os testes com imagens não garantem precisão durante uma partida.

Os argumentos da linha de comando substituem a configuração carregada. `--data-dir caminho` permite usar outra pasta de dados. `--check` não altera os dados. A maior parte dos ajustes também está disponível no painel.

Testes: `venv_eldenring\Scripts\python.exe -m unittest discover -s tests -v`.

Após contar uma morte, a frequência cai para uma consulta por segundo até a mensagem desaparecer. O reconhecimento trabalha em uma imagem reduzida de 320 pixels de largura e usa uma thread do OpenCV. No RTSS, screenshots temporárias continuam sendo necessárias; a otimização reduz sua frequência, sem prometer ausência de impacto no jogo.

## Execut?vel e ?cone

O execut?vel fica em `dist/EntreTerras/EntreTerras.exe`; mantenha a pasta `_internal` junto dele. N?o requer Python instalado, mas requer RTSS instalado. O atalho **Entre Terras** na pasta do projeto usa os dados existentes em `data/`. Abrir o execut?vel diretamente usa `data/` ao lado dele. Para gerar novamente ap?s mudar o c?digo, execute `gerar_executavel.bat`. O execut?vel solicita eleva??o do Windows para poder iniciar e encerrar o RTSS.
