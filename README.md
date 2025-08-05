# Clip Raster Layout Plugin per QGIS

Plugin QGIS che fornisce tre funzionalità principali per l'analisi topografica:

## Funzionalità

### 1. Clip Raster in Batch
- Clipping multiplo di raster usando un poligono
- Selezione dei raster da elaborare
- Barra di progresso per monitorare l'operazione
- Aggiunta automatica dei raster clippati alla mappa

### 2. Creazione Profili DEM
- Click su due punti per creare profili topografici
- Linee tratteggiate nere con etichette (A-B, C-D, ecc.)
- Calcolo lunghezza 2D e 3D
- Elevazioni ai punti estremi
- Grafico del profilo con min/max annotati
- Possibilità di scegliere dove salvare le immagini dei profili

### 3. Generazione Layout Professionale
- Layout automatico con:
  - Mappa principale con raster e profili
  - Grafico del profilo elevazione
  - Freccia del Nord
  - Barra di scala dinamica
  - Legenda
  - Mappa di inquadramento
  - Griglia coordinate
  - Tabella metadati
- Supporto per vari formati carta (A4-A1)
- Scale topografiche standard (1:1 - 1:500000)
- Esportazione PDF

## Installazione

1. Copia la cartella `clip_raster_layout` nella directory dei plugin QGIS:
   - Windows: `C:\Users\[username]\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins\`
   - macOS: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
   - Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`

2. Riavvia QGIS o ricarica i plugin

3. Attiva il plugin dal menu Plugin → Gestisci e installa plugin

## Requisiti

- QGIS 3.x
- Python 3.x
- Librerie Python: numpy, matplotlib

## Uso

1. **Clip Raster**: Menu Raster → Clip Raster Layout → Clip Raster in Batch
2. **Profili DEM**: Menu Raster → Clip Raster Layout → Crea Profilo DEM
3. **Layout**: Menu Raster → Clip Raster Layout → Genera Layout Professionale

## Autore

Enzo - enzo@example.com

## Licenza

GPL v3