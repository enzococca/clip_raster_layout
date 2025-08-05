# Guida d'uso - Clip Raster Layout Plugin

## Workflow corretto per i profili elevazione

### 1. Preparazione
- Assicurati di avere un layer DEM/DTM caricato nel progetto
- Il DEM deve essere configurato nelle proprietà del progetto come sorgente elevazione

### 2. Creazione delle sezioni
1. Usa lo strumento "Crea Profilo DEM" dal menu
2. Seleziona il layer DEM quando richiesto
3. Clicca due punti sulla mappa per creare una sezione (A-B, C-D, ecc.)
4. Il plugin:
   - Crea la linea di sezione nel layer "Profili DEM"
   - Mostra il grafico matplotlib come dock widget sulla sinistra
   - Apre automaticamente il pannello "Profilo Elevazione" di QGIS

### 3. Configurazione del profilo elevazione QGIS
1. Nel pannello "Profilo Elevazione" di QGIS che si è aperto:
   - Seleziona la linea di sezione appena creata
   - Verifica che il DEM sia visibile nel profilo
   - Personalizza colori e stile se necessario
2. Ripeti per ogni sezione (massimo 6)

### 4. Generazione del layout
1. Vai su "Genera Layout Professionale"
2. Seleziona il raster principale da visualizzare
3. Assicurati che "Usa template_layout.qpt" sia selezionato
4. Clicca "Genera Layout"

### 5. Nel layout
- Pagina 1: Mappa con le sezioni tracciate
- Pagina 2: I profili elevazione (solo quelli creati, non sempre 6)

## Note importanti
- I profili elevazione devono essere creati nel pannello nativo di QGIS
- Il template usa il metodo "copia da profilo esistente" per popolare i profili
- Se non vedi i profili nel layout, verifica che il pannello "Profilo Elevazione" sia aperto e contenga il profilo corretto

## Troubleshooting
- **Profili vuoti nel layout**: Assicurati che il pannello "Profilo Elevazione" di QGIS sia aperto con il profilo visualizzato
- **Non si apre il pannello profili**: Vai su Vista → Pannelli → Profilo Elevazione
- **DEM non visibile nel profilo**: Configura il DEM nelle proprietà del progetto come sorgente elevazione