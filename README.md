# Google Sheets to SQL Converter

Converti automaticamente Google Sheets in SQL

## Setup Iniziale

### 1. Installa le dipendenze

```bash
pip install gspread google-auth-oauthlib google-auth-httplib2 pyperclip
```

- **gspread**: Accesso a Google Sheets
- **google-auth-***: Autenticazione OAuth2
- **pyperclip**: Copia negli appunti (opzionale)

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

## Configurazione (config.json)

Lo script legge tutte le configurazioni dal file **`config.json`** nella stessa cartella.

### Sezioni configurabili:

#### `google_sheets`
```json
{
  "credentials_file": "credentials.json",
  "default_sheet_id": "YOUR_SHEET_ID"
}
```
- **`credentials_file`**: percorso al file JSON con le credenziali (scaricato da Google Cloud)
- **`default_sheet_id`**: ID del Google Sheet (opzionale, chiede all'avvio se non presente)

#### `sql_server`
```json
{
  "default_server": "localhost",
  "default_database": "YOUR_DATABASE",
  "use_windows_auth": true
}
```
- **`default_server`**: nome del server SQL Server (es: `localhost`, `.\\SQLEXPRESS`, `192.168.1.100`)
- **`default_database`**: database di destinazione
- **`use_windows_auth`**: `true` per autenticazione Windows, `false` per username/password

#### `sql_generation`
```json
{
  "string_type": "VARCHAR(MAX)",
  "int_type": "INT",
  "float_type": "FLOAT",
  "bool_type": "BIT",
  "datetime_type": "DATETIME"
}
```
- Personalizza i tipi SQL usati per le colonne

## Come usare lo script

### Opzione 1: Esegui lo script Python

```bash
python .\GoogleSheet_to_SQL.py
```

### Opzione 2: Esegui l'eseguibile 


```bash
GoogleSheet_to_SQL.exe
```

**Vantaggi dell'eseguibile:**
- ✅ Non devi installare Python
- ✅ Modifica il `config.json` quando vuoi - si aggiorna automaticamente!
- ✅ Più veloce da avviare

### Flusso interattivo:
1. **Incolla l'ID del Google Sheet** quando richiesto
2. **Scegli il foglio** dal menu (1, 2, 3, ...)
3. **Visualizza anteprima** dei dati estratti
4. **Salva il file SQL** (opzionale) oppure esegui su db
5. **Copia negli appunti** (opzionale)

## Output

Lo script genera:
- ✅ **CREATE TABLE** con tipo di colonne inferito automaticamente
- ✅ **INSERT statements** per tutti i record
- ✅ File `.sql` salvato localmente (opzionale)

### Esempio output:

```sql
-- Created: 2026-04-21 10:30:45;

DROP TABLE IF EXISTS [Clienti];

CREATE TABLE [Clienti] (
    [Nome] VARCHAR(MAX),
    [Email] VARCHAR(MAX),
    [Eta] INT,
    [Data_Iscrizione] DATETIME
);

-- Insert 150 records;
INSERT INTO [Clienti] VALUES ('Mario Rossi', 'mario@example.com', '28', '2024-01-15');
INSERT INTO [Clienti] VALUES ('Anna Bianchi', 'anna@example.com', '34', '2024-02-20');
...
```

## Note

- ⚠️ I nomi delle colonne vengono puliti (spazi → `_`, trattini → `_`)
- 📊 I tipi di dati vengono inferiti dai valori 
- 🔒 Le credenziali rimangono locali nel tuo PC
- 🔄 Lo script supporta fogli con diverse colonne
- ⚙️ **Personalizza tutto dal file `config.json`** senza modificare il codice Python
