# Workflow Aggiornato per Profili Elevazione

## Funzionalità Implementate

### 1. Creazione Sequenziale dei Profili
Quando si clicca "Prepara Profili per Layout", il plugin automaticamente:

Per ogni sezione nel layer "Profili DEM":
1. **Apre il pannello Profilo Elevazione** di QGIS
2. **Rinomina il pannello** con il nome della sezione (es. "Profilo Elevazione A-B")
3. **Configura i layer**:
   - Disattiva tutti i layer
   - Attiva solo il DEM utilizzato per creare la sezione
4. **Cattura la curva**:
   - Imposta la geometria della sezione
   - Clicca automaticamente il pulsante "Cattura curva"
   - Seleziona la feature corrispondente nel layer "Profili DEM"
5. **Conferma** con una finestra di dialogo prima di passare al profilo successivo

### 2. Automazione Completa
Il plugin ora gestisce automaticamente:
- **Selezione del DEM corretto**: Solo il DEM usato per la sezione viene attivato
- **Cattura della sezione**: La sezione viene selezionata e catturata automaticamente
- **Rinomina del pannello**: Ogni pannello ha il nome della sezione corrispondente

### 3. Integrazione con il Layout
Quando si genera il layout:
- Il plugin cerca i pannelli "Profilo Elevazione" aperti
- Priorità data ai pannelli con nomi specifici delle sezioni
- Copia i profili dal pannello al layout usando `copyFromProfileWidget`
- Se il metodo di copia non è disponibile, configura manualmente il profilo

## Workflow Consigliato

1. **Crea le sezioni** con lo strumento "Crea Profilo DEM"
2. **Prepara i profili** cliccando "Prepara Profili per Layout"
3. **Per ogni profilo**, quando appare la finestra:
   - Verifica che il profilo sia visibile
   - Se necessario, seleziona manualmente la sezione nel pannello
   - Clicca OK per continuare
4. **Genera il layout** quando tutti i profili sono pronti

## Troubleshooting

### Profili non visibili nel layout
- Assicurati che i pannelli "Profilo Elevazione" siano aperti
- Verifica che ogni pannello mostri il profilo corretto
- Controlla i log di QGIS per eventuali errori

### Selezione automatica non funziona
- In alcune versioni di QGIS potrebbe essere necessario selezionare manualmente la sezione
- Usa lo strumento di cattura curva nel pannello profilo elevazione

### Performance
- Con molti profili, il processo potrebbe richiedere tempo
- Non chiudere i pannelli profilo elevazione prima di generare il layout