# MFO Brasil — Dashboard de Inteligência de Mercado

Dashboard automático de MFOs e Gestores de Patrimônio brasileiros, alimentado por dados oficiais da CVM.

## Como funciona

```
Toda segunda-feira, às 07h:
  GitHub Actions → baixa CSV da CVM → processa → gera docs/index.html → publica no GitHub Pages
```

O link do dashboard nunca muda. Os dados se atualizam sozinhos.

---

## Setup em 5 passos

### 1. Fork ou clone este repositório

```bash
git clone https://github.com/SEU_USUARIO/mfo-dashboard.git
cd mfo-dashboard
```

### 2. Ative o GitHub Pages

No seu repositório no GitHub:
- Vá em **Settings → Pages**
- Em **Source**, selecione: `Deploy from a branch`
- Branch: `main` / Folder: `/docs`
- Clique em **Save**

Após alguns segundos, o link aparece:
`https://SEU_USUARIO.github.io/mfo-dashboard/`

### 3. Ative o GitHub Actions

- Vá em **Actions** no seu repositório
- Clique em **"I understand my workflows, go ahead and enable them"**

Pronto. O workflow vai rodar automaticamente toda segunda-feira.

### 4. Rodar a primeira vez (dados imediatos)

Na aba **Actions**, clique no workflow **"Atualizar Dashboard MFO"** e depois em **"Run workflow"**.
Em ~2 minutos o dashboard estará ao vivo.

### 5. (Opcional) Rodar localmente

```bash
pip install pandas requests
python src/build_dashboard.py
# Abre docs/index.html no browser
```

---

## O que o dashboard mostra

| Métrica | Fonte |
|---|---|
| Total de firmas ativas | CVM Dados Abertos — `ADM_CART` |
| MFOs identificados | Heurística: nome + tipo de gestão |
| Score M&A (0–10) | Modelo proprietário (sanções + idade + UF + contato) |
| Evolução histórica | Contagem de registros por ano |
| Concentração por UF | Filtro de MFOs por estado |
| Sanções CVM | CVM Dados Abertos — `PAS` |

### Como os MFOs são identificados

A CVM não tem uma categoria formal "MFO". A identificação usa heurística:

1. **Palavras-chave no nome**: `family office`, `patrimônio`, `wealth`, `familiar`, `private`, etc.
2. **Tipo de gestão**: campo `TP_GEST` contendo `patrimônio` ou equivalentes

Para calibrar com firmas que você conhece, edite `MFO_KEYWORDS` em `src/build_dashboard.py`.

### Score M&A

| Critério | Peso |
|---|---|
| Ausência de sanções CVM | 25% |
| Tempo de registro (5–15 anos) | 25% |
| Classificado como MFO | 20% |
| Localização SP/RJ | 10% |
| Site cadastrado | 5% |
| Email cadastrado | 5% |

---

## Fontes de dados

| Fonte | URL | Atualização |
|---|---|---|
| Administradores de carteira | `dados.cvm.gov.br/dados/ADM_CART/CAD/DADOS/` | Semanal |
| Consultores de valores mobiliários | `dados.cvm.gov.br/dados/CONSUL_VALOR/CAD/DADOS/` | Semanal |
| Processos sancionadores | `dados.cvm.gov.br/dados/PAS/DADOS/` | Diária |

---

## Estrutura do repositório

```
mfo-dashboard/
├── .github/
│   └── workflows/
│       └── update_dashboard.yml   ← agendamento automático
├── src/
│   └── build_dashboard.py         ← ETL + gerador de HTML
├── docs/
│   ├── index.html                 ← dashboard (gerado automaticamente)
│   └── mfos.csv                   ← CSV completo para download
└── README.md
```

---

## Enriquecimento futuro

Para adicionar AuM estimado via fundos administrados (ANBIMA/CVM):

```python
# No build_dashboard.py, adicionar após a etapa de coleta:
CVM_FUNDOS_URL = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/inf_cadastral_fi.csv"
df_fundos = fetch_csv(CVM_FUNDOS_URL, "Cadastro de Fundos")
# Cruzar df_fundos["CNPJ_ADMIN"] com df_mfo["CNPJ_CPF"]
# Somar Patrimonio_Liquido por administrador
```

---

*Dados: CVM Dados Abertos (dados.cvm.gov.br). Este repositório não constitui recomendação de investimento.*
