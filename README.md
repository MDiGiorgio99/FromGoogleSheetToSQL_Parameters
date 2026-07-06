# Google Sheets to SQL Converter - Batch Mode

Estrae automaticamente dati da molteplici Google Sheets e li inserisce in SQL Server **senza interazione manuale**.

## 🚀 Nuove Caratteristiche (v2.0)

- ✅ **Modalità Batch**: Processa automaticamente múltiples fogli da un file di configurazione
- ✅ **Nessun Menù Interattivo**: Esecuzione completamente automatica
- ✅ **3 Modalità di Elaborazione**: CREATE (ricrea tabella), TRUNCATE (svuota), INSERT (aggiungi dati)
- ✅ **Logging Dettagliato**: Visualizza il progresso dell'esecuzione in tempo reale

## Setup Iniziale

### 0. Clona il Repository

```bash
git clone https://github.com/MDiGiorgio99/FromGoogleSheetToSQL_Parameters.git
cd FromGoogleSheetToSQL_Parameters
```

### 1. Installa le dipendenze

```bash
pip install gspread google-auth-oauthlib google-auth-httplib2 pyodbc
```

- **gspread**: Accesso a Google Sheets
- **google-auth-***: Autenticazione OAuth2
- **pyodbc**: Connessione a SQL Server

### 2. Ottieni le credenziali da Google Cloud Console

#### Passo A: Abilita l'API Google Sheets
1. Vai su [Google Cloud Console](https://console.cloud.google.com/)
2. Seleziona il progetto oppure creane uno nuovo
3. In alto nella barra di ricerca, cerca **"Google Sheets API"**
4. Clicca sul risultato e premi il pulsante **"Abilita"**
5. Aspetta che l'API sia abilitata (potrebbe richiedere alcuni secondi)

#### Passo B: Crea una Service Account
1. Nel menu a sinistra: **APIs & Services** → **Credentials**
2. Clicca **+ Create Credentials** → **Service Account**
3. Riempi i dettagli e crea
4. Vai su **Keys** → **Add Key** → **Create new key** → **JSON**
5. Scarica il file JSON e rinominalo `credentials.json`
6. Metti il file nella stessa cartella dello script

#### Passo C: Condividi il Google Sheet
1. Apri il tuo Google Sheet
2. Clicca **Condividi** (pulsante in alto a destra)
3. Copia l'email della Service Account dal file `credentials.json` (campo `client_email`)
4. Incolla l'email nel modulo di condivisione e dai permessi di visualizzazione

### 3. Ricava l'ID del Google Sheet

Dalla URL del Google Sheet, copia la parte tra `/d/` e `/edit`:

```
https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID_HERE/edit#gid=0
                                      ↑ copia questo ↑
```

## 📋 File di Configurazione

### batch.json
File che specifica quali fogli estrarre e come processarli:

```json
[
  {
    "spreadsheet": "YOUR_PARENT_SHEET_ID",
    "sheet": "SHEET_NAME",
    "dropCreate": "create"
  },
  {
    "spreadsheet": "YOUR_PARENT_SHEET_ID",
    "sheet": "SHEET_NAME",
    "dropCreate": "truncate"
  },
  {
    "spreadsheet": "YOUR_PARENT_SHEET_ID",
    "sheet": "SHEET_NAME",
    "dropCreate": "insert"
  }
]
```

**Campi:**
- `spreadsheet`: ID del Google Sheet (da URL: `/d/{ID}/edit`)
- `sheet`: Nome esatto del foglio da estrarre
- `dropCreate`: Modalità di elaborazione:
  - **`"create"`**: DROP TABLE IF EXISTS + CREATE TABLE + INSERT (ricrea la tabella)
  - **`"truncate"`**: TRUNCATE TABLE + INSERT (svuota ma mantiene la struttura)
  - **`"insert"`**: Solo INSERT (aggiunge ai dati esistenti)

### config.json
Mantiene le configurazioni di connessione:

```json
{
  "google_sheets": {
    "credentials_file": "credentials.json"
  },
  "sql_server": {
    "default_server": "localhost",
    "default_database": "YOUR_DB",
    "use_windows_auth": true,
    "username": null,
    "password": null
  },
  "sql_generation": {
    "string_type": "VARCHAR(MAX)",
    "int_type": "INT",
    "float_type": "FLOAT",
    "bool_type": "BIT",
    "datetime_type": "DATETIME"
  },
  "logging": {
    "log_level": "errors"
  }
}
```

**Campi:**
- `credentials_file`: percorso al file JSON con le credenziali
- `default_server`: nome del server SQL Server
- `default_database`: database di destinazione
- `use_windows_auth`: `true` per autenticazione Windows, `false` per SQL Server
- `username`: username SQL Server (usato solo se `use_windows_auth` è `false`)
- `password`: password SQL Server (usato solo se `use_windows_auth` è `false`)
- `log_level`: Livello di dettaglio del logging:
  - **`"errors"`** (predefinito): Registra solo gli errori 
  - **`"full"`**: Registra tutto (INSERT statements, operazioni completate, errori) 

#### Configurazione del Logging

La configurazione del logging ti permette di controllare il livello di dettaglio dei file di log generati:

**Modalità "errors" (predefinita)**:
```json
"logging": {
  "log_level": "errors"
}
```
✅ Registra solo gli errori:
- Errori durante la connessione
- Errori SQL
- Fallimenti dell'esecuzione
- File di log minimale


**Modalità "full"**:
```json
"logging": {
  "log_level": "full"
}
```
✅ Registra tutti i dettagli:
- Inizio e fine dell'elaborazione
- Ogni INSERT statement eseguito
- Operazioni completate
- Errori SQL
- Riepilogo completo


#### Modalità Autenticazione

**Autenticazione Windows** (predefinita):
```json
"sql_server": {
  "default_server": "localhost",
  "default_database": "TestExtraction",
  "use_windows_auth": true,
  "username": null,
  "password": null
}
```
✅ Usa le credenziali dell'utente Windows attualmente loggato

**Autenticazione SQL Server**:
```json
"sql_server": {
  "default_server": "localhost",
  "default_database": "TestExtraction",
  "use_windows_auth": false,
  "username": "sa",
  "password": "TuaPassword123"
}
```
✅ Usa username e password per connettersi a SQL Server

## ▶️ Come Usare

### Esecuzione con Python:
```bash
python GoogleSheet_to_SQL.py batch.json
```

### Esecuzione con l'Eseguibile:

#### Dalla riga di comando (PowerShell/CMD):
```bash
.\GoogleSheet_to_SQL.exe batch.json
```

⚠️ **Il file di configurazione è obbligatorio** - deve essere specificato come parametro della riga di comando.

## �️ Schedulazione Automatica (Windows Task Scheduler)

È possibile schedulare l'esecuzione automatica del programma su Windows per sincronizzare i dati periodicamente.

L'eseguibile è già disponibile nella cartella del progetto: `GoogleSheet_to_SQL.exe`

### 1. Apri Task Scheduler

- Premi `Win + R`
- Digita: `taskschd.msc`
- Premi `Invio`

### 2. Crea una Nuova Attività

1. **Nel pannello sinistro**: Clicca su "Task Scheduler Library"
2. **Nel pannello destro**: Clicca su "Create Basic Task..."

### 3. Configura l'Attività - Scheda "General"

- **Nome**: `GoogleSheet_to_SQL_Batch`
- **Descrizione**: `Sincronizzazione automatica Google Sheets to SQL Server`
- Spunta: ✓ "Run whether user is logged in or not"
- Spunta: ✓ "Run with highest privileges"

### 4. Configura i Trigger - Scheda "Triggers"

Clicca "New" e scegli la frequenza:

- **Giornaliera**: Alle 02:00 AM
- **Settimanale**: Lunedì alle 02:00 AM
- **Mensile**: Primo giorno del mese alle 02:00 AM

Personalizza secondo le tue necessità e clicca "OK"

### 5. Configura l'Azione - Scheda "Actions"

Clicca "New" e imposta:

```
Program/script:
C:\Latitudo\FromGoogleSheetToSQL_Parameters\GoogleSheet_to_SQL.exe

Add arguments:
batch.json

Start in:
C:\Latitudo\FromGoogleSheetToSQL_Parameters
```

⚠️ **Importante**: Il campo "Start in" DEVE contenere il percorso della cartella di lavoro, altrimenti il programma non troverà `config.json` e `batch.json`

### 6. Salva e Testa

- Clicca "Finish"
- Fai clic destro sull'attività creata
- Seleziona "Run"
- Verifica che il file log sia creato in: `log/batch_execution_*.log`

### 7. Visualizza i Log

I log di ogni esecuzione automatica saranno salvati in:
```
C:\Latitudo\FromGoogleSheetToSQL_Parameters\log\
```

Ogni file contiene:
- ✓ Ogni statement INSERT eseguito
- ❌ Errori SQL (se presenti)
- 📊 Riepilogo dell'elaborazione

Esempio di log:
```
2026-07-03 02:00:45 - INFO - ======================================================================
2026-07-03 02:00:45 - INFO - INIZIO ELABORAZIONE BATCH: 2 foglio/i
2026-07-03 02:00:45 - INFO - [1/2] Elaborazione: Sheet 'Commesse' - Modalità: TRUNCATE
2026-07-03 02:00:46 - INFO - INSERT INTO [Spreadsheet_Commesse] VALUES (...)
2026-07-03 02:00:46 - INFO - ✓ Successo
2026-07-03 02:00:46 - INFO - RIEPILOGO ELABORAZIONE:
2026-07-03 02:00:46 - INFO - Successo: 2/2
```

## 📊 Esempio di Output

### Output Console (visualizzazione su schermo)

```
======================================================================
  Google Sheets to SQL Converter - Batch Mode
======================================================================

======================================================================
📥 Inizio elaborazione batch: 3 foglio/i
======================================================================

[1/3] Elaborazione: Sheet 'Dati_Vendite' da '1q2Sjp0AR9i4ieNeqy2IUHfRXwk19OCcVHlTQYLS9lcY'
      ✓ Estratti 150 record con 8 colonne
      ✓ SQL generato (CREATE)
      ✓ Dati inseriti su SQL Server

[2/3] Elaborazione: Sheet 'Clienti' da '1q2Sjp0AR9i4ieNeqy2IUHfRXwk19OCcVHlTQYLS9lcY'
      ✓ Estratti 75 record con 5 colonne
      ✓ SQL generato (TRUNCATE)
      ✓ Dati inseriti su SQL Server

[3/3] Elaborazione: Sheet 'Storico' da '1q2Sjp0AR9i4ieNeqy2IUHfRXwk19OCcVHlTQYLS9lcY'
      ✓ Estratti 42 record con 6 colonne
      ✓ SQL generato (INSERT)
      ✓ Dati inseriti su SQL Server

======================================================================
📊 Elaborazione completata:
   ✓ Successo: 3/3
   ❌ Falliti:  0/3
======================================================================
```

### Output Log File

#### 📝 Modalità "errors" (predefinita)

Il file di log conterrà **solo gli errori** (se presenti). Se l'elaborazione è andata bene, il file sarà vuoto oppure vuoto:

```
[LOG VUOTO - Nessun errore]
```

Se si verifica un errore:

```
2026-07-06 14:30:52 - ERROR - ❌ Errore di connessione a SQL Server: ('42000', '[42000] [Microsoft][ODBC Driver 17 for SQL Server][SQL Server]Login failed for user \'sa\'. (18456) (SQLState: 42000; NativeError: 18456)')
2026-07-06 14:30:52 - ERROR - ❌ Errore nel comando: INSERT INTO [Spreadsheet_Dati] VALUES ...
2026-07-06 14:30:52 - ERROR -    Dettagli: Syntax error near 'VALUES'
```


#### 📝 Modalità "full"

Il file di log conterrà **tutte le operazioni e gli errori**:

```
2026-07-06 14:30:45 - INFO - ======================================================================
2026-07-06 14:30:45 - INFO - INIZIO ELABORAZIONE BATCH: 3 foglio/i
2026-07-06 14:30:45 - INFO - ======================================================================
2026-07-06 14:30:46 - INFO - [1/3] Elaborazione: Sheet 'Dati_Vendite' - Modalità: CREATE
2026-07-06 14:30:46 - INFO - Estratti 150 record con 8 colonne
2026-07-06 14:30:47 - INFO - INSERT INTO [Spreadsheet_Dati_Vendite] VALUES ('2026-01-05', 'Acme Corp', 5000.00, 'Completato', NULL, 1, 'IT', '2026-01-05 10:30:00')
2026-07-06 14:30:47 - INFO - ✓ Successo
2026-07-06 14:30:47 - INFO - INSERT INTO [Spreadsheet_Dati_Vendite] VALUES ('2026-01-06', 'Tech Solutions', 3500.50, 'Completato', NULL, 1, 'IT', '2026-01-06 11:15:00')
2026-07-06 14:30:47 - INFO - ✓ Successo
2026-07-06 14:30:47 - INFO - INSERT INTO [Spreadsheet_Dati_Vendite] VALUES ('2026-01-07', 'Global Industries', 7200.00, 'In sospeso', NULL, 2, 'EU', '2026-01-07 14:45:00')
2026-07-06 14:30:47 - INFO - ✓ Successo
... [150 record totali] ...
2026-07-06 14:31:02 - INFO - [2/3] Elaborazione: Sheet 'Clienti' - Modalità: TRUNCATE
2026-07-06 14:31:02 - INFO - Estratti 75 record con 5 colonne
2026-07-06 14:31:03 - INFO - INSERT INTO [Spreadsheet_Clienti] VALUES ('Acme Corp', 'acme@company.com', '+39 06 1234567', 'Roma', 'Italia')
2026-07-06 14:31:03 - INFO - ✓ Successo
... [75 record totali] ...
2026-07-06 14:31:45 - INFO - [3/3] Elaborazione: Sheet 'Storico' - Modalità: INSERT
2026-07-06 14:31:45 - INFO - Estratti 42 record con 6 colonne
... [42 record totali] ...
2026-07-06 14:32:10 - INFO - ======================================================================
2026-07-06 14:32:10 - INFO - Elaborazione completata con successo
2026-07-06 14:32:10 - INFO - ======================================================================
2026-07-06 14:32:10 - INFO - ======================================================================
2026-07-06 14:32:10 - INFO - RIEPILOGO ELABORAZIONE:
2026-07-06 14:32:10 - INFO - Successo: 3/3
2026-07-06 14:32:10 - INFO - Falliti: 0/3
2026-07-06 14:32:10 - INFO - ======================================================================
```

## 🔍 Risoluzione Problemi

| Errore | Soluzione |
|--------|-----------|
| `File 'batch.json' non trovato` | Crea il file batch.json nella stessa cartella con la struttura corretta |
| `Foglio non trovato` | Verifica il nome esatto del foglio (è case-sensitive) |
| `Errore di autenticazione Google` | Verifica che il service account abbia accesso al foglio |
| `Errore di connessione SQL Server` | Controlla server, database e driver ODBC in config.json |
| `Modalità non valida` | Usa solo "create", "truncate", o "insert" nel campo dropCreate |

## 📝 Note Importanti

- **Nomi colonne**: Spazi e caratteri speciali → underscore
- **Celle vuote**: Diventano `NULL` nel database
- **Booleani**: `true/false`, `yes/no`, `1/0` → `BIT` (0/1)
- **Date**: Rilevate automaticamente → `DATETIME`

---
**Versione**: 2.0 - Batch Mode  

