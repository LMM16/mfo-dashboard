"""
MFO Brasil — Dashboard Builder
Gera: docs/index.html + docs/firma/{cnpj}.html para cada MFO
"""
import pandas as pd
import requests, zipfile, io, json, sys, re
from datetime import datetime, date
from pathlib import Path

DOCS_DIR  = Path(__file__).parent.parent / "docs"
FIRMA_DIR = DOCS_DIR / "firma"
DOCS_DIR.mkdir(exist_ok=True)
FIRMA_DIR.mkdir(exist_ok=True)

CVM_ADM_URL    = "https://dados.cvm.gov.br/dados/ADM_CART/CAD/DADOS/cad_adm_cart.zip"
CVM_CONSUL_URL = "https://dados.cvm.gov.br/dados/CONSUL_VALOR/CAD/DADOS/cad_consul_val.zip"

MFO_KEYWORDS = [
    "family office", "family", "patrimônio", "patrimonio", "wealth",
    "familiar", "multifamily", "multi-family", "gestão patrimonial",
    "gestao patrimonial", "private wealth", "private", "fortune",
    "multi family", "mfo",
]

KNOWN_MFOS = [
    "1618", "051 capital", "adduntia", "aeternus", "amb family",
    "aqua wealth", "aram capital", "arbitral", "attimo", "aware",
    "azimut", "bevas", "bnr family", "brasil wm", "capital advisors",
    "capri family", "carpa family", "centuria", "cimo family",
    "consist mfo", "criteria", "ekho", "eleva invest", "enseada family",
    "ethos investimentos", "etrnty", "fd international", "g5 partners",
    "galacticos", "genesis", "ghia", "grupo independiente",
    "gutierrez group", "hieron", "horizonte mx", "ibbra", "incipio",
    "investport", "jera capital", "legend", "lombard odier", "lxg family",
    "mandatto", "setta", "mercury", "mfo advisors", "milenium family",
    "misti capital", "moma family", "naopim", "nau capital", "oikos",
    "orion advisors", "oriz partners", "patagonia capital", "perfin",
    "portofino", "portogallo", "pragma", "privatto", "promecap",
    "sastre", "seven pounds", "sg mfo", "sonata", "sow capital",
    "sten capital", "sten gestao", "taler gestao", "tempus asset",
    "tera capital", "trafalgar", "troon capital", "turim",
    "veneto family", "vokin", "we capital", "whg", "wisdom family",
    "wright", "vitra", "ventura",
]

CSS = """<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap" rel="stylesheet">
<style>
:root{--ink:#0d0d0d;--muted:#5a5a5a;--subtle:#a0a0a0;--line:#e0ddd8;--bg:#f5f3ee;--card:#fdfcfa;--gold:#b8965a;--gold-pale:#f5eed9;--green:#2d6a4f;--green-pale:#d8ede2;--red:#9b2335;--red-pale:#f5dde0;--blue:#1a3a6b;--blue-pale:#dae3f5}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Syne',sans-serif;background:var(--bg);color:var(--ink);min-height:100vh}
.shell{display:grid;grid-template-columns:210px 1fr;min-height:100vh}
.sidebar{background:var(--ink);color:#fff;display:flex;flex-direction:column;padding:28px 0;position:sticky;top:0;height:100vh}
.brand{padding:0 22px 24px;border-bottom:1px solid #222}
.brand-label{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.12em;color:var(--gold);text-transform:uppercase;margin-bottom:5px}
.brand-name{font-size:20px;font-weight:800;letter-spacing:-.02em}
.brand-name span{color:var(--gold)}
.brand-sub{font-family:'DM Mono',monospace;font-size:9px;color:#444;margin-top:3px}
.nav{padding:16px 0;flex:1}
.nav-sec{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.1em;color:#333;text-transform:uppercase;padding:12px 22px 5px}
.nav-item{display:flex;align-items:center;gap:9px;padding:8px 22px;font-size:12px;font-weight:600;color:#666;border-left:3px solid transparent;text-decoration:none;transition:all .15s}
.nav-item:hover,.nav-item.active{color:#fff;border-left-color:var(--gold);background:#141414}
.sid-foot{padding:18px 22px;border-top:1px solid #1a1a1a;font-family:'DM Mono',monospace;font-size:9px;color:#333;line-height:1.8}
.dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:var(--green);margin-right:4px;vertical-align:middle}
.main{overflow-y:auto}
.topbar{background:var(--card);border-bottom:1px solid var(--line);padding:14px 28px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:10}
.topbar-t{font-size:14px;font-weight:700}.topbar-m{font-family:'DM Mono',monospace;font-size:9px;color:var(--subtle);margin-top:2px}
.updated{font-family:'DM Mono',monospace;font-size:9px;background:var(--green-pale);color:var(--green);padding:4px 10px;border-radius:20px}
.content{padding:24px 28px}
.kpi-strip{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px}
.kpi-l{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.08em;color:var(--subtle);text-transform:uppercase;margin-bottom:8px}
.kpi-v{font-size:28px;font-weight:800;letter-spacing:-.03em;line-height:1}
.kpi-d{font-family:'DM Mono',monospace;font-size:10px;margin-top:5px;color:var(--green)}
.grid-3{display:grid;grid-template-columns:2fr 1fr 1fr;gap:16px;margin-bottom:24px}
.grid-2{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:20px 22px}
.card-t{font-size:12px;font-weight:700;margin-bottom:4px}.card-sub{font-family:'DM Mono',monospace;font-size:9px;color:var(--subtle);margin-bottom:16px}
.sec-hd{display:flex;align-items:center;gap:10px;margin-bottom:14px}
.sec-hd h2{font-size:13px;font-weight:700}.sec-cnt{font-family:'DM Mono',monospace;font-size:10px;color:var(--subtle)}
.ml-auto{margin-left:auto}
.btn{font-family:'DM Mono',monospace;font-size:10px;padding:6px 14px;border-radius:6px;background:var(--gold);color:#fff;text-decoration:none;display:inline-block}
.btn-outline{font-family:'DM Mono',monospace;font-size:10px;padding:6px 14px;border-radius:6px;border:1px solid var(--line);background:var(--card);color:var(--muted);text-decoration:none;display:inline-block}
.table-wrap{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden;margin-bottom:24px}
table{width:100%;border-collapse:collapse}
thead th{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.08em;color:var(--subtle);text-transform:uppercase;padding:9px 20px;text-align:left;background:var(--bg);border-bottom:1px solid var(--line);white-space:nowrap}
tbody tr{transition:background .1s;cursor:pointer}tbody tr:hover{background:var(--gold-pale)}
tbody tr:not(:last-child){border-bottom:1px solid var(--line)}
tbody td{padding:11px 20px;font-size:12px;vertical-align:middle}
.firm-name{font-weight:700;font-size:12px}
.mono{font-family:'DM Mono',monospace}.micro{font-size:9px}.small{font-size:11px}.subtle{color:var(--subtle)}
.score-dot{display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:50%;font-family:'DM Mono',monospace;font-size:10px;font-weight:500}
.score-high{background:var(--green-pale);color:var(--green)}.score-mid{background:var(--gold-pale);color:#7a5c00}.score-low{background:var(--red-pale);color:var(--red)}
.tag{display:inline-flex;align-items:center;height:20px;padding:0 8px;border-radius:4px;font-family:'DM Mono',monospace;font-size:9px;font-weight:500}
.tag-ok{background:var(--green-pale);color:var(--green)}.tag-warn{background:#fff3cd;color:#7a5c00}.tag-bad{background:var(--red-pale);color:var(--red)}
.tag-blue{background:var(--blue-pale);color:var(--blue)}
.blist{list-style:none;margin-top:12px}.bitem{display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid var(--line);font-size:11px}
.bitem:last-child{border:none}.bcolor{width:9px;height:9px;border-radius:2px;flex-shrink:0}.bname{flex:1;font-weight:600}.bcnt{font-family:'DM Mono',monospace;font-size:10px;color:var(--muted)}
.fnote{font-family:'DM Mono',monospace;font-size:9px;color:var(--subtle);text-align:center;padding:20px 0 4px;border-top:1px solid var(--line);margin-top:8px;line-height:1.8}
.firma-header{background:var(--ink);color:#fff;padding:32px 36px}
.firma-back{font-family:'DM Mono',monospace;font-size:10px;color:#666;text-decoration:none;display:inline-flex;align-items:center;gap:6px;margin-bottom:16px;transition:color .15s}
.firma-back:hover{color:var(--gold)}
.firma-nome{font-size:26px;font-weight:800;letter-spacing:-.02em;margin-bottom:6px}
.firma-cnpj{font-family:'DM Mono',monospace;font-size:11px;color:#555}
.firma-tags{display:flex;gap:8px;margin-top:12px;flex-wrap:wrap}
.firma-body{padding:28px 36px}
.info-row{display:flex;justify-content:space-between;align-items:center;padding:10px 0;border-bottom:1px solid var(--line);font-size:12px}
.info-row:last-child{border:none}
.info-label{font-family:'DM Mono',monospace;font-size:10px;color:var(--subtle);text-transform:uppercase;letter-spacing:.06em}
.info-val{font-weight:600;text-align:right;max-width:240px;word-break:break-word}
.score-bar-wrap{margin-bottom:14px}
.score-bar-label{display:flex;justify-content:space-between;font-size:11px;margin-bottom:4px}
.score-bar-label .pts{font-family:'DM Mono',monospace;font-size:10px;color:var(--muted)}
.score-bar{height:6px;border-radius:3px;background:var(--line)}
.score-bar-fill{height:6px;border-radius:3px;background:var(--gold)}
.socio-pill{display:inline-flex;align-items:center;background:var(--bg);border:1px solid var(--line);border-radius:20px;padding:5px 12px;font-size:11px;font-weight:600;margin:3px}
.resp-row{padding:10px 0;border-bottom:1px solid var(--line);font-size:12px}
.resp-row:last-child{border:none}
.resp-nome{font-weight:700;margin-bottom:2px}
.resp-tipo{font-family:'DM Mono',monospace;font-size:9px;color:var(--subtle)}
.score-big{font-size:48px;font-weight:800;letter-spacing:-.04em;color:var(--gold);line-height:1}
.score-label{font-family:'DM Mono',monospace;font-size:10px;color:var(--subtle);margin-top:4px}
</style>"""

SIDEBAR_TPL = """<aside class="sidebar">
  <div class="brand">
    <div class="brand-label">Inteligencia de Mercado</div>
    <div class="brand-name">MFO<span>BR</span></div>
    <div class="brand-sub">CVM · ANBIMA · RFB</div>
  </div>
  <nav class="nav">
    <div class="nav-sec">Analise</div>
    <a href="/mfo-dashboard/" class="nav-item ACTIVE_DASH">Dashboard</a>
    <div class="nav-sec">Dados</div>
    <a href="/mfo-dashboard/mfos.csv" class="nav-item">Exportar CSV</a>
  </nav>
  <div class="sid-foot"><span class="dot"></span>Dados CVM ao vivo<br>Atualizacao semanal<br>GitHub Actions</div>
</aside>"""


def fetch_zip(url, label):
    print(f"  Baixando {label}...")
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        return zipfile.ZipFile(io.BytesIO(resp.content))
    except Exception as e:
        print(f"    ERRO: {e}")
        return None


def read_csv_from_zip(z, filename):
    try:
        with z.open(filename) as f:
            df = pd.read_csv(f, sep=";", encoding="latin-1", dtype=str)
        df.columns = [c.strip().upper() for c in df.columns]
        return df.fillna("")
    except Exception as e:
        print(f"    ERRO ao ler {filename}: {e}")
        return pd.DataFrame()


def is_mfo(nome):
    n = nome.lower()
    return any(kw in n for kw in MFO_KEYWORDS) or any(kw in n for kw in KNOWN_MFOS)


def cnpj_slug(cnpj):
    return re.sub(r'\D', '', str(cnpj))


def score_detail(r):
    items = []
    total = 0.0
    try:
        ano  = int(str(r.get("DT_REGISTRO", ""))[:4])
        anos = date.today().year - ano
        if 5 <= anos <= 15:        pts, lbl = 2.5, f"{anos} anos (janela ideal)"
        elif anos > 15:            pts, lbl = 2.0, f"{anos} anos (senior)"
        elif 3 <= anos < 5:        pts, lbl = 1.5, f"{anos} anos (jovem)"
        elif anos > 0:             pts, lbl = 0.5, f"{anos} anos"
        else:                      pts, lbl = 0.0, "Data desconhecida"
    except:
        pts, lbl = 0.0, "Data desconhecida"
    items.append(("Tempo de registro", pts, 2.5, lbl)); total += pts

    pts = 2.5 if r.get("IS_MFO") else 0.0
    items.append(("Identificado como MFO", pts, 2.5, "Sim" if pts else "Nao")); total += pts

    uf = str(r.get("UF", "")).strip().upper()
    if uf in ("SP", "RJ"):                pts, lbl = 1.5, f"{uf} (mercado principal)"
    elif uf in ("MG", "RS", "PR", "DF"): pts, lbl = 0.5, uf
    else:                                 pts, lbl = 0.0, uf or "Outro"
    items.append(("Localizacao estrategica", pts, 1.5, lbl)); total += pts

    email = str(r.get("EMAIL", "")).strip()
    pts = 0.75 if email and email not in ("", "nan", "N/A") else 0.0
    items.append(("Email cadastrado", pts, 0.75, email[:30] if pts else "Nao")); total += pts

    site = str(r.get("SITE", "")).strip()
    pts = 0.75 if site and site not in ("", "nan", "N/A") else 0.0
    items.append(("Site cadastrado", pts, 0.75, site[:30] if pts else "Nao")); total += pts

    try:
        pl = float(str(r.get("PATRIM_LIQ", "")).replace(",", "."))
        if pl >= 50_000_000:   pts, lbl = 2.0, f"R$ {pl/1e6:.1f}M"
        elif pl >= 10_000_000: pts, lbl = 1.5, f"R$ {pl/1e6:.1f}M"
        elif pl >= 1_000_000:  pts, lbl = 1.0, f"R$ {pl/1e6:.1f}M"
        elif pl > 0:           pts, lbl = 0.5, f"R$ {pl/1e3:.0f}K"
        else:                  pts, lbl = 0.0, "Nao declarado"
    except:
        pts, lbl = 0.0, "Nao declarado"
    items.append(("Patrimonio da gestora (PL)", pts, 2.0, lbl)); total += pts

    return items, round(min(total, 10.0), 1)


def main():
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    print("=== MFO Brasil Dashboard Builder ===")
    print(f"Data: {now}\n")

    print("1. Coletando dados CVM...")
    z_adm = fetch_zip(CVM_ADM_URL, "ADM_CART")

    df_pj = df_socios = df_resp = pd.DataFrame()
    if z_adm:
        df_pj     = read_csv_from_zip(z_adm, "cad_adm_cart_pj.csv")
        df_socios = read_csv_from_zip(z_adm, "cad_adm_cart_socios.csv")
        df_resp   = read_csv_from_zip(z_adm, "cad_adm_cart_resp.csv")
        print(f"   PJ:{len(df_pj)} Socios:{len(df_socios)} Resp:{len(df_resp)}")

    socios_map = {}
    if not df_socios.empty and "CNPJ" in df_socios.columns:
        for cnpj, grp in df_socios.groupby("CNPJ"):
            socios_map[cnpj] = [s.strip() for s in grp["SOCIOS"].tolist() if s.strip()]

    resp_map = {}
    if not df_resp.empty and "CNPJ" in df_resp.columns:
        col_tipo = "TP_RESP" if "TP_RESP" in df_resp.columns else None
        for cnpj, grp in df_resp.groupby("CNPJ"):
            entries = []
            for _, row in grp.iterrows():
                nome = str(row.get("RESP", "")).strip()
                tipo = str(row.get(col_tipo, "")).strip() if col_tipo else ""
                if nome:
                    entries.append({"nome": nome, "tipo": tipo})
            resp_map[cnpj] = entries

    print("\n2. Normalizando...")
    rows = []
    for _, r in df_pj.iterrows():
        cnpj = str(r.get("CNPJ", "")).strip()
        rows.append(dict(
            NOME_SOCIAL=str(r.get("DENOM_SOCIAL", "") or r.get("DENOM_COMERC", "")).strip(),
            CNPJ_CPF=cnpj,
            SITUACAO=str(r.get("SIT", "")).strip(),
            DT_REGISTRO=str(r.get("DT_REG", "")).strip(),
            UF=str(r.get("UF", "")).strip(),
            MUNICIPIO=str(r.get("MUN", "")).strip(),
            CATEG_REG=str(r.get("CATEG_REG", "")).strip(),
            SUBCATEG=str(r.get("SUBCATEG_REG", "")).strip(),
            EMAIL=str(r.get("EMAIL", "")).strip(),
            SITE=str(r.get("SITE_ADMIN", "")).strip(),
            TELEFONE=str(r.get("TEL", "")).strip(),
            LOGRADOURO=str(r.get("LOGRADOURO", "")).strip(),
            COMPL=str(r.get("COMPL", "")).strip(),
            CEP=str(r.get("CEP", "")).strip(),
            PATRIM_LIQ=str(r.get("VL_PATRIM_LIQ", "")).strip(),
            DT_PATRIM=str(r.get("DT_PATRIM_LIQ", "")).strip(),
            CONTROLE=str(r.get("CONTROLE_ACIONARIO", "")).strip(),
        ))

    df = pd.DataFrame(rows).fillna("")
    df = df.drop_duplicates(subset=["CNPJ_CPF"])

    if "SITUACAO" in df.columns:
        df_ativos = df[df["SITUACAO"].str.upper().str.contains("FUNCIONAMENTO|AUTORIZADO|ATIVO", na=False)].copy()
    else:
        df_ativos = df.copy()
    print(f"   Ativos: {len(df_ativos)}")

    print("\n3. Identificando MFOs...")
    if df_ativos.empty or "NOME_SOCIAL" not in df_ativos.columns:
        print("ERRO: dados da CVM indisponiveis ou vazios. Abortando.")
        sys.exit(0)
    df_ativos["IS_MFO"] = df_ativos["NOME_SOCIAL"].apply(is_mfo)
    df_ativos["IS_MFO"] |= df_ativos["CATEG_REG"].str.lower().str.contains("patrimonio|patrimônio|wealth", na=False)
    n_mfo = int(df_ativos["IS_MFO"].sum())
    print(f"   MFOs: {n_mfo}")

    print("\n4. Calculando scores...")
    df_ativos["SCORE_MA"] = df_ativos.apply(lambda r: score_detail(r)[1], axis=1)
    df_ativos["SOCIOS"]   = df_ativos["CNPJ_CPF"].map(lambda c: socios_map.get(c, []))
    df_ativos["N_SOCIOS"] = df_ativos["SOCIOS"].map(len)
    df_ativos["RESPS"]    = df_ativos["CNPJ_CPF"].map(lambda c: resp_map.get(c, []))

    df_mfo = df_ativos[df_ativos["IS_MFO"]].sort_values("SCORE_MA", ascending=False).reset_index(drop=True)

    n_total = len(df_ativos)
    n_alvos = int((df_mfo["SCORE_MA"] >= 6).sum())
    df_ativos["ANO_REG"] = df_ativos["DT_REGISTRO"].str[:4]
    n_novos  = int((df_ativos["ANO_REG"] == str(date.today().year)).sum())
    evolucao = (df_ativos.groupby("ANO_REG").size()
                .reset_index(name="count")
                .pipe(lambda d: d[d["ANO_REG"].str.match(r"^\d{4}$")])
                .sort_values("ANO_REG"))
    geo = df_mfo["UF"].value_counts().head(10).to_dict()
    tipo_dist = {"MFO/Wealth Management": n_mfo, "Outros gestores": n_total - n_mfo}

    print(f"\n5. Gerando {len(df_mfo)} paginas individuais...")
    for _, r in df_mfo.iterrows():
        slug = cnpj_slug(r["CNPJ_CPF"])
        if slug:
            (FIRMA_DIR / f"{slug}.html").write_text(build_firma_page(r, now), encoding="utf-8")

    print("\n6. Gerando index...")
    html_index = build_index(df_mfo, evolucao, geo, tipo_dist,
                             n_total, n_mfo, n_alvos, n_novos, now)
    (DOCS_DIR / "index.html").write_text(html_index, encoding="utf-8")

    df_mfo.drop(columns=["SOCIOS", "RESPS"], errors="ignore").to_csv(
        DOCS_DIR / "mfos.csv", index=False, encoding="utf-8-sig")
    print(f"   CSV: {len(df_mfo)} firmas")
    print("=== Concluido! ===")


def fmt_pl(r):
    try:
        pl = float(str(r.get("PATRIM_LIQ", "")).replace(",", "."))
        dt = str(r.get("DT_PATRIM", ""))[:10]
        if pl >= 1e9:   s = f"R$ {pl/1e9:.2f}B"
        elif pl >= 1e6: s = f"R$ {pl/1e6:.1f}M"
        elif pl > 0:    s = f"R$ {pl/1e3:.0f}K"
        else:           return "Nao declarado"
        return f"{s} ({dt})" if dt else s
    except:
        return "Nao declarado"


def build_firma_page(r, now):
    nome  = str(r.get("NOME_SOCIAL", "")).strip().title()
    cnpj  = str(r.get("CNPJ_CPF", "")).strip()
    uf    = str(r.get("UF", "")).strip()
    mun   = str(r.get("MUNICIPIO", "")).strip().title()
    dt    = str(r.get("DT_REGISTRO", ""))[:10]
    categ = str(r.get("CATEG_REG", "")).strip()
    sub   = str(r.get("SUBCATEG", "")).strip()
    email = str(r.get("EMAIL", "")).strip()
    site  = str(r.get("SITE", "")).strip()
    tel   = str(r.get("TELEFONE", "")).strip()
    end   = str(r.get("LOGRADOURO", "")).strip()
    compl = str(r.get("COMPL", "")).strip()
    cep   = str(r.get("CEP", "")).strip()
    ctrl  = str(r.get("CONTROLE", "")).strip()
    sit   = str(r.get("SITUACAO", "")).strip()
    socios = r.get("SOCIOS", [])
    resps  = r.get("RESPS", [])
    score  = r.get("SCORE_MA", 0)
    score_items, _ = score_detail(r)

    try:
        ano  = int(str(r.get("DT_REGISTRO", ""))[:4])
        anos = f"{date.today().year - ano} anos no mercado"
    except:
        anos = ""

    # Tags
    sit_class = "tag-ok" if "FUNCIONAMENTO" in sit.upper() or "AUTORIZADO" in sit.upper() else "tag-warn"
    tags_html = f'<span class="tag tag-blue">{categ or "Adm. Carteira"}</span>'
    if sub:
        tags_html += f'<span class="tag tag-blue">{sub}</span>'
    tags_html += f'<span class="tag {sit_class}">{sit or "Ativo"}</span>'

    # Socios
    if socios:
        pills = "".join(f'<span class="socio-pill">{s.title()}</span>' for s in socios)
        socios_html = f'<div class="card-t">Socios <span class="mono micro subtle">{len(socios)} cadastrados</span></div><div style="margin-top:14px">{pills}</div>'
    else:
        socios_html = '<div class="card-t">Socios</div><div style="margin-top:10px;font-size:12px;color:var(--subtle)">Nao cadastrados na CVM</div>'

    # Responsaveis
    if resps:
        resp_rows = "".join(f'<div class="resp-row"><div class="resp-nome">{e["nome"].title()}</div><div class="resp-tipo">{e["tipo"]}</div></div>' for e in resps)
        resp_html = f'<div class="card-t">Responsaveis tecnicos CVM</div><div style="margin-top:14px">{resp_rows}</div>'
    else:
        resp_html = '<div class="card-t">Responsaveis tecnicos CVM</div><div style="margin-top:10px;font-size:12px;color:var(--subtle)">Nao cadastrados</div>'

    # Score bars
    score_rows = ""
    for lbl, pts, max_pts, desc in score_items:
        pct   = int(pts / max_pts * 100) if max_pts else 0
        color = "#2d6a4f" if pts >= max_pts * 0.8 else ("#b8965a" if pts > 0 else "#e0ddd8")
        score_rows += f'<div class="score-bar-wrap"><div class="score-bar-label"><span>{lbl} <span class="mono micro subtle">— {desc}</span></span><span class="pts">{pts}/{max_pts}</span></div><div class="score-bar"><div class="score-bar-fill" style="width:{pct}%;background:{color}"></div></div></div>'

    end_parts = [p for p in [end, compl, mun, uf, cep] if p]
    end_str   = ", ".join(end_parts) or "—"

    email_link = f'<a href="mailto:{email}" style="color:var(--gold)">{email}</a>' if email and email not in ("nan", "N/A", "") else "—"
    site_link  = f'<a href="{site}" target="_blank" style="color:var(--blue)">{site[:40]}</a>' if site and site not in ("nan", "N/A", "") else "—"
    email_btn  = f'<a href="mailto:{email}" class="btn" style="margin-right:8px">Enviar email</a>' if email and email not in ("nan", "N/A", "") else ""
    site_btn   = f'<a href="{site}" target="_blank" class="btn-outline">Visitar site</a>' if site and site not in ("nan", "N/A", "") else ""

    sidebar = SIDEBAR_TPL.replace("ACTIVE_DASH", "")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{nome} — MFO Brasil</title>
{CSS}
</head>
<body>
<div class="shell">
{sidebar}
<main class="main">
  <div class="firma-header">
    <a href="/mfo-dashboard/" class="firma-back">&#8592; Voltar ao dashboard</a>
    <div class="firma-nome">{nome}</div>
    <div class="firma-cnpj">CNPJ {cnpj} · {anos}</div>
    <div class="firma-tags">{tags_html}</div>
  </div>
  <div class="firma-body">
    <div class="kpi-strip">
      <div class="kpi"><div class="kpi-l">Score M&amp;A</div><div class="score-big">{score}</div><div class="score-label">de 10.0 possiveis</div></div>
      <div class="kpi"><div class="kpi-l">Socios cadastrados</div><div class="kpi-v">{len(socios) or "—"}</div><div class="kpi-d">na CVM</div></div>
      <div class="kpi"><div class="kpi-l">Responsaveis CVM</div><div class="kpi-v">{len(resps) or "—"}</div><div class="kpi-d">cadastrados</div></div>
      <div class="kpi"><div class="kpi-l">PL da gestora</div><div class="kpi-v" style="font-size:16px">{fmt_pl(r)}</div><div class="kpi-d">patrimonio proprio</div></div>
    </div>
    <div class="grid-2">
      <div class="card">
        <div class="card-t">Dados cadastrais</div>
        <div class="card-sub">Fonte: CVM Dados Abertos</div>
        <div class="info-row"><span class="info-label">CNPJ</span><span class="info-val mono small">{cnpj}</span></div>
        <div class="info-row"><span class="info-label">Categoria CVM</span><span class="info-val">{categ or "—"}</span></div>
        <div class="info-row"><span class="info-label">Subcategoria</span><span class="info-val">{sub or "—"}</span></div>
        <div class="info-row"><span class="info-label">Situacao</span><span class="info-val">{sit or "—"}</span></div>
        <div class="info-row"><span class="info-label">Data de registro</span><span class="info-val mono small">{dt or "—"}</span></div>
        <div class="info-row"><span class="info-label">Controle acionario</span><span class="info-val">{ctrl or "—"}</span></div>
        <div class="info-row"><span class="info-label">Endereco</span><span class="info-val" style="font-size:11px">{end_str}</span></div>
      </div>
      <div class="card">
        <div class="card-t">Contatos</div>
        <div class="card-sub">Dados publicos CVM</div>
        <div class="info-row"><span class="info-label">Email</span><span class="info-val">{email_link}</span></div>
        <div class="info-row"><span class="info-label">Site</span><span class="info-val">{site_link}</span></div>
        <div class="info-row"><span class="info-label">Telefone</span><span class="info-val mono small">{tel or "—"}</span></div>
        <div style="margin-top:16px;padding-top:16px;border-top:1px solid var(--line)">{email_btn}{site_btn}</div>
      </div>
    </div>
    <div class="card" style="margin-bottom:20px">{socios_html}</div>
    <div class="card" style="margin-bottom:20px">{resp_html}</div>
    <div class="card" style="margin-bottom:20px">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:20px">
        <div><div class="card-t">Score M&amp;A — Detalhamento</div><div class="card-sub">Modelo proprietario · Pontuacao 0–10</div></div>
        <div style="text-align:right"><div class="score-big" style="font-size:36px">{score}</div><div class="score-label">/ 10.0</div></div>
      </div>
      {score_rows}
    </div>
    <div class="fnote">Fonte: CVM Dados Abertos (dados.cvm.gov.br) · Atualizado: {now}<br>Score M&A e modelo proprietario e nao constitui recomendacao de investimento.</div>
  </div>
</main>
</div>
</body></html>"""


def build_index(df_mfo, evolucao, geo, tipo_dist, n_total, n_mfo, n_alvos, n_novos, now):
    rows = ""
    for i, (_, r) in enumerate(df_mfo.head(50).iterrows(), 1):
        score = r["SCORE_MA"]
        sc    = "score-high" if score >= 8 else ("score-mid" if score >= 6 else "score-low")
        ano   = str(r.get("DT_REGISTRO", ""))[:4] or "—"
        uf    = str(r.get("UF", "")).strip() or "—"
        cnpj  = str(r.get("CNPJ_CPF", "")).strip()
        nome  = str(r.get("NOME_SOCIAL", "")).strip().title() or "—"
        email = str(r.get("EMAIL", "")).strip()
        site  = str(r.get("SITE", "")).strip()
        n_soc = int(r.get("N_SOCIOS", 0) or 0)
        slug  = cnpj_slug(cnpj)

        em_html   = f'<a href="mailto:{email}" style="color:var(--gold);font-size:9px">{email[:24]}</a>' if email and email not in ("nan","N/A","") else "—"
        site_html = f'<a href="{site}" target="_blank" style="color:var(--blue);font-size:9px">site</a>' if site and site not in ("nan","N/A","") else ""

        rows += f'<tr onclick="window.location=\'/mfo-dashboard/firma/{slug}.html\'"><td><span class="mono subtle">{i:02d}</span></td><td><div class="firm-name">{nome}</div><div class="mono micro subtle">{cnpj}</div></td><td><span class="mono small">{uf}</span></td><td><span class="mono micro">{ano}</span></td><td><span class="mono small">{n_soc if n_soc else "—"}</span></td><td><span class="score-dot {sc}">{score}</span></td><td>{em_html} {site_html}</td></tr>'

    anos_evo   = json.dumps(evolucao["ANO_REG"].tolist())
    counts_evo = json.dumps(evolucao["count"].tolist())
    geo_labels = json.dumps(list(geo.keys()))
    geo_vals   = json.dumps(list(geo.values()))
    tipo_lbl   = json.dumps(list(tipo_dist.keys()))
    tipo_val   = json.dumps(list(tipo_dist.values()))
    sidebar    = SIDEBAR_TPL.replace("ACTIVE_DASH", "active")

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MFO Brasil — Inteligencia de Mercado</title>
{CSS}
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
</head>
<body>
<div class="shell">
{sidebar}
<main class="main">
  <div class="topbar">
    <div><div class="topbar-t">MFOs &amp; Gestores de Patrimonio — Brasil</div><div class="topbar-m">Cadastro CVM · Ref. {now}</div></div>
    <span class="updated">Atualizado {now}</span>
  </div>
  <div class="content">
    <div class="kpi-strip">
      <div class="kpi"><div class="kpi-l">Firmas ativas (CVM)</div><div class="kpi-v">{n_total:,}</div><div class="kpi-d">Adm. carteira ativas</div></div>
      <div class="kpi"><div class="kpi-l">MFOs identificados</div><div class="kpi-v">{n_mfo:,}</div><div class="kpi-d">Heuristica multicritério</div></div>
      <div class="kpi"><div class="kpi-l">Alvos M&amp;A (score 6+)</div><div class="kpi-v">{n_alvos:,}</div><div class="kpi-d" style="color:var(--gold)">Alta prioridade</div></div>
      <div class="kpi"><div class="kpi-l">Novos em {date.today().year}</div><div class="kpi-v">{n_novos:,}</div><div class="kpi-d">Registros no ano</div></div>
    </div>
    <div class="grid-3">
      <div class="card"><div class="card-t">Crescimento da industria</div><div class="card-sub">Registros ativos por ano · CVM</div><div style="height:180px"><canvas id="gc"></canvas></div></div>
      <div class="card"><div class="card-t">Perfil do universo</div><div class="card-sub">Por classificacao</div><div style="height:110px"><canvas id="gt"></canvas></div><ul class="blist"><li class="bitem"><span class="bcolor" style="background:#b8965a"></span><span class="bname">MFO/Wealth Management</span><span class="bcnt">{n_mfo}</span></li><li class="bitem"><span class="bcolor" style="background:#1a3a6b"></span><span class="bname">Outros gestores</span><span class="bcnt">{n_total-n_mfo}</span></li></ul></div>
      <div class="card"><div class="card-t">Concentracao por UF</div><div class="card-sub">Top estados · MFOs</div><div style="height:180px"><canvas id="gs"></canvas></div></div>
    </div>
    <div class="sec-hd"><h2>Ranking MFOs — Score M&amp;A</h2><span class="sec-cnt">Top 50 de {n_mfo} · clique para ver ficha completa</span><div class="ml-auto"><a href="mfos.csv" class="btn">CSV completo ({n_mfo} firmas)</a></div></div>
    <div class="table-wrap"><table><thead><tr><th>#</th><th>Firma</th><th>UF</th><th>Registro</th><th>Socios</th><th>Score M&amp;A</th><th>Contato</th></tr></thead><tbody>{rows}</tbody></table></div>
    <div class="fnote">Fonte: CVM Dados Abertos · Atualizacao automatica via GitHub Actions · {now}<br>Clique em qualquer firma para ver a ficha completa com socios, responsaveis e score detalhado.</div>
  </div>
</main>
</div>
<script>
const M="'DM Mono',monospace",G="#b8965a",L="#e0ddd8",I="#0d0d0d";
const cfg=(t,d,o)=>{{return{{type:t,data:d,options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},...o}}}}}};
new Chart(document.getElementById('gc'),cfg('line',{{labels:{anos_evo},datasets:[{{data:{counts_evo},borderColor:I,backgroundColor:'transparent',borderWidth:2,pointRadius:0,tension:.4}}]}},{{scales:{{x:{{grid:{{color:L}},ticks:{{font:{{family:M,size:8}},color:'#aaa',maxTicksLimit:8}}}},y:{{grid:{{color:L}},ticks:{{font:{{family:M,size:8}},color:'#aaa'}}}}}}}}));
new Chart(document.getElementById('gt'),cfg('doughnut',{{labels:{tipo_lbl},datasets:[{{data:{tipo_val},backgroundColor:['#b8965a','#1a3a6b'],borderWidth:0}}]}},{{cutout:'65%'}}));
new Chart(document.getElementById('gs'),cfg('bar',{{labels:{geo_labels},datasets:[{{data:{geo_vals},backgroundColor:G+'cc',borderWidth:0,borderRadius:3}}]}},{{scales:{{x:{{grid:{{display:false}},ticks:{{font:{{family:M,size:9}},color:'#aaa'}}}},y:{{grid:{{color:L}},ticks:{{font:{{family:M,size:9}},color:'#aaa'}}}}}}}}));
</script>
</body></html>"""


if __name__ == "__main__":
    main()
