# Seguiment de cotxes (i peces) de segona mà

Versió simplificada: **tot el codi cap en un sol fitxer** (`seguiment.py`),
perquè pujar-ho a GitHub sigui senzill i no calgui arrossegar carpetes.

Executa aquest script manualment (1-2 cops al dia) per detectar anuncis
**nous** a les cerques que defineixis a `config.json` (Wallapop, Milanuncios,
Coches.net, AutoScout24, Autohero), i genera un informe HTML amb el resum:
títol, preu, detalls i enllaç de cada anunci.

Només 5 fitxers:
```
seguiment.py                        el codi (tot en un)
config.json                          les teves cerques (edita aquest)
requirements.txt                     dependències de Python
README.md                            aquest fitxer
.github/workflows/seguiment.yml      perquè GitHub ho pugui executar sol
```

---

## Configuració a GitHub (sense terminal, sense permisos d'admin)

### 1. Crea el repositori
1. [github.com/new](https://github.com/new) → nom (p. ex. `seguiment-cotxes`)
   → **Public** → **Create repository** (no marquis cap altra opció).

### 2. Puja els fitxers
Com que ara només hi ha 4 fitxers a l'arrel i 1 dins d'una subcarpeta, es pot
fer tot des de la web sense necessitat d'arrossegar cap carpeta:

1. **Add file → Upload files**, i arrossega-hi (o selecciona amb "choose your
   files") aquests 4 fitxers alhora: `seguiment.py`, `config.json`,
   `requirements.txt`, `README.md`. **Commit changes**.
2. Ara el cinquè fitxer, el que va dins d'una subcarpeta: **Add file →
   Create new file**. Al camp del nom, escriu tal qual:
   `.github/workflows/seguiment.yml` — en escriure la barra `/`, GitHub crea
   les carpetes soles. Enganxa el contingut del fitxer `seguiment.yml` que
   tens al zip, i **Commit changes**.

Comprova que a l'arrel del repositori hi ha `seguiment.py`, `config.json`,
`requirements.txt`, `README.md`, i una carpeta `.github`.

### 3. Permisos perquè el robot pugui desar l'informe
**Settings → Actions → General → Workflow permissions** → selecciona
**"Read and write permissions"** → **Save**.

### 4. Activa GitHub Pages
**Settings → Pages → Build and deployment → Source**: *"Deploy from a
branch"*, branca `main`, carpeta `/docs` → **Save**.
(La carpeta `docs` encara no existeix — es crearà sola la primera vegada
que executis el workflow. És normal que ara mateix no aparegui a la llista;
torna a aquesta pantalla després del primer "Run workflow" si cal
tornar-la a seleccionar.)
Apuntar-te la URL que et doni (tipus `https://el-teu-usuari.github.io/seguiment-cotxes/`).

### 5. Configura les teves cerques
Obre `config.json` al repositori, clica la icona del llapis (✏️) per
editar-lo, posa `"activa": true` i la `url` real en almenys una cerca
(vegeu més avall com obtenir la URL de cada web), i **Commit changes**.

### 6. Executa-ho
**Actions** (pestanya de dalt) → *"Seguiment de cotxes"* (a l'esquerra) →
**Run workflow** → **Run workflow**. Espera un minut i refresca: hauria de
sortir una ✅ verda. Obre la URL de Pages per veure l'informe.

Repeteix el pas 6 cada vegada que vulguis actualitzar-lo (1-2 cops al dia).

---

## Com obtenir la `url` de cada cerca

### Wallapop
Wallapop carrega els resultats per JavaScript, així que cal la URL de la
seva API, no la de la pàgina:
1. Fes la cerca a wallapop.com amb els filtres que vulguis (cotxe o peça).
2. **F12** → pestanya **Network/Xarxa** → filtra per `wallapop` → recarrega.
3. Busca una petició cap a `api.wallapop.com/api/v3/.../search...`.
4. Botó dret → **Copy → Copy link address** → enganxa-ho al camp `url`
   (amb `"site": "wallapop"`).

### Coches.net / AutoScout24 / Autohero / Milanuncios
1. Fes la cerca amb els filtres que vulguis directament a la web i copia la
   URL de resultats tal qual — aquesta és la `url` (amb `"site": "generic"`).
2. Si els `selectors` d'exemple de `config.json` no funcionen (una cerca
   torna 0 resultats o dona error), toca ajustar-los: **F12** →
   **Inspeccionar** sobre la targeta d'un anunci, i mira quina classe CSS
   envolta tot l'anunci (`contenidor`), quina el títol, quina el preu, i
   quin és l'enllaç.

## Si una cerca dona error
- **"No s'ha pogut extreure cap anunci..."**: la web probablement bloqueja
  peticions automàtiques (Milanuncios té fama de ser la més estricta), o els
  selectors no coincideixen amb el disseny actual — revisa'ls com s'explica
  a dalt.
- **Error HTTP 403/429**: bloqueig temporal; espera abans de tornar a
  executar.
- **Wallapop torna 0 anuncis sense error**: mira el missatge "(avís: cap
  anunci reconegut...)" al log de l'execució (pestanya Actions → clica
  l'execució → "Executa la cerca") — indica les claus rebudes, útils per
  ajustar la funció `cerca_wallapop` si Wallapop ha canviat l'API.

## Executar-ho en local (alternativa, si tens Python i permisos)
```bash
pip install -r requirements.txt
python seguiment.py
```
S'obrirà `ultim_informe.html` automàticament al navegador.
