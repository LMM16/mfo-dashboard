"""
MFO Brasil — Dashboard Builder
Baixa dados da CVM, identifica MFOs, gera HTML estático em docs/index.html
"""

import pandas as pd
import requests
import json
import re
import sys
from datetime import datetime, date
from io import StringIO
from pathlib import Path

# ─── Configuração ────────────────────────────────────────────────────────────

DOCS_DIR = Path(__file__).parent.parent / "docs"
DOCS_DIR.mkdir(exist_ok=True)

# URLs CVM Dados Abertos — verificadas em Mar/2026
# Administradores de carteira (gestor de recursos + patrimônio)
CVM_ADM_URLS = [
    "https://dados.cvm.gov.br/dados/ADM_CART/CAD/DADOS/cad_adm_cart.csv",
    "https://dados.cvm.gov.br/dados/ADM_CART/CAD/DADOS/cad_adm_cart_pj.csv",
    "https://dados.cvm.gov.br/dados/ADM_CART/CAD/DADOS/cad_adm_cart_pf.csv",
]
# Consultores de valores mobiliários
CVM_CONSUL_URLS = [
    "https://dados.cvm.gov.br/dados/CONSUL_VALOR/CAD/DADOS/cad_consul_val.csv",
    "https://dados.cvm.gov.br/dados/CONSUL_VALOR/CAD/DADOS/cad_consul_val_pj.csv",
    "https://dados.cvm.gov.br/dados/CONSUL_VALOR/CAD/DADOS/cad_consul_val_pf.csv",
]
# Processos sancionadores
CVM_PAS_URLS = [
    "https://dados.cvm.gov.br/dados/PAS/DADOS/pas_adm_responsavel.csv",
    "https://dados.cvm.gov.br/dados/PAS/DADOS/pas.csv",
]

# Palavras-chave para identificar MFOs no nome social
MFO_KEYWORDS = [
    "family office", "family", "patrimônio", "patrimonio",
    "wealth", "familiar", "multifamily", "multi-family",
    "gestão patrimonial", "gestao patrimonial",
    "private wealth", "private", "fortune",
]

# Tipos de gestão que indicam foco em patrimônio (campo TP_GEST ou equivalente)
MFO_TIPO_GEST = ["gestor de patrimônio", "patrimônio", "carteira administrada"]

# ─── Coleta ──────────────────────────────────────────────────────────────────

def fetch_csv(url: str, label: str) -> pd.DataFrame:
    print(f"  Baixando {label}...")
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        # CVM usa latin-1 com separador ;
        df = pd.read_csv(StringIO(resp.content.decode("latin-1")), sep=";", dtype=str)
        df.columns = [c.strip().upper() for c in df.columns]
        print(f"    → {len(df)} linhas, colunas: {list(df.columns)}")
        return df
    except Exception as e:
        print(f"    ERRO ao baixar {label}: {e}")
        return pd.DataFrame()

# ─── Identificação de MFOs ───────────────────────────────────────────────────

def is_mfo(row: pd.Series) -> bool:
    """Heurística multicritério para identificar MFOs."""
    nome = str(row.get("NOME_SOCIAL", "") or row.get("NOME", "")).lower()
    tipo = str(row.get("TP_GEST", "") or row.get("CATEGORIA", "")).lower()

    # Critério 1: palavra-chave no nome
    for kw in MFO_KEYWORDS:
        if kw in nome:
            return True

    # Critério 2: tipo de gestão patrimonial
    for t in MFO_TIPO_GEST:
        if t in tipo:
            return True

    return False

def classify_firma(row: pd.Series) -> str:
    if is_mfo(row):
        return "MFO/Wealth Management"
    tipo = str(row.get("TP_GEST", "") or "").lower()
    if "gestor" in tipo or "fundo" in tipo:
        return "Gestor de Recursos"
    return "Consultor CVM"

# ─── Normalização ────────────────────────────────────────────────────────────

def normalize_adm(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza o DataFrame de administradores para schema comum."""
    if df.empty:
        return df

    # Mapeamento defensivo de colunas — CVM pode mudar nomes
    col_map = {
        "NOME_SOCIAL":    ["NOME_SOCIAL", "NOME", "DENOM_SOCIAL"],
        "CNPJ_CPF":       ["CNPJ_CPF", "CNPJ", "CPF_CNPJ"],
        "SITUACAO":       ["SITUACAO", "SIT"],
        "DT_REGISTRO":    ["DT_REGISTRO", "DT_REG", "DATA_REGISTRO"],
        "UF":             ["UF", "ESTADO"],
        "MUNICIPIO":      ["MUNICIPIO", "CIDADE", "MUN"],
        "TP_GEST":        ["TP_GEST", "TIPO_GEST", "CATEGORIA", "TP_CATEGORIA"],
        "EMAIL":          ["EMAIL", "EMAIL_RESP"],
        "SITE":           ["SITE", "SITE_WEB", "URL"],
        "TELEFONE":       ["TELEFONE", "TEL"],
    }

    out = pd.DataFrame()
    for target, candidates in col_map.items():
        for c in candidates:
            if c in df.columns:
                out[target] = df[c]
                break
        if target not in out.columns:
            out[target] = ""

    out["FONTE"] = "ADM_CART"
    return out.fillna("")

def normalize_consul(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza o DataFrame de consultores."""
    if df.empty:
        return df

    col_map = {
        "NOME_SOCIAL":    ["NOME_SOCIAL", "NOME", "DENOM_SOCIAL"],
        "CNPJ_CPF":       ["CNPJ_CPF", "CNPJ", "CPF_CNPJ"],
        "SITUACAO":       ["SITUACAO", "SIT"],
        "DT_REGISTRO":    ["DT_REGISTRO", "DT_REG", "DATA_REGISTRO"],
        "UF":             ["UF", "ESTADO"],
        "MUNICIPIO":      ["MUNICIPIO", "CIDADE"],
        "TP_GEST":        ["TP_GEST", "TIPO_GEST", "CATEGORIA"],
        "EMAIL":          ["EMAIL"],
        "SITE":           ["SITE", "SITE_WEB"],
        "TELEFONE":       ["TELEFONE", "TEL"],
    }

    out = pd.DataFrame()
    for target, candidates in col_map.items():
        for c in candidates:
            if c in df.columns:
                out[target] = df[c]
                break
        if target not in out.columns:
            out[target] = ""

    out["FONTE"] = "CONSUL_VALOR"
    return out.fillna("")

# ─── Sanções ─────────────────────────────────────────────────────────────────

def build_sancoes_map(df_pas: pd.DataFrame) -> dict:
    """Retorna {cnpj_or_cpf: count_of_pas}"""
    if df_pas.empty:
        return {}
    # Tenta encontrar coluna com identificador
    for col in ["CNPJ_CPF", "CPF_CNPJ", "CNPJ", "CPF"]:
        if col in df_pas.columns:
            return df_pas[col].value_counts().to_dict()
    return {}

# ─── Score M&A ───────────────────────────────────────────────────────────────

def calc_score(row: pd.Series, sancoes_map: dict) -> float:
    """
    Modelo de scoring 0-10 para priorização de aquisição.
    Ajuste os pesos conforme sua tese de M&A.
    """
    score = 0.0

    # Sanções (max 2.5 pts — menos sanções = melhor)
    cnpj = str(row.get("CNPJ_CPF", ""))
    n_pas = sancoes_map.get(cnpj, 0)
    if n_pas == 0:
        score += 2.5
    elif n_pas == 1:
        score += 1.0

    # Anos de registro (max 2.5 pts — janela ideal 5-15 anos)
    try:
        dt_raw = str(row.get("DT_REGISTRO", ""))
        ano = int(dt_raw[:4]) if dt_raw and dt_raw != "nan" else 0
        anos = date.today().year - ano if ano > 2000 else 0
        if 5 <= anos <= 15:
            score += 2.5
        elif 3 <= anos < 5 or 15 < anos <= 20:
            score += 1.5
        elif anos > 0:
            score += 0.5
    except Exception:
        pass

    # É MFO identificado (2.0 pts)
    if row.get("CLASSIFICACAO") == "MFO/Wealth Management":
        score += 2.0

    # Localização estratégica SP/RJ (1.0 pt)
    uf = str(row.get("UF", "")).strip().upper()
    if uf in ("SP", "RJ"):
        score += 1.0
    elif uf in ("MG", "RS", "PR", "DF"):
        score += 0.5

    # Tem site cadastrado (0.5 pt — sinal de estrutura)
    if str(row.get("SITE", "")).strip() not in ("", "nan", "N/A"):
        score += 0.5

    # Tem email cadastrado (0.5 pt)
    if str(row.get("EMAIL", "")).strip() not in ("", "nan", "N/A"):
        score += 0.5

    return round(min(score, 10.0), 1)

# ─── Pipeline principal ──────────────────────────────────────────────────────

def main():
    print("=== MFO Brasil Dashboard Builder ===")
    print(f"Data de referência: {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")

    print("1. Coletando dados da CVM...")

    def fetch_first(urls, label):
        for url in urls:
            df = fetch_csv(url, label)
            if not df.empty:
                return df
        print(f"  AVISO: nenhuma URL funcionou para {label}")
        return pd.DataFrame()

    df_adm_raw    = fetch_first(CVM_ADM_URLS,    "Administradores de Carteira")
    df_consul_raw = fetch_first(CVM_CONSUL_URLS, "Consultores de Valores Mobiliários")
    df_pas_raw    = fetch_first(CVM_PAS_URLS,    "Processos Sancionadores")

    print("\n2. Normalizando schemas...")
    df_adm    = normalize_adm(df_adm_raw)
    df_consul = normalize_consul(df_consul_raw)

    print("\n3. Consolidando universo...")
    df = pd.concat([df_adm, df_consul], ignore_index=True)
    if df.empty:
        print("   ERRO: nenhum dado coletado. Verifique as URLs da CVM.")
        import sys; sys.exit(1)
    # drop_duplicates só se coluna existir
    if "CNPJ_CPF" in df.columns:
        df = df.drop_duplicates(subset=["CNPJ_CPF"])
    print(f"   Total de registros únicos: {len(df)}")

    # Apenas ativos — coluna SITUACAO pode ter nome diferente dependendo da fonte
    if "SITUACAO" in df.columns:
        df_ativos = df[df["SITUACAO"].str.upper().str.contains("AUTORIZADO|ATIVO", na=False)].copy()
    else:
        print("   AVISO: coluna SITUACAO nao encontrada — usando todos os registros")
        df_ativos = df.copy()
    print(f"   Ativos: {len(df_ativos)}")

    print("\n4. Classificando MFOs...")
    df_ativos["CLASSIFICACAO"] = df_ativos.apply(classify_firma, axis=1)
    n_mfo = (df_ativos["CLASSIFICACAO"] == "MFO/Wealth Management").sum()
    print(f"   MFOs identificados: {n_mfo}")

    print("\n5. Calculando scores M&A...")
    sancoes_map = build_sancoes_map(df_pas_raw)
    df_ativos["SCORE_MA"] = df_ativos.apply(lambda r: calc_score(r, sancoes_map), axis=1)
    df_ativos["N_SANCOES"] = df_ativos["CNPJ_CPF"].map(sancoes_map).fillna(0).astype(int)

    print("\n6. Preparando dados para o dashboard...")
    df_mfo = df_ativos[df_ativos["CLASSIFICACAO"] == "MFO/Wealth Management"].copy()
    df_mfo = df_mfo.sort_values("SCORE_MA", ascending=False).reset_index(drop=True)

    # Evolução histórica — conta registros por ano
    df_ativos["ANO_REG"] = df_ativos["DT_REGISTRO"].str[:4]
    evolucao = (
        df_ativos.groupby("ANO_REG")
        .size()
        .reset_index(name="count")
    )
    evolucao = evolucao[evolucao["ANO_REG"].str.match(r"^\d{4}$")]
    evolucao = evolucao.sort_values("ANO_REG")

    # Distribuição geográfica MFOs
    geo = df_mfo["UF"].value_counts().head(10).to_dict()

    # Tipo breakdown
    tipo_dist = df_ativos["CLASSIFICACAO"].value_counts().to_dict()

    print("\n7. Gerando HTML...")
    html = build_html(df_mfo, df_ativos, evolucao, geo, tipo_dist, sancoes_map)

    out_path = DOCS_DIR / "index.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"   → Salvo em {out_path}")

    # Salva CSV de MFOs para download
    csv_path = DOCS_DIR / "mfos.csv"
    df_mfo.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"   → CSV salvo em {csv_path}")

    print("\n=== Concluído! ===")
    return df_mfo

# ─── Geração do HTML ─────────────────────────────────────────────────────────

def build_html(df_mfo, df_all, evolucao, geo, tipo_dist, sancoes_map):
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    n_total   = len(df_all)
    n_mfo     = len(df_mfo)
    n_alvos   = (df_mfo["SCORE_MA"] >= 7).sum()
    n_novos   = (df_all["DT_REGISTRO"].str[:4] == str(date.today().year)).sum()

    # Top 50 para a tabela
    top = df_mfo.head(50)

    rows_html = ""
    for i, (_, r) in enumerate(top.iterrows(), 1):
        score = r["SCORE_MA"]
        score_class = "score-high" if score >= 8 else ("score-mid" if score >= 6 else "score-low")
        sancoes = r["N_SANCOES"]
        san_tag = (
            '<span class="tag tag-ok">Nenhuma</span>' if sancoes == 0
            else f'<span class="tag tag-warn">{sancoes} PAS</span>' if sancoes == 1
            else f'<span class="tag tag-bad">{sancoes} PAS</span>'
        )
        dt_raw = str(r.get("DT_REGISTRO", ""))
        ano_reg = dt_raw[:4] if dt_raw and dt_raw != "nan" else "—"
        uf = str(r.get("UF", "—")).strip() or "—"
        cnpj = str(r.get("CNPJ_CPF", "")).strip()
        nome = str(r.get("NOME_SOCIAL", "")).strip().title()
        email = str(r.get("EMAIL", "")).strip()
        email_html = f'<a href="mailto:{email}" style="color:var(--gold);font-size:9px">{email[:28]}…</a>' if email and email != "nan" else '<span style="color:var(--subtle)">—</span>'
        rows_html += f"""
        <tr>
          <td><span class="mono subtle">{i:02d}</span></td>
          <td><div class="firm-name">{nome or "—"}</div><div class="mono micro subtle">{cnpj}</div></td>
          <td><span class="mono small">{uf}</span></td>
          <td><span class="mono micro">{ano_reg}</span></td>
          <td>{san_tag}</td>
          <td><span class="score-dot {score_class}">{score}</span></td>
          <td>{email_html}</td>
        </tr>"""

    # Chart data
    anos_evo   = json.dumps(evolucao["ANO_REG"].tolist())
    counts_evo = json.dumps(evolucao["count"].tolist())
    geo_labels = json.dumps(list(geo.keys()))
    geo_vals   = json.dumps(list(geo.values()))
    tipo_labels = json.dumps(list(tipo_dist.keys()))
    tipo_vals   = json.dumps(list(tipo_dist.values()))

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MFO Brasil — Inteligência de Mercado</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root {{
    --ink:#0d0d0d; --ink2:#1e1e1e; --muted:#5a5a5a; --subtle:#a0a0a0;
    --line:#e0ddd8; --bg:#f5f3ee; --card:#fdfcfa;
    --gold:#b8965a; --gold-pale:#f5eed9;
    --green:#2d6a4f; --green-pale:#d8ede2;
    --red:#9b2335; --red-pale:#f5dde0;
    --blue:#1a3a6b; --blue-pale:#dae3f5;
  }}
  *,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
  html{{font-size:14px}}
  body{{font-family:'Syne',sans-serif;background:var(--bg);color:var(--ink);min-height:100vh}}
  .shell{{display:grid;grid-template-columns:210px 1fr;min-height:100vh}}
  .sidebar{{background:var(--ink);color:#fff;display:flex;flex-direction:column;padding:28px 0;position:sticky;top:0;height:100vh;overflow-y:auto}}
  .brand{{padding:0 22px 24px;border-bottom:1px solid #222}}
  .brand-label{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.12em;color:var(--gold);text-transform:uppercase;margin-bottom:5px}}
  .brand-name{{font-size:20px;font-weight:800;letter-spacing:-.02em}}
  .brand-name span{{color:var(--gold)}}
  .brand-sub{{font-family:'DM Mono',monospace;font-size:9px;color:#444;margin-top:3px}}
  .nav{{padding:16px 0;flex:1}}
  .nav-sec{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.1em;color:#333;text-transform:uppercase;padding:12px 22px 5px}}
  .nav-item{{display:flex;align-items:center;gap:9px;padding:8px 22px;cursor:pointer;font-size:12px;font-weight:600;color:#666;border-left:3px solid transparent;transition:all .15s}}
  .nav-item:hover,.nav-item.active{{color:#fff;border-left-color:var(--gold);background:#141414}}
  .sid-foot{{padding:18px 22px;border-top:1px solid #1a1a1a;font-family:'DM Mono',monospace;font-size:9px;color:#333;line-height:1.8}}
  .dot{{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--green);margin-right:4px;vertical-align:middle}}
  .main{{overflow-y:auto}}
  .topbar{{background:var(--card);border-bottom:1px solid var(--line);padding:14px 28px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:10}}
  .topbar-t{{font-size:14px;font-weight:700;letter-spacing:-.01em}}
  .topbar-m{{font-family:'DM Mono',monospace;font-size:9px;color:var(--subtle);margin-top:2px}}
  .updated{{font-family:'DM Mono',monospace;font-size:9px;background:var(--green-pale);color:var(--green);padding:4px 10px;border-radius:20px}}
  .content{{padding:24px 28px}}
  .kpi-strip{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}}
  .kpi{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;position:relative;overflow:hidden;transition:box-shadow .2s}}
  .kpi:hover{{box-shadow:0 4px 20px rgba(184,150,90,.15)}}
  .kpi-l{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.08em;color:var(--subtle);text-transform:uppercase;margin-bottom:8px}}
  .kpi-v{{font-size:28px;font-weight:800;letter-spacing:-.03em;line-height:1}}
  .kpi-d{{font-family:'DM Mono',monospace;font-size:10px;margin-top:5px}}
  .up{{color:var(--green)}} .gold{{color:var(--gold)}}
  .grid-3{{display:grid;grid-template-columns:2fr 1fr 1fr;gap:16px;margin-bottom:24px}}
  .grid-2{{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}}
  .card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:20px 22px}}
  .card-hd{{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:16px}}
  .card-t{{font-size:12px;font-weight:700;letter-spacing:-.01em}}
  .card-sub{{font-family:'DM Mono',monospace;font-size:9px;color:var(--subtle);margin-top:2px}}
  .ch{{position:relative}}
  .sec-hd{{display:flex;align-items:center;gap:10px;margin-bottom:14px}}
  .sec-hd h2{{font-size:13px;font-weight:700}}
  .sec-cnt{{font-family:'DM Mono',monospace;font-size:10px;color:var(--subtle)}}
  .btn{{font-family:'DM Mono',monospace;font-size:10px;padding:6px 14px;border:1px solid var(--line);border-radius:6px;background:var(--card);cursor:pointer;color:var(--muted);transition:all .15s;text-decoration:none;display:inline-block}}
  .btn:hover{{background:var(--ink);color:#fff;border-color:var(--ink)}}
  .btn.gold{{background:var(--gold);color:#fff;border-color:var(--gold)}}
  .ml-auto{{margin-left:auto}}
  .table-wrap{{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;margin-bottom:24px}}
  table{{width:100%;border-collapse:collapse}}
  thead th{{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.08em;color:var(--subtle);text-transform:uppercase;padding:9px 20px;text-align:left;background:var(--bg);border-bottom:1px solid var(--line);white-space:nowrap}}
  tbody tr{{cursor:pointer;transition:background .1s}}
  tbody tr:hover{{background:var(--gold-pale)}}
  tbody tr:not(:last-child){{border-bottom:1px solid var(--line)}}
  tbody td{{padding:11px 20px;font-size:12px;vertical-align:middle}}
  .firm-name{{font-weight:700;font-size:12px;letter-spacing:-.01em}}
  .mono{{font-family:'DM Mono',monospace}}
  .micro{{font-size:9px}} .small{{font-size:11px}} .subtle{{color:var(--subtle)}}
  .tag{{display:inline-flex;align-items:center;height:20px;padding:0 7px;border-radius:4px;font-family:'DM Mono',monospace;font-size:9px;font-weight:500;white-space:nowrap}}
  .tag-ok{{background:var(--green-pale);color:var(--green)}}
  .tag-warn{{background:#fff3cd;color:#7a5c00}}
  .tag-bad{{background:var(--red-pale);color:var(--red)}}
  .score-dot{{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;font-family:'DM Mono',monospace;font-size:10px;font-weight:500}}
  .score-high{{background:var(--green-pale);color:var(--green)}}
  .score-mid{{background:var(--gold-pale);color:#7a5c00}}
  .score-low{{background:var(--red-pale);color:var(--red)}}
  .blist{{list-style:none}}
  .bitem{{display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:1px solid var(--line);font-size:11px}}
  .bitem:last-child{{border:none}}
  .bcolor{{width:9px;height:9px;border-radius:2px;flex-shrink:0}}
  .bname{{flex:1;font-weight:600}}
  .bcnt,.bpct{{font-family:'DM Mono',monospace;font-size:10px;color:var(--muted)}}
  .bpct{{width:30px;text-align:right}}
  .fnote{{font-family:'DM Mono',monospace;font-size:9px;color:var(--subtle);text-align:center;padding:20px 0 4px;border-top:1px solid var(--line);margin-top:8px;line-height:1.8}}
  a{{color:inherit}}
</style>
</head>
<body>
<div class="shell">
<aside class="sidebar">
  <div class="brand">
    <div class="brand-label">Inteligência de Mercado</div>
    <div class="brand-name">MFO<span>BR</span></div>
    <div class="brand-sub">CVM · ANBIMA · RFB</div>
  </div>
  <nav class="nav">
    <div class="nav-sec">Análise</div>
    <div class="nav-item active">◈ Dashboard</div>
    <div class="nav-item">≡ Todas as firmas</div>
    <div class="nav-item">◇ Scoring M&A</div>
    <div class="nav-item">↗ Evolução</div>
    <div class="nav-sec">Dados</div>
    <div class="nav-item"><a href="mfos.csv" style="color:inherit;text-decoration:none">↓ Exportar CSV</a></div>
  </nav>
  <div class="sid-foot">
    <span class="dot"></span>Dados CVM ao vivo<br>
    Atualização semanal<br>
    GitHub Actions
  </div>
</aside>
<main class="main">
  <div class="topbar">
    <div>
      <div class="topbar-t">MFOs &amp; Gestores de Patrimônio — Brasil</div>
      <div class="topbar-m">Cadastro CVM · Dados Abertos · Ref. {now}</div>
    </div>
    <span class="updated">⬤ Atualizado {now}</span>
  </div>
  <div class="content">

    <!-- KPIs -->
    <div class="kpi-strip">
      <div class="kpi">
        <div class="kpi-l">Firmas ativas (CVM)</div>
        <div class="kpi-v">{n_total:,}</div>
        <div class="kpi-d up">Adm. carteira + Consultores</div>
      </div>
      <div class="kpi">
        <div class="kpi-l">MFOs identificados</div>
        <div class="kpi-v">{n_mfo:,}</div>
        <div class="kpi-d up">Heurística multicritério</div>
      </div>
      <div class="kpi">
        <div class="kpi-l">Alvos M&amp;A (score ≥ 7)</div>
        <div class="kpi-v">{n_alvos:,}</div>
        <div class="kpi-d gold">⬤ Alta prioridade</div>
      </div>
      <div class="kpi">
        <div class="kpi-l">Novos registros ({date.today().year})</div>
        <div class="kpi-v">{n_novos:,}</div>
        <div class="kpi-d up">Ano corrente</div>
      </div>
    </div>

    <!-- Charts -->
    <div class="grid-3">
      <div class="card">
        <div class="card-hd">
          <div><div class="card-t">Crescimento da indústria</div>
          <div class="card-sub">Registros ativos por ano · CVM</div></div>
        </div>
        <div class="ch" style="height:180px"><canvas id="growthChart"></canvas></div>
      </div>
      <div class="card">
        <div class="card-hd"><div>
          <div class="card-t">Perfil do universo</div>
          <div class="card-sub">Por tipo de gestão</div>
        </div></div>
        <div class="ch" style="height:110px"><canvas id="typeChart"></canvas></div>
        <ul class="blist" style="margin-top:10px">
          {"".join(f'<li class="bitem"><span class="bcolor" style="background:{c}"></span><span class="bname">{k}</span><span class="bcnt">{v}</span><span class="bpct">{round(100*v/max(sum(tipo_dist.values()),1))}%</span></li>' for (k,v),c in zip(sorted(tipo_dist.items(), key=lambda x:-x[1]), ["#b8965a","#1a3a6b","#4a2d7a","#2d6a4f","#888"]))}
        </ul>
      </div>
      <div class="card">
        <div class="card-hd"><div>
          <div class="card-t">Concentração por UF</div>
          <div class="card-sub">Top estados · MFOs</div>
        </div></div>
        <div class="ch" style="height:180px"><canvas id="stateChart"></canvas></div>
      </div>
    </div>

    <!-- Tabela -->
    <div class="sec-hd">
      <h2>Ranking MFOs — Score M&amp;A</h2>
      <span class="sec-cnt">Top 50 de {n_mfo} identificados</span>
      <div class="ml-auto" style="display:flex;gap:8px">
        <a href="mfos.csv" class="btn gold">↓ Baixar CSV completo ({n_mfo} firmas)</a>
      </div>
    </div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th><th>Firma</th><th>UF</th><th>Registro</th>
            <th>Sanções</th><th>Score M&A</th><th>Contato</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>

    <div class="fnote">
      Fonte: CVM Dados Abertos (dados.cvm.gov.br) · Atualização automática via GitHub Actions · {now}<br>
      MFOs identificados por heurística: nome social + tipo de gestão. Score M&A: modelo proprietário 0–10.<br>
      Este dashboard não constitui recomendação de investimento ou assessoria de M&A.
    </div>
  </div>
</main>
</div>
<script>
const mono = "'DM Mono',monospace";
const gold = '#b8965a', ink = '#0d0d0d', lineC = '#e0ddd8';

new Chart(document.getElementById('growthChart'), {{
  type:'line',
  data:{{
    labels:{anos_evo},
    datasets:[{{
      label:'Todos os registros',
      data:{counts_evo},
      borderColor:ink, backgroundColor:'transparent', borderWidth:2, pointRadius:0, tension:.4
    }}]
  }},
  options:{{
    responsive:true, maintainAspectRatio:false,
    plugins:{{ legend:{{ display:false }} }},
    scales:{{
      x:{{ grid:{{ color:lineC }}, ticks:{{ font:{{ family:mono, size:8 }}, color:'#aaa', maxTicksLimit:8 }} }},
      y:{{ grid:{{ color:lineC }}, ticks:{{ font:{{ family:mono, size:8 }}, color:'#aaa' }} }}
    }}
  }}
}});

new Chart(document.getElementById('typeChart'), {{
  type:'doughnut',
  data:{{
    labels:{tipo_labels},
    datasets:[{{ data:{tipo_vals}, backgroundColor:['#b8965a','#1a3a6b','#4a2d7a','#2d6a4f','#888'], borderWidth:0 }}]
  }},
  options:{{ responsive:true, maintainAspectRatio:false, cutout:'65%', plugins:{{ legend:{{ display:false }} }} }}
}});

new Chart(document.getElementById('stateChart'), {{
  type:'bar',
  data:{{
    labels:{geo_labels},
    datasets:[{{ data:{geo_vals}, backgroundColor:gold+'cc', borderWidth:0, borderRadius:3 }}]
  }},
  options:{{
    responsive:true, maintainAspectRatio:false,
    plugins:{{ legend:{{ display:false }} }},
    scales:{{
      x:{{ grid:{{ display:false }}, ticks:{{ font:{{ family:mono, size:9 }}, color:'#aaa' }} }},
      y:{{ grid:{{ color:lineC }}, ticks:{{ font:{{ family:mono, size:9 }}, color:'#aaa' }} }}
    }}
  }}
}});
</script>
</body>
</html>"""

if __name__ == "__main__":
    main()
