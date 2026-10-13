# Automação RPA com Windmill e Guacamole

Este repositório demonstra uma automação de navegador que coleta os títulos dos
cursos de `adolfoguimaraes.dev` e os preenche em uma planilha do Google Sheets.
O navegador roda em um desktop Linux com XFCE e Chromium. O Guacamole fornece
acesso visual ao desktop; o Windmill publica, orquestra e executa os scripts
Python. Não há agendamento pré-configurado neste repositório.

O ambiente é destinado a desenvolvimento e uso local. As credenciais padrão do
compose são de demonstração: não exponha essas portas à internet nem reutilize
essas senhas em um ambiente compartilhado ou de produção.

## Como as peças se conectam

```text
Navegador do usuário
  ├── Windmill (http://localhost:8000) ── executa o script RPA
  ├── Portal opcional (http://localhost:8090) ── inicia jobs do Windmill
  └── Guacamole (http://localhost:8080/guacamole) ── mostra o desktop

Windmill worker
  ├── cria um container rpa-desktop por job via Docker
  ├── conecta ao Chromium por CDP
  └── registra uma conexão VNC temporária no Guacamole

Script RPA ── abre o site, coleta os títulos e escreve na planilha
```

O worker precisa acessar o daemon Docker e a rede Docker `rpa-net`. Ao terminar
o job, o módulo compartilhado remove o container do desktop e a conexão
temporária do Guacamole, inclusive se ocorrer um erro no script.

## Componentes do repositório

| Caminho | Responsabilidade |
| --- | --- |
| `docker-compose.guacamole.yml` | Serviços de Guacamole/PostgreSQL, Windmill, portal e desktop manual opcional. |
| `desktop/Dockerfile` e `desktop/start.sh` | Imagem XFCE/Chromium, servidor VNC e endpoint CDP do navegador. |
| `windmill/f/rpa/guac_session.py` | Cria e limpa o desktop descartável e a conexão do Guacamole para cada job. |
| `windmill/f/rpa/coletar_cursos.py` | Robô publicado no Windmill; coleta os títulos e os escreve na planilha. |
| `windmill/f/rpa/coleta_candidatos.py` | Robô (em construção) que coleta no TSE os nomes dos candidatos de um estado; os passos ficam em `TODO`. |
| `windmill/deploy.py` | Cria o workspace `rpa` se necessário e publica os scripts no Windmill. |
| `windmill/launch.py` | Executa um script publicado, acompanha os logs e abre o Guacamole quando o link aparece. |
| `windmill/portal/` | Interface web opcional para executar scripts publicados e ver o histórico recente. |
| `run.py` | Fluxo local/manual, separado da execução pelo Windmill. |

## Requisitos

- Docker Desktop iniciado, usando containers Linux, com Docker Compose v2.
- Python instalado e disponível como `python` no PowerShell.
- Acesso de rede ao site e à planilha de destino.
- Para a execução pelo Windmill, o worker deve conseguir usar o socket do Docker
  montado pelo compose. O compose está configurado para ambientes Docker
  compatíveis com `/var/run/docker.sock`; confirme essa integração no Docker
  Desktop caso o worker não consiga criar containers.

Execute os comandos abaixo no PowerShell, a partir da pasta raiz do repositório.
Se necessário, primeiro navegue até ela:

```powershell
Set-Location "C:\caminho\para\playteste"
```

## Inicialização do ambiente

### 1. Construir a imagem do desktop

O serviço `desktop` tem um perfil Compose e não inicia junto com os serviços
principais. A imagem, porém, também é usada pelo worker para criar desktops
temporários, por isso construa-a antes de executar o primeiro robô:

```powershell
docker compose -f docker-compose.guacamole.yml --profile desktop build desktop
```

### 2. Iniciar Guacamole e Windmill

```powershell
docker compose -f docker-compose.guacamole.yml up -d
docker compose -f docker-compose.guacamole.yml ps
```

Espere os serviços ficarem prontos antes de publicar os scripts. Se algum deles
não iniciar, consulte os logs:

```powershell
docker compose -f docker-compose.guacamole.yml logs -f guacamole windmill_server windmill_worker
```

Para interromper o acompanhamento dos logs, pressione `Ctrl+C`; isso não
interrompe os containers.

### 3. Acessar as interfaces

| Serviço | Endereço | Credencial local configurada |
| --- | --- | --- |
| Windmill | <http://localhost:8000> | Use a conta configurada no Windmill; o script de publicação tem valores padrão locais. |
| Guacamole | <http://localhost:8080/guacamole> | Use a conta configurada no compose e no worker. |
| Portal opcional | <http://localhost:8090> | Usa o token do Windmill gerado/registrado durante a publicação. |

O compose e os scripts definem credenciais padrão para uso local. Consulte esses
arquivos para identificar os valores da sua cópia e altere-os antes de
compartilhar ou expor o ambiente. Se a conta do Windmill tiver outras
credenciais, informe-as nos comandos abaixo.

## Publicar e executar o robô no Windmill

### 1. Publicar os scripts

O comando autentica no Windmill, cria o workspace `rpa` se necessário e publica
`f/rpa/guac_session` e `f/rpa/coletar_cursos`:

```powershell
python windmill/deploy.py
```

Para usar outra URL ou credenciais do Windmill:

```powershell
python windmill/deploy.py --url http://localhost:8000 --email "email configurado" --password "senha configurada"
```

O script registra um token para o portal em `.env` somente quando ainda não há
uma entrada `WM_TOKEN`. O token é uma credencial: não o publique nem o inclua
em logs ou documentação; não versione `.env`. Depois da publicação, (re)crie o
serviço do portal para que ele leia o `.env` atualizado:

```powershell
docker compose -f docker-compose.guacamole.yml up -d --force-recreate portal
```

O portal é opcional; a publicação e a execução por linha de comando não
dependem dele.

### 2. Executar pelo Windmill via linha de comando

Inicie o robô em modo assistido, que espera a interação do usuário:

```powershell
python windmill/launch.py f/rpa/coletar_cursos --args '{"assisted": true, "max_wait_s": 1800}'
```

O launcher mostra o identificador do job, acompanha os logs e abre o endereço
do Guacamole quando o desktop estiver pronto. No desktop, clique em **Cursos**
no site. Depois que o robô preencher a planilha, feche a aba da planilha no
desktop para finalizar a execução assistida. O launcher retorna código de saída
zero em caso de sucesso e diferente de zero quando o job falha.

Para deixar a navegação automática, sem esperar o clique em **Cursos** nem o
fechamento da planilha:

```powershell
python windmill/launch.py f/rpa/coletar_cursos --args '{"assisted": false}'
```

Também é possível passar uma planilha diferente e ajustar o tempo limite:

```powershell
python windmill/launch.py f/rpa/coletar_cursos --args '{"sheet_url": "https://docs.google.com/spreadsheets/d/ID_DA_PLANILHA/edit", "assisted": true, "max_wait_s": 900}'
```

Para usar credenciais diferentes do Windmill no launcher:

```powershell
python windmill/launch.py f/rpa/coletar_cursos --email "email configurado" --password "senha configurada"
```

### 3. Executar pela interface web do Windmill

1. Abra <http://localhost:8000> e entre no workspace `rpa`.
2. Abra o script `f/rpa/coletar_cursos` e execute-o.
3. Para o modo assistido, mantenha `assisted` habilitado. Use `max_wait_s` para
   configurar o limite de espera em segundos.
4. Acompanhe os logs do job. Quando o script imprimir o endereço do desktop,
   abra esse endereço e clique em **Cursos**.
5. Feche a aba da planilha no desktop quando o preenchimento terminar.

### 4. Executar pelo portal (opcional)

Depois de publicar os scripts e iniciar/recriar o serviço `portal`, abra
<http://localhost:8090>. Selecione o robô, ajuste seus parâmetros e clique em
**Executar**. O portal exibe o estado e os logs, abre o desktop quando o job o
informa e mostra até dez execuções recentes. O script compartilhado
`guac_session` não aparece como robô executável no portal.

## Fluxo local/manual com `run.py`

Esse é um caminho alternativo e não cria jobs no Windmill. Ele usa um desktop
fixo do Compose e configura a conexão `Desktop Linux` no Guacamole:

```powershell
docker compose -f docker-compose.guacamole.yml --profile desktop up -d desktop
```

Instale as bibliotecas Python importadas por `run.py`:

```powershell
python -m pip install playwright selenium
```

Em seguida, execute:

```powershell
python run.py --os guacamole
```

Abra o endereço do Guacamole impresso no terminal, clique em **Cursos** e
aguarde o robô preencher a planilha. O processo local espera que a aba da
planilha seja fechada para terminar. O Chromium usado está dentro do container;
não é necessário instalar um browser do Playwright no Windows para esse modo.

`run.py` também aceita `--os linux` (Selenium Grid em `localhost:4444`) e
`--os windows` (Chrome/CDP em `localhost:9223`), mas esses ambientes externos
não são provisionados por este compose.

## Configuração e parâmetros

### Robô `f/rpa/coletar_cursos`

| Parâmetro | Tipo | Padrão | Comportamento |
| --- | --- | --- | --- |
| `sheet_url` | texto | Planilha definida no script | URL da planilha editável. |
| `assisted` | booleano | `true` | Espera o usuário navegar até **Cursos** e fechar a aba da planilha. Desabilitado, acessa `/courses` e finaliza após preencher. |
| `max_wait_s` | inteiro | `1800` | Tempo máximo de espera pelas interações assistidas, em segundos. |

O robô escreve os títulos coletados a partir da célula `A1`, um por linha. O
desktop criado para cada execução é descartável e não usa a sessão autenticada
do usuário; por isso, a planilha precisa permitir edição para quem a acessa
pelo link, como no compartilhamento esperado por esta automação.

### Variáveis usadas pelo worker

O compose configura no `windmill_worker` as variáveis `GUAC_URL`,
`GUAC_PUBLIC_URL`, `GUAC_USER`, `GUAC_PASS`, `DESKTOP_IMAGE` e
`DESKTOP_NETWORK`. A lista `WHITELIST_ENVS` permite que os scripts Windmill
recebam esses valores. Se alterar nomes, credenciais ou rede, mantenha as
configurações do compose consistentes com o módulo
`windmill/f/rpa/guac_session.py`.

`GUAC_URL` é o endereço interno usado pelo worker para chamar a API do
Guacamole; `GUAC_PUBLIC_URL` é o endereço que o navegador do usuário consegue
abrir. Em uso local, eles apontam respectivamente para o serviço Docker e para
`localhost`.

## Operação diária

Verificar estado:

```powershell
docker compose -f docker-compose.guacamole.yml ps
```

Ver logs do worker:

```powershell
docker compose -f docker-compose.guacamole.yml logs -f windmill_worker
```

Parar os serviços sem remover os dados persistidos:

```powershell
docker compose -f docker-compose.guacamole.yml down
```

Iniciá-los novamente:

```powershell
docker compose -f docker-compose.guacamole.yml up -d
```

Após alterar um script RPA, publique-o novamente:

```powershell
python windmill/deploy.py
```

Após alterar `desktop/Dockerfile` ou `desktop/start.sh`, reconstrua a imagem:

```powershell
docker compose -f docker-compose.guacamole.yml --profile desktop build desktop
```

## Solução de problemas

- **Windmill ou Guacamole ainda não respondem:** confira `docker compose ... ps`
  e os logs de `windmill_server`, `windmill_worker`, `guacamole`, `postgres` e
  `guacd`. Aguarde os serviços e bancos terminarem a inicialização.
- **Falha de autenticação na publicação/launcher:** confira a URL e as
  credenciais Windmill. Informe-as com `--url`, `--email` e `--password`.
- **Worker não consegue criar o desktop:** confira os logs de
  `windmill_worker`, se o Docker Desktop está ativo e se o socket Docker está
  acessível dentro do container. O worker cria o desktop usando a imagem
  `rpa-desktop:latest` e a rede `rpa-net`.
- **Erro indicando imagem ou rede ausente:** construa a imagem com o comando
  de build acima e confirme que a stack foi iniciada pelo arquivo
  `docker-compose.guacamole.yml`.
- **Link do desktop não abre:** o endereço público é configurado por
  `GUAC_PUBLIC_URL`. O navegador do usuário precisa conseguir alcançar esse
  endereço e a porta `8080`.
- **Portal sem lista de robôs ou com erro de autorização:** confirme que os
  scripts foram publicados no workspace `rpa` e recrie `portal` após o token
  existir em `.env`. Não compartilhe esse arquivo, pois ele pode conter um
  token de acesso.
- **Planilha não abre, não permite edição ou não finaliza:** valide o parâmetro
  `sheet_url`, a permissão de edição da planilha e, no modo assistido, feche a
  aba da planilha no desktop antes de expirar `max_wait_s`.
- **Código do script atualizado não aparece no Windmill:** execute novamente
  `python windmill/deploy.py` para publicar a versão atual.
