# SESI — Indústria do Conhecimento

Projeto simples em Django Templates, HTML semântico, Bootstrap 5 e CSS próprio. Interface mobile-first, com JavaScript vanilla apenas para enviar a seleção de unidade automaticamente. As três imagens fornecidas orientam a identidade visual e a estrutura das páginas. A Home utiliza a foto cadastrada do polo, com a imagem fornecida como exemplo identificado quando não há foto; o cabeçalho utiliza os dois SVGs fornecidos e todas as telas compartilham o fundo SVG em static/img.

## Autenticação e controle de acesso

### Organização visual do painel e de Registros

A Home mantém a identidade visual e coloca o filtro de Polo no topo, ao lado do
título, somente para ADMIN. A primeira linha contém foto, informações da unidade
e acompanhamento mensal em cards, um por indicador. A segunda contém um placeholder
para futuro mapa e o calendário existente. Nenhum mapa, API ou biblioteca de mapas
foi implementado. O header mantém navegação e Sair, sem identificação da conta.

Os cards mostram competência, previsto, realizado e atingimento mensais. Totais de
atendimentos ou livros só aparecem separadamente quando não há indicador configurado
para essa métrica. Não são exibidos valores anuais. A barra limita a largura a 100%,
enquanto o texto mantém percentuais superiores a 100%. Meta ausente aparece como
travessão, com descrição acessível; zero cadastrado aparece como 0. Previsto e realizado
são apresentados como inteiros na Home e em Registros (arredondamento visual, sem
alteração dos valores armazenados); percentuais mantêm duas casas decimais. Atingimento
indisponível permanece travessão, sem atribuição artificial de percentual.

Registros aceita `?year=<ano>&polo=<id>` e preserva links antigos com `?month=AAAA-MM`.
Cada Polo tem uma seção por indicador e exatamente 12 linhas, Janeiro a Dezembro,
com Mês, Previsto, Realizado e Atingimento. Em telas pequenas as mesmas linhas se
reorganizam em blocos, sem duplicar os dados no DOM. ADMIN pode filtrar polos;
GERENTE continua limitado ao seu Polo no backend.

A view monta os 12 meses reutilizando `resultados_por_polo` em lotes para os polos
autorizados. A quantidade de consultas é fixa por página e não cresce por Polo ou
indicador. Nenhuma fórmula, model, migration, autorização ou dado persistido mudou
nesta reorganização. Atendimentos, notas, anexos e ações existentes ficam numa área
recolhível abaixo das tabelas, referente à competência selecionada (mês atual quando
se usa somente o filtro de ano). Os cálculos anuais continuam disponíveis no serviço
e contexto para compatibilidade, sem apresentação nas telas.

O layout foi inspecionado no Chrome em larguras de 390, 768 e 1440 pixels, sem
overflow horizontal. Testes cobrem cards, ordem dos meses, meta ausente versus zero,
atingimento superior a 100%, ausência de valores anuais na interface e permissões.

Todas as páginas internas exigem login em `/login/`. A autenticação utiliza User,
hashing de senhas, sessões e proteção CSRF nativos do Django. Não há cadastro público.
O botão Sair envia POST para `/logout/`, encerra a sessão e retorna ao login.
O parâmetro `next` é validado pelo LoginView do Django contra redirecionamento externo.

`PerfilUsuario` (migration `0006_perfilusuario`) associa exatamente um perfil a cada
User por `OneToOneField`, com tipo ADMIN ou GERENTE e timestamps. GERENTE exige
um único Polo; ADMIN exige Polo vazio. ModelForms validam essas regras e uma
constraint no banco também impede combinações inválidas. Usuários comuns sem
perfil recebem 403. Nenhuma conta ou perfil é criado automaticamente.

O superusuário tem acesso técnico ao Django Admin e é tratado como ADMIN funcional,
mesmo sem perfil. O Django Admin fica reservado a superusuários; `is_staff` e
permissões isoladas não permitem contornar as regras funcionais. ADMIN funcional
não recebe acesso técnico ao Admin. Somente superusuários podem gerenciar perfis.

Para criar contas internamente:

1. Execute `.venv\Scripts\python.exe manage.py createsuperuser` caso ainda não tenha acesso técnico.
2. Entre em `/admin/` e crie o User em Usuários, definindo a senha pelo formulário nativo.
3. Em Perfis de usuários (`/admin/portal/perfilusuario/`), associe o User ao tipo ADMIN
   sem Polo ou ao tipo GERENTE com o Polo obrigatório. Mantenha contas funcionais sem
   flags de superusuário ou acesso à equipe. Usuários inativos não podem autenticar.

`portal/access.py` centraliza a validação de perfil e a função `escopo`, utilizada
por Home, Registros, edição e arquivos. Para novos relatórios, aplique `login_required`
e `escopo(request.user, queryset)` antes de consultar dados; para Polo use campo `pk`,
e para relações indiretas informe o caminho do polo. Não existem relatórios separados
de Registros nesta etapa.

ADMIN consulta todos os polos e filtra Registros por `?polo=<id>`. GERENTE abre
automaticamente seu Polo, sem seletor, e parâmetros externos não ampliam o escopo.
Eventos, metas, responsáveis e realizados acompanham o Polo autorizado. Na criação
e edição, o campo Polo do gerente fica desabilitado e seu valor é determinado no
servidor. Um `polo`/`polo_id` forjado é ignorado; eventos de outro polo são rejeitados.

Registros contém links para `/atendimentos/<id>/editar/` e, para ADMIN, exclusão.
Editar registro fora do escopo retorna 404, inclusive por POST. GERENTE recebe 403
em GET/POST de exclusão; DELETE não é aceito (405). A exclusão por ADMIN exige
confirmação e POST com CSRF. A edição preserva os anexos existentes e não oferece
substituição de fotos nesta etapa. A exclusão mantém a política existente de não
apagar arquivos físicos automaticamente.

URLs `/media/` também exigem autenticação e conferem o Polo vinculado no banco,
incluindo fotos de polos e anexos de eventos/atendimentos. Arquivos sem referência
autorizada retornam 404. A configuração de desenvolvimento não publica mais media
diretamente com `static()`. Em uma futura publicação, o servidor de mídia também
deverá preservar essa autorização, sem expor a pasta como diretório público.

Testes de regressão existentes foram mantidos com login de teste. Os testes de acesso
incluem manipulação de URL, query string, POST, exclusão, acesso direto a mídia,
CSRF, login/logout e ausência de perfil. Contas de teste existem somente no banco
temporário. O teste HTTP existente agora realiza login real antes do cadastro.

Próxima etapa recomendada: revisão visual e homologação dos perfis com os responsáveis,
incluindo a definição da retenção de anexos. Não foram implementadas integrações externas,
recuperação de senha por e-mail ou publicação.

## Executar no Windows (ambiente local)

Use Python 3.10 ou superior (ambiente validado: Python 3.14.8, Django 5.2.18 e SQLite 3.50.4). Execute no PowerShell, na pasta do projeto. Se `.venv` já existir, reutilize-a e pule sua criação:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py check
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver
```

Acesse http://127.0.0.1:8000/. Bootstrap é carregado por CDN e requer internet; para uso offline, baixe o CSS para static e altere o link em base.html.

Mantenha o terminal do servidor aberto enquanto utiliza o site; use `Ctrl+C` para encerrá-lo. Se o PowerShell bloquear `Activate.ps1`, pule a ativação: os comandos acima usam diretamente o Python da `.venv`.

## Banco local de desenvolvimento

O banco padrão utiliza o backend oficial `django.db.backends.sqlite3`, com o arquivo `BASE_DIR / 'db.sqlite3'` na raiz do projeto. Não é necessário instalar SQL Server ou um servidor de banco separado. `migrate` aplica as migrations internas de autenticação, tipos de conteúdo e sessões do Django, além das migrations do aplicativo `portal` que já existiam.

Para confirmar o backend, o caminho e o acesso à conexão pelo Django:

```powershell
.venv\Scripts\python.exe manage.py shell -c "from django.db import connection; connection.ensure_connection(); print(connection.vendor); print(connection.settings_dict['NAME']); print(connection.is_usable())"
.venv\Scripts\python.exe manage.py showmigrations
```

O resultado da conexão deve indicar `sqlite`, o caminho de `db.sqlite3` e `True`. As migrations aplicadas aparecem com `[X]`. `.venv/`, caches Python e `db.sqlite3` estão ignorados pelo Git; os arquivos de migrations são versionados. Alterações futuras de estrutura devem usar models e migrations do Django, sem scripts SQL manuais.

Os models iniciais `Attendance` e `Attachment` foram adaptados para `Atendimento` e `AnexoAtendimento`, sem duplicar entidades. A migration `0003_normalizar_legado_teste` remove os dois registros confirmados como testes, renomeia os models/campos aproveitáveis e elimina as quantidades agregadas antigas. Essa remoção é irreversível; a migration interrompe a execução se houver anexos legados ou mais de dois registros. Não use esse procedimento para importar dados de produção. A migration `0004_estrutura_normalizada` completa a modelagem; as migrations anteriores foram mantidas.

## Modelagem e administração

Os cadastros usam a chave primária padrão do Django. IDs SharePoint são opcionais, apenas para rastreabilidade, em Polo, Atendimento e Evento.

| Model | Relacionamentos e regras |
| --- | --- |
| Polo | Cadastro com nome, situação, contato, parceiro, horário, coordenadas e referência à foto. Sem tabela Unidade ou colunas mensais. |
| ResponsavelPolo | Vários responsáveis por polo; email e telefone opcionais. |
| Evento | Pertence a um polo; data final não pode anteceder a inicial. Status é texto livre até a definição das opções de negócio. |
| Atendimento | Pertence a um polo e pode ter um evento do mesmo polo. Livros retirados são inteiros não negativos. Cada registro representa um atendimento. |
| Indicador | Código único, nome, tipo de cálculo e situação. Nenhum indicador é criado automaticamente. |
| MetaMensal | Polo + indicador + competência únicos. Competência é uma data no primeiro dia do mês; previsto é decimal não negativo, com duas casas. |
| AnexoAtendimento | Arquivo e metadados relacionados ao atendimento, em `media/atendimentos/`. |
| AnexoEvento | Arquivo e metadados relacionados ao evento, em `media/eventos/`. |

Os seis cadastros principais possuem datas de criação e atualização; anexos possuem data de envio. As coordenadas usam decimal com seis casas, com validação dos limites de latitude e longitude. A foto usa `FileField`, evitando dependências adicionais: o banco armazena o caminho, e o arquivo fica em `media/polos/`. A validação específica da foto poderá ser adicionada posteriormente.

As relações com Polo, Indicador e Evento usam `PROTECT`: um cadastro referenciado não pode ser excluído acidentalmente. Use o campo `ativo` quando disponível para desativar cadastros. Anexos usam `CASCADE` e suas referências são removidas com o atendimento/evento; o Django não apaga automaticamente os arquivos físicos. A política de limpeza de mídia ficará para uma etapa posterior.

Valores negativos, datas de evento inválidas, competência fora do primeiro dia do mês e metas duplicadas são protegidos no banco por constraints. A relação entre atendimento e evento do mesmo polo é validada em `clean()`, utilizada pelo formulário e pelo Admin. Para gravações diretas via ORM, chame `full_clean()` antes de `save()`; o Django não executa essa validação automaticamente.

O Admin padrão está em `/admin/`. Para cadastrar um usuário administrador local, execute interativamente:

```powershell
.venv\Scripts\python.exe manage.py createsuperuser
```

As migrations não criam usuários ou cadastros de negócio. Polos podem ser cadastrados pelo Admin ou pelo comando manual descrito abaixo. Testes usam somente o banco temporário do Django:

```powershell
.venv\Scripts\python.exe manage.py test
.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Ficam para etapas posteriores: opções de status, definição dos cadastros reais de indicadores, relatórios, API, validação avançada de uploads e política de retenção dos arquivos. Não existem credenciais ou conexões SharePoint nesta implementação e não há importação de atendimentos antigos.

## Cadastrar e conferir os dados reais

### Carga manual dos 26 polos

O comando abaixo carrega exclusivamente os nomes e parceiros fornecidos manualmente para esta etapa, usando o ORM e uma única transação:

```powershell
.venv\Scripts\python.exe manage.py seed_polos
```

São 26 polos: Açailândia e Caxias com parceiro SENAI; os outros 24 com Prefeitura. Novos registros preservam a grafia da lista e usam somente os defaults legítimos do model para campos não informados. IDs SharePoint, responsáveis, telefone, horário, foto, coordenadas, metas, eventos e atendimentos não são preenchidos pela carga.

A execução é idempotente: cria nomes ausentes, atualiza somente `parceiro` quando diferente e deixa os registros corretos intactos. A comparação usa `casefold()` Unicode, incluindo acentos, sem alterar o nome de registros existentes. Outros campos, timestamps e relações são preservados. Se mais de um polo corresponder ao mesmo nome, o comando cancela a carga inteira e pede a resolução da ambiguidade, sem excluir registros.

O model não possui unicidade no nome; execute a carga sequencialmente, sem outros processos cadastrando polos ao mesmo tempo. A operação não faz conexão com SharePoint nem lê arquivos externos, e não exige alterações de schema. O resumo informa criados, atualizados, já corretos e total processado; o total do banco pode ser maior se houver polos fora da lista.

### Importar metas de um CSV manual

O arquivo fornecido nesta etapa é `data/Medições.csv`. O comando aceita o caminho como argumento e não depende do nome do arquivo:

```powershell
.venv\Scripts\python.exe manage.py importar_metas "data/Medições.csv" --dry-run
.venv\Scripts\python.exe manage.py importar_metas "data/Medições.csv"
```

Use CSV UTF-8 (com ou sem BOM), separado por vírgulas, com as colunas `ChaveMeta`, `Polo`, `Mes_Referencia`, `Indicador` e `Valor`. O importador desta etapa aceita somente metas de 2026 para `Atendimentos`. Datas devem usar `dd/mm/aaaa`, com dia 01. Valores são inteiros não negativos: pontos representam milhares, portanto `1.800` vira **1800**, nunca 1,8. Valores decimais ou com agrupamento inválido são rejeitados.

Todo o arquivo é lido e validado antes de qualquer gravação: cabeçalhos, campos vazios, datas, limites numéricos do model, indicador suportado e duplicidades de ChaveMeta e polo + indicador + competência. Os polos devem existir e são comparados por nome com `casefold()` Unicode; ausências e nomes ambíguos cancelam a importação. Erros de linha informam número e ChaveMeta quando disponível. ChaveMeta não é armazenada no banco.

O indicador é localizado primeiro pelo código `atendimentos`, depois por nome quando não há esse código. Se ainda não existe, é criado com nome `Atendimentos`, tipo `quantidade_atendimentos` e ativo. Indicadores preexistentes incompatíveis ou pendentes interrompem a operação; nenhum tipo é alterado silenciosamente. Indicadores compatíveis são preservados.

`--dry-run` valida e informa quantas metas seriam criadas, atualizadas ou mantidas, sem gravar indicador ou metas. A importação real utiliza uma transação: cria metas ausentes, atualiza somente `previsto` quando diferente e preserva as metas já corretas. A reexecução sequencial não duplica registros. Execute sem alterações concorrentes dos cadastros durante a carga.

Foram importadas 240 metas para 20 polos, com 12 meses cada. Os 20 totais anuais foram conferidos por soma no ORM. Açailândia tem abril = 1800 e anual = 10230. Os seis polos fora do arquivo continuam sem metas; ausência não vira zero. Nenhum atendimento, realizado histórico, responsável ou dado de polo foi importado/alterado.

Confira em `/?unit=<id-do-polo>&month=2026-04` e `/registros/?month=2026-04`. Realizado permanece zero enquanto não houver atendimentos e o percentual segue as regras do serviço existente. Não houve alteração de schema, CSS ou templates.

Próxima etapa recomendada para a carga: revisar os previstos nas telas com os responsáveis pelo negócio e definir como serão autorizadas futuras revisões do CSV. Essa etapa não foi executada.

### Cadastro manual e conferência

1. Crie seu usuário com `createsuperuser` e abra http://127.0.0.1:8000/admin/ usando suas próprias credenciais.
2. Em **Polos**, adicione nome, situação e os dados opcionais de parceiro, telefone, horário e foto. Todos os polos, inclusive inativos, continuam disponíveis na consulta; os inativos são identificados pelo status.
3. No cadastro de responsáveis (`/admin/portal/responsavelpolo/`), cadastre cada responsável, escolhendo o polo. A Home apresenta todos os responsáveis relacionados e identifica os inativos; nomes não são duplicados no cadastro do polo.
4. No cadastro de indicadores (`/admin/portal/indicador/`), cadastre código único, nome, tipo de cálculo e situação. Escolha **Quantidade de atendimentos** ou **Livros retirados**; o nome e o código não determinam a regra. A interface apresenta cada indicador separadamente e identifica os inativos.
5. No cadastro de metas (`/admin/portal/metamensal/`), selecione polo e indicador, informe o primeiro dia do mês em competência (por exemplo, `2026-10-01`) e um previsto não negativo. O Admin mostra erros de validação e impede duplicidade de polo + indicador + competência.
6. Na Home, selecione o polo. Navegue pelos meses no calendário ou abra `/?unit=<id-do-polo>&month=2026-10`. A foto, responsáveis, horário e parceiro devem corresponder ao cadastro. Eventos exibidos são os que coincidem com o mês consultado, sem ampliar seu fluxo operacional.
7. Confira as metas no bloco de acompanhamento e em `/registros/?month=2026-10`. O previsto mensal considera exatamente a competência selecionada. O anual é a soma das metas do mesmo polo, indicador e ano; não mistura indicadores. Metas ausentes aparecem como **Sem meta cadastrada**, enquanto zero cadastrado aparece como `0,00`.

Os realizados são derivados de `COUNT(Atendimento)` ou `SUM(livros_retirados)`, conforme o tipo explícito do indicador. Cada registro representa um atendimento. Sem atendimentos, os valores são zero. Sem polos ou indicadores, a interface apresenta estados vazios e não cria cadastros automaticamente.

As views `home` e `records` consultam somente o banco configurado no Django. Metas utilizam `values()` e `annotate(Sum(...))`, com filtro de competência mensal e ano; totais de atendimentos usam `Count` e `Sum`. A consulta consolidada usa `Prefetch` para atendimentos e seus anexos, evitando N+1. Nenhum total anual é armazenado e não há cálculos de metas em JavaScript.

A integração mantém URLs, CSS, imagens de identidade, cores, tipografia e organização dos componentes. O fragmento `templates/metas.html` apresenta as metas dentro das seções existentes. A imagem de exemplo é o único dado ilustrativo de polo mantido, até o cadastro da foto; textos como “Não informado” representam ausência real de informação, não registros fictícios.

## Regras de cálculo dos indicadores

`Indicador.tipo_calculo` utiliza `TextChoices` com os valores `quantidade_atendimentos` e `livros_retirados`. Novos indicadores exigem esse campo no Admin, nos ModelForms e na criação normal via `save()`/`objects.create()`.

A migration `0005_indicador_tipo_calculo` adiciona o campo sem default e preserva os cadastros anteriores como `NULL` (pendentes). Não atribui regras por nome ou código e não altera metas ou atendimentos. A nulabilidade é transitória para preservar dados legados; ao editar um indicador no Admin, selecione o tipo. Operações em lote do ORM não executam `save()`/`full_clean()`: valide explicitamente os objetos antes de utilizá-las. O banco rejeita tipos não suportados, mas permite `NULL` para os cadastros pendentes.

O serviço `portal/services/indicadores.py` centraliza as regras:

- `calcular_realizado(indicador, polo, competencia, anual=False)`: conta registros ou soma livros do polo e do mês/ano da data informada; o dia da competência não altera o mês selecionado. Com `anual=True`, considera o ano inteiro.
- `resultados_por_polo(...)`: calcula metas e realizados mensais/anuais em duas consultas agrupadas para todos os polos e indicadores. É utilizado por `home` e `records`, sem N+1.
- `calcular_atingimento(realizado, previsto)`: retorna `realizado / previsto * 100` usando `Decimal`, sem limitar a 100%. A apresentação arredonda para duas casas.

Previsto vem exclusivamente de `MetaMensal`. O percentual é `—` quando a meta está ausente, o previsto é zero ou o indicador está pendente. Não existe regra artificial de 100% para previsto zero. Um indicador pendente mostra “Tipo de cálculo pendente” e realizado `—`; selecione o tipo no Admin para habilitar o cálculo. Para indicadores configurados, a ausência de meta não impede a apresentação do realizado.

As mesmas regras se aplicam ao anual, já exibido nas telas: previsto é a soma das metas por polo/indicador/ano, enquanto realizado é a contagem ou soma dos atendimentos desse polo no ano inteiro. Nenhum realizado, total anual ou percentual é persistido.

Próxima etapa recomendada: cadastrar ou revisar manualmente os indicadores reais no Admin e conferir os resultados com os responsáveis pelo negócio. Após classificar todos os indicadores legados, avaliar uma migration para remover a nulabilidade transitória; essa próxima etapa não foi executada.

## Páginas

- `/`: seleção de unidade, indicadores e calendário com meses navegáveis.
- `/registros/`: totais por unidade e filtro mensal.
- `/atendimentos/novo/`: formulário validado no servidor e persistência SQLite.

O formulário registra um atendimento por envio, com polo, data, livros retirados, evento opcional e observações. As telas existentes foram adaptadas para contar registros e somar livros retirados, sem persistir realizados mensais ou anuais. Metas ficam em `MetaMensal`; não se mistura previsto de indicadores diferentes nas telas.

O formulário aceita até 2 fotos (JPG, PNG ou WebP) por atendimento, com até 2 MB (2 × 1024 × 1024 bytes) por foto. PDFs não são aceitos nos novos envios pelo formulário. Fotos continuam opcionais e anexos antigos são preservados. As inserções já possuem data para registro diário; mais de um atendimento na mesma data continua permitido. Os arquivos ficam em media/ e seus links aparecem nos registros consolidados. A validação verifica extensão e assinatura inicial; não realiza análise completa do conteúdo. Faça backup do banco e da pasta media juntos.

## Registrar um atendimento pelo frontend

Abra `/atendimentos/novo/` pelo botão **Registrar atendimentos**. O formulário existente utiliza `AtendimentoForm` (`ModelForm`) e oferece polo, data, livros retirados, evento opcional e observações. IDs e campos de migração/criação/atualização não são expostos.

Novos atendimentos no frontend aceitam somente polos ativos. Polos inativos continuam disponíveis nas consultas históricas; o cadastro no Admin foi preservado. Os eventos vêm do banco e são apresentados com o polo em seu nome; o backend valida que o evento informado pertence ao polo escolhido. Não há AJAX nem restrição adicional de datas passadas ou futuras.

Informe uma data válida e uma quantidade inteira não negativa de livros, inclusive zero. Observações são opcionais, limitadas a 2.000 caracteres. Erros aparecem junto aos campos e preservam o conteúdo informado. O formulário mantém proteção CSRF.

Após um POST válido, a gravação ocorre em transação e a view redireciona para a Home do polo e do mês da data salva. A mensagem **Atendimento registrado com sucesso.** aparece uma vez. Atualizar essa página de destino não repete o POST; dois envios independentes para o mesmo polo e data continuam permitidos.

Home e Registros recalculam realizados pelo serviço de indicadores, sem atualizar metas ou armazenar totais: dois atendimentos com 5 e 8 livros resultam em 2 atendimentos e 13 livros. Nenhuma tabela ou migration adicional foi necessária para este fluxo.

O upload é opcional. Os limites de duas fotos de 2 MB são validados no servidor pelo formulário de atendimento; o cadastro direto de anexos no Admin permanece separado deste fluxo. Autenticação externa não foi acrescentada.

A suíte inclui um teste com servidor HTTP, cookies e token CSRF reais em banco de testes isolado, além dos testes de formulário, Admin, mensagens, refresh e recálculo. Não são criados cadastros de teste no `db.sqlite3` de desenvolvimento.

A política de retenção e exclusão física dos anexos permanece pendente de definição.

Os polos são cadastros do banco, disponíveis pelo Admin. As telas tratam a ausência de cadastros e os totais são calculados a partir dos registros salvos. O estilo, as imagens e a organização visual do frontend foram preservados; rótulos e campos foram ajustados à nova modelagem.

Configuração para desenvolvimento local. Antes de publicar, configure SECRET_KEY por variável de ambiente, DEBUG=False, ALLOWED_HOSTS, HTTPS, arquivos estáticos e autenticação adequada ao ambiente.
