# Distribuição para Windows

## Instalar

Baixe `EntreTerras-<versão>-Setup-x64.exe` em
[Releases](https://github.com/SamuelASDev/pythonleitorEldenRing/releases/latest).
O instalador inclui Python e as dependências, cria o atalho no menu Iniciar,
oferece um atalho na área de trabalho e registra a desinstalação no Windows.
Instale o RTSS separadamente; o aplicativo oferece a página oficial quando
não o encontra. Abra o Entre Terras antes do jogo.

O histórico fica em `%LOCALAPPDATA%\EntreTerras`. Atualizações e desinstalações
preservam essa pasta. Para remover os dados pessoais, abra a pasta pelo painel,
encerre o aplicativo e remova a pasta manualmente.

A edição portátil fica no arquivo `Portable-x64.zip`: extraia a pasta inteira
e abra `EntreTerras.exe`. Ela também usa LOCALAPPDATA por padrão. Para manter
dados independentes, passe `--data-dir caminho`. Não separe o executável da
pasta `_internal`.

Na primeira abertura, dados válidos da antiga pasta `data` ao lado do executável
são copiados para LOCALAPPDATA, se ainda não houver dados no destino. Os arquivos
originais são mantidos. O checkout antigo `dist/EntreTerras` também reconhece
`data` na raiz do projeto. Para mudar de uma pasta antiga para uma instalação
em Program Files, copie `state.json` e `state.json.bak`, se existir, para
`%LOCALAPPDATA%\EntreTerras` antes da primeira abertura, com o contador encerrado.

## Gerar uma versão

Requisitos: Windows x64, Python 3.11+, dependências de `requirements-dev.txt`
e [Inno Setup 6.3 ou superior](https://jrsoftware.org/isinfo.php).

```powershell
.\venv_eldenring\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv_eldenring\Scripts\python.exe scripts/build_release.py
# Caso ISCC.exe não esteja instalado no caminho padrão:
.\venv_eldenring\Scripts\python.exe scripts/build_release.py --iscc "C:\caminho\ISCC.exe"
```

O script executa os testes e gera instalador, ZIP portátil e `SHA256SUMS.txt`
em `dist/release`. O executável recebe os metadados de versão do Windows.
O build usa `build/release`, sem substituir a distribuição local em uso.
Os artefatos incluem somente os arquivos da aplicação, sem o histórico pessoal.
Antes de instalar ou atualizar, encerre o contador pelo ícone na bandeja.

## Publicar no GitHub

1. Atualize a versão em `pyproject.toml` e `entre_terras/__init__.py`.
2. Faça commit, push e crie uma tag correspondente, por exemplo `v1.1.0`.
3. Envie a tag. O workflow `Windows release` executa testes, gera os arquivos
   e publica a Release com os downloads e avisos sobre a assinatura.

Executar o workflow manualmente gera artefatos para revisão sem publicar Release.
O workflow de testes continua sendo executado em cada push e pull request.

## Assinatura digital

O instalador funciona sem certificado, mas pode mostrar “Publicador desconhecido”
ou avisos do SmartScreen. Checksums verificam integridade; não identificam o autor.
Não peça às pessoas para desativar o antivírus ou as proteções do Windows.

Para assinar, obtenha um certificado de assinatura de código emitido para sua
identidade e instale-o, com a chave privada, no armazenamento de certificados
do usuário responsável pelo build. Instale também `signtool.exe` do Windows SDK.
O suporte local usa o certificado pelo thumbprint, sem gravar a chave no projeto:

```powershell
$env:WINDOWS_SIGN_THUMBPRINT = "THUMBPRINT_DO_CERTIFICADO"
$env:SIGNTOOL_PATH = "C:\caminho\signtool.exe"
.\venv_eldenring\Scripts\python.exe scripts/build_release.py
```

O script assina o executável, o instalador e o desinstalador com SHA256 e
timestamp. O serviço de timestamp pode ser definido em `WINDOWS_TIMESTAMP_URL`.
O ZIP contém o executável assinado. O workflow público atual produz versões
**sem assinatura**, pois ainda não há identidade/certificado configurado no CI.
Não coloque certificados, senhas ou chaves privadas no Git.

Microsoft Artifact Signing é outra opção; exige cadastro, validação de identidade
e configuração própria no CI. Uma assinatura válida não garante a ausência de
avisos do SmartScreen em uma aplicação nova.

Fontes: [Microsoft: reputação SmartScreen](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation),
[Inno Setup](https://jrsoftware.org/isinfo.php).
