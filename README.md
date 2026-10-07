# SESI — Indústria do Conhecimento

Projeto simples em Django Templates, HTML semântico, Bootstrap 5 e CSS próprio. Interface mobile-first, com JavaScript vanilla apenas para enviar a seleção de unidade automaticamente. As três imagens fornecidas orientam a identidade visual e a estrutura das páginas. A Home utiliza a foto fixa fornecida; o cabeçalho utiliza os dois SVGs fornecidos e todas as telas compartilham o fundo SVG em static/img.

## Executar no Windows

Instale Python 3.10 ou superior e execute no PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe manage.py migrate
.venv\Scripts\python.exe manage.py runserver
```

Acesse http://127.0.0.1:8000/. Bootstrap é carregado por CDN e requer internet; para uso offline, baixe o CSS para static e altere o link em base.html.

## Páginas

- `/`: seleção de unidade, indicadores e calendário com meses navegáveis.
- `/registros/`: totais por unidade e filtro mensal.
- `/atendimentos/novo/`: formulário validado no servidor e persistência SQLite.

O formulário registra apenas os atendimentos realizados. O campo de previstos permanece no banco para futura integração com outra origem de dados.

O formulário aceita até 10 fotos (JPG, PNG ou WebP) ou PDFs por atendimento, com até 10 MB por arquivo. Os arquivos ficam em media/ e seus links aparecem nos registros consolidados. A validação verifica extensão e assinatura inicial; não realiza análise completa do conteúdo. Faça backup do banco e da pasta media juntos.

As unidades são uma lista inicial configurável em portal/models.py. Responsável, horário e parceiro permanecem sem informação até que dados reais sejam fornecidos. Os totais começam em zero e são calculados a partir dos registros salvos. Cada envio cria um registro e seus valores são somados no mês.

Configuração para desenvolvimento local. Antes de publicar, configure SECRET_KEY por variável de ambiente, DEBUG=False, ALLOWED_HOSTS, HTTPS, arquivos estáticos e autenticação adequada ao ambiente.
