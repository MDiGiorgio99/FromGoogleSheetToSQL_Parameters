import gspread
from google.oauth2.service_account import Credentials
import json
import sys
import logging
import os
from typing import List, Tuple
from datetime import datetime

try:
    import pyodbc
    PYODBC_AVAILABLE = True
except ImportError:
    PYODBC_AVAILABLE = False

# Carica la configurazione
def load_config(config_file: str = 'config.json') -> dict:
    """Carica la configurazione da file JSON"""
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"❌ Errore: File '{config_file}' non trovato.")
        print("   Crea un file config.json nella stessa cartella dello script")
        input("\nPremi INVIO per chiudere...")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"❌ Errore: Il file '{config_file}' non è un JSON valido")
        input("\nPremi INVIO per chiudere...")
        sys.exit(1)

# Carica configurazione globale
CONFIG = load_config()
SCOPES = CONFIG.get('google_sheets', {}).get('scopes', ['https://www.googleapis.com/auth/spreadsheets.readonly'])
CREDENTIALS_FILE = CONFIG.get('google_sheets', {}).get('credentials_file', 'credentials.json')

# Configura il logger
def setup_logger(log_filename: str = None) -> logging.Logger:
    """Configura il logger per salvare gli INSERT e gli errori nella cartella 'log'
    
    La modalità di logging è controllata dal flag 'log_level' nel config:
    - "full": Registra tutto (INSERT, operazioni, errori) - modalità dettagliata
    - "errors": Registra solo errori - file di log più piccolo
    """
    # Crea la cartella 'log' se non esiste
    log_dir = 'log'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    if log_filename is None:
        log_filename = f"batch_execution_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    # Salva il file nella cartella 'log'
    log_path = os.path.join(log_dir, log_filename)
    
    logger = logging.getLogger('GoogleSheetToSQL')
    
    # Leggi il flag di logging dal config
    log_level_config = CONFIG.get('logging', {}).get('log_level', 'full').lower()
    
    # Imposta il livello di logging basato sul config
    if log_level_config == 'errors':
        logger.setLevel(logging.ERROR)
        log_level = logging.ERROR
    else:  # 'full' o qualsiasi altro valore default a 'full'
        logger.setLevel(logging.INFO)
        log_level = logging.INFO
    
    # File handler
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(log_level)
    
    # Formato del log
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', 
                                 datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(formatter)
    
    # Aggiungi il file handler al logger
    if not logger.handlers:  # Evita handler duplicati
        logger.addHandler(file_handler)
    
    return logger

# Crea il logger globale
LOGGER = setup_logger()


class GoogleSheetToSQL:
    def __init__(self, credentials_file: str):
        """Inizializza la connessione a Google Sheets"""
        try:
            self.creds = Credentials.from_service_account_file(
                credentials_file, 
                scopes=SCOPES
            )
            self.client = gspread.authorize(self.creds)
            print("✓ Autenticazione riuscita a Google Sheets")
        except FileNotFoundError:
            print(f"❌ Errore: File '{credentials_file}' non trovato.")
            print("   Scarica le credenziali da Google Cloud Console e rinomina il file")
            input("\nPremi INVIO per chiudere...")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Errore di autenticazione: {e}")
            input("\nPremi INVIO per chiudere...")
            sys.exit(1)

    def open_spreadsheet(self, spreadsheet_id: str):
        """Apre il Google Sheet usando l'ID"""
        try:
            self.sheet = self.client.open_by_key(spreadsheet_id)
            print(f"✓ Google Sheet aperto: {self.sheet.title}")
        except Exception as e:
            print(f"\n❌ Errore nell'apertura del file:")
            print(f"   {type(e).__name__}: {str(e)}")
            print("\n💡 Soluzione possibile:")
            print("   1. Verifica l'ID del Google Sheet (deve essere la parte della URL dopo /d/)")
            print("   2. Condividi il Google Sheet con l'email del service account")
            print("   3. Verifica che le credenziali siano corrette in credentials.json")
            input("\nPremi INVIO per chiudere...")
            sys.exit(1)

    def list_sheets(self) -> List[str]:
        """Elenca tutti i fogli disponibili"""
        sheet_names = [ws.title for ws in self.sheet.worksheets()]
        return sheet_names

    def get_worksheet(self, sheet_name: str) -> object:
        """Ottiene il foglio per nome"""
        try:
            return self.sheet.worksheet(sheet_name)
        except Exception as e:
            raise Exception(f"Foglio '{sheet_name}' non trovato: {e}")

    def infer_column_type(self, values: List, for_sqlserver: bool = True) -> str:
        """Inferisce il tipo SQL per una colonna con distinzione avanzata"""
        import re
        from datetime import datetime
        
        # Leggi i tipi dal config
        sql_types = CONFIG.get('sql_generation', {})
        string_type = sql_types.get('string_type', 'VARCHAR(MAX)')
        int_type = sql_types.get('int_type', 'INT')
        float_type = sql_types.get('float_type', 'FLOAT')
        bool_type = sql_types.get('bool_type', 'BIT')
        datetime_type = sql_types.get('datetime_type', 'DATETIME')
        
        # Filtra valori vuoti
        non_empty = [str(v).strip() for v in values if v and str(v).strip()]
        
        if not non_empty:
            return string_type if for_sqlserver else "TEXT"
        
        # Conta i tipi rilevati
        is_int = True
        is_float = True
        is_bool = True
        is_date = True
        
        date_patterns = [
            r'^\d{1,2}/\d{1,2}/\d{4}$',  # DD/MM/YYYY
            r'^\d{4}-\d{1,2}-\d{1,2}$',  # YYYY-MM-DD
            r'^\d{1,2}-\d{1,2}-\d{4}$',  # DD-MM-YYYY
            r'^\d{4}/\d{1,2}/\d{1,2}$',  # YYYY/MM/DD
        ]
        
        bool_values = {'true', 'false', 'yes', 'no', 'sì', 'si', 'vero', 'falso', '1', '0', 'y', 'n'}
        
        for val in non_empty:
            # Test INT
            if is_int:
                try:
                    int(val)
                except ValueError:
                    is_int = False
            
            # Test FLOAT
            if is_float:
                try:
                    float(val)
                except ValueError:
                    is_float = False
            
            # Test BOOLEAN
            if is_bool:
                if val.lower() not in bool_values:
                    is_bool = False
            
            # Test DATE
            if is_date:
                match_found = False
                for pattern in date_patterns:
                    if re.match(pattern, val):
                        match_found = True
                        break
                
                # Prova anche a parsare come data
                if not match_found:
                    try:
                        datetime.strptime(val, '%d/%m/%Y')
                        match_found = True
                    except:
                        try:
                            datetime.strptime(val, '%Y-%m-%d')
                            match_found = True
                        except:
                            pass
                
                if not match_found:
                    is_date = False
        
        # Determina il tipo
        if is_bool and len(non_empty) >= 1:
            return bool_type if for_sqlserver else "INTEGER"
        elif is_date and len(non_empty) >= 1:
            return datetime_type if for_sqlserver else "TEXT"
        elif is_int and len(non_empty) >= 1:
            return int_type if for_sqlserver else "INTEGER"
        elif is_float:
            return float_type if for_sqlserver else "REAL"
        else:
            return string_type if for_sqlserver else "TEXT"

    def get_data_and_headers(self, worksheet) -> Tuple[List[str], List[List]]:
        """Ottiene headers e dati dal foglio, eliminando colonne vuote"""
        all_values = worksheet.get_all_values()
        
        if not all_values or len(all_values) < 1:
            print("❌ Il foglio è vuoto")
            return [], []
        
        headers = all_values[0]
        data = all_values[1:]
        
        # Rimuovi righe completamente vuote
        data = [row for row in data if any(cell.strip() for cell in row)]
        
        # Identifica colonne vuote
        non_empty_cols = []
        for col_idx, header in enumerate(headers):
            # Controlla se la colonna ha almeno un valore non vuoto
            has_value = any(
                col_idx < len(row) and row[col_idx].strip() 
                for row in data
            )
            # Anche l'header deve avere un valore
            if header.strip() or has_value:
                non_empty_cols.append(col_idx)
        
        # Filtra headers e dati mantenendo solo le colonne non vuote
        filtered_headers = [headers[i] for i in non_empty_cols]
        filtered_data = []
        for row in data:
            filtered_row = [row[i] if i < len(row) else '' for i in non_empty_cols]
            filtered_data.append(filtered_row)
        
        removed_count = len(headers) - len(filtered_headers)
        if removed_count > 0:
            print(f"⚠️  Rimosse {removed_count} colonna/e vuote")
        
        print(f"\n✓ Estratti {len(filtered_data)} record con {len(filtered_headers)} colonne")
        return filtered_headers, filtered_data

    def clean_value(self, value: str) -> str:
        """Pulisce i valori per l'SQL"""
        if not value or str(value).strip() == '':
            return 'NULL'
        value = str(value).replace("'", "''")  # Escape single quotes
        return f"'{value}'"
    
    def clean_table_name(self, name: str) -> str:
        """Pulisce il nome per usarlo come nome di tabella SQL"""
        import re
        
        # Rimuovi accenti e caratteri speciali
        # Sostituisci spazi e caratteri speciali con underscore
        name = str(name).strip()
        
        # Sostituisci spazi con underscore
        name = name.replace(' ', '_')
        
        # Rimuovi caratteri non alfanumerici (eccetto underscore)
        # Mantieni solo a-z, A-Z, 0-9 e underscore
        name = re.sub(r'[^a-zA-Z0-9_]', '', name)
        
        # Rimuovi underscore multipli consecutivi
        name = re.sub(r'_+', '_', name)
        
        # Rimuovi underscore all'inizio e alla fine
        name = name.strip('_')
        
        # Se il nome è vuoto dopo la pulizia, usa un default
        if not name:
            name = 'Table'
        
        return name

    def generate_sql(self, spreadsheet_name: str, sheet_name: str, headers: List[str], data: List[List], drop_create: str = "create") -> str:
        """Genera SQL con opzione di DROP+CREATE, TRUNCATE, o solo INSERT
        
        Modalità:
        - "create": DROP TABLE IF EXISTS + CREATE TABLE + INSERT
        - "truncate": TRUNCATE TABLE + INSERT
        - "insert": Solo INSERT (senza modificare la struttura)
        """
        sql = []
        
        # Pulisci i nomi prima di concatenarli
        clean_spreadsheet_name = self.clean_table_name(spreadsheet_name)
        clean_sheet_name = self.clean_table_name(sheet_name)
        table_name = f"{clean_spreadsheet_name}_{clean_sheet_name}"
        
        sql.append(f"-- Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')};")
        
        # Genera comandi specifici in base alla modalità
        if drop_create == "create":
            # DROP + CREATE (ricrea la tabella)
            sql.append(f"\nDROP TABLE IF EXISTS [{table_name}];")
            sql.append(f"\nCREATE TABLE [{table_name}] (")
            
            # Inferisci i tipi di colonna (ottimizzati per SQL Server)
            column_types = []
            for col_idx, header in enumerate(headers):
                values = [row[col_idx] if col_idx < len(row) else '' for row in data]
                col_type = self.infer_column_type(values, for_sqlserver=True)
                column_types.append(col_type)
                
                clean_header = header.replace(' ', '_').replace('-', '_')
                sql.append(f"    [{clean_header}] {col_type},")
            
            # Rimuovi la virgola dall'ultima colonna
            if sql[-1].endswith(","):
                sql[-1] = sql[-1][:-1]
            
            sql.append(");")
        
        elif drop_create == "truncate":
            # TRUNCATE (svuota ma mantiene la struttura)
            sql.append(f"\nTRUNCATE TABLE [{table_name}];")
            
            # Inferisci i tipi comunque (potrebbero servire per conversioni)
            column_types = []
            for col_idx, header in enumerate(headers):
                values = [row[col_idx] if col_idx < len(row) else '' for row in data]
                col_type = self.infer_column_type(values, for_sqlserver=True)
                column_types.append(col_type)
        
        else:  # "insert" o qualsiasi altro valore
            # Solo INSERT (mantieni la struttura e i dati)
            column_types = []
            for col_idx, header in enumerate(headers):
                values = [row[col_idx] if col_idx < len(row) else '' for row in data]
                col_type = self.infer_column_type(values, for_sqlserver=True)
                column_types.append(col_type)
        
        # INSERT statements
        sql.append(f"\n-- Insert {len(data)} records;")
        bool_type = CONFIG.get('sql_generation', {}).get('bool_type', 'BIT')
        
        for row in data:
            values = []
            for col_idx, cell in enumerate(row):
                # Se il tipo della colonna è BIT, converti i valori booleani a 1 o 0
                if column_types[col_idx] == bool_type:
                    cell_lower = str(cell).strip().lower()
                    if cell_lower in {'true', 'yes', 'sì', 'si', 'vero', '1', 'y'}:
                        values.append('1')
                    elif cell_lower in {'false', 'no', 'falso', '0', 'n'}:
                        values.append('0')
                    else:
                        # Se non riconosce il valore, usa il comportamento standard
                        values.append(self.clean_value(cell))
                else:
                    values.append(self.clean_value(cell))
            
            insert = f"INSERT INTO [{table_name}] VALUES ({', '.join(values)});"
            sql.append(insert)
        
        return "\n".join(sql)

    def export_to_file(self, sql: str, filename: str = None):
        """Esporta l'SQL in un file"""
        if filename is None:
            filename = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        else:
            # Aggiungi .sql se non è già presente
            if not filename.lower().endswith('.sql'):
                filename = f"{filename}.sql"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(sql)
        
        print(f"\n✓ SQL esportato in: {filename}")
        return filename

    def execute_on_sqlserver(self, sql: str, server: str = None, database: str = None, 
                            use_windows_auth: bool = None, username: str = None, password: str = None) -> bool:
        """Esegue la query su SQL Server con logging degli INSERT e degli errori"""
        if not PYODBC_AVAILABLE:
            print("❌ Modulo pyodbc non installato!")
            print("   Installa con: pip install pyodbc")
            return False
        
        # Leggi i default dal config
        sql_server_config = CONFIG.get('sql_server', {})
        default_server = sql_server_config.get('default_server', '')
        default_database = sql_server_config.get('default_database', '')
        default_auth = sql_server_config.get('use_windows_auth', True)
        default_username = sql_server_config.get('username')
        default_password = sql_server_config.get('password')
        
        # Usa i default se non forniti
        server = server or default_server
        database = database or default_database
        if use_windows_auth is None:
            use_windows_auth = default_auth
        
        # Se non forniti come parametri, usa quelli del config
        if username is None:
            username = default_username
        if password is None:
            password = default_password
        
        if not server or not database:
            print("❌ Server e database sono obbligatori in config.json")
            return False
        
        try:
            # Costruisci la connection string
            if use_windows_auth:
                conn_str = f'Driver={{ODBC Driver 17 for SQL Server}};Server={server};Database={database};Trusted_Connection=yes;'
            else:
                if username is None or password is None:
                    print("❌ Username e password sono obbligatori per autenticazione SQL")
                    return False
                conn_str = f'Driver={{ODBC Driver 17 for SQL Server}};Server={server};Database={database};UID={username};PWD={password};'
            
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()
            
            # Dividi i comandi
            commands = [cmd.strip() for cmd in sql.split(';') if cmd.strip()]
            
            for i, command in enumerate(commands):
                if command.startswith('--'):  # Salta i commenti ma loggali
                    continue
                
                # Logga l'INSERT statement SEMPRE (prima dell'esecuzione)
                if command.upper().startswith('INSERT INTO'):
                    LOGGER.info(command)
                
                try:
                    cursor.execute(command)
                    
                    # Log di successo per INSERT
                    if command.upper().startswith('INSERT INTO'):
                        LOGGER.info("✓ Successo\n")
                
                except Exception as e:
                    # Logga l'errore per INSERT
                    if command.upper().startswith('INSERT INTO'):
                        LOGGER.error(f"❌ Errore: {str(e)}\n")
                    else:
                        # Per altri comandi, logga ugualmente
                        LOGGER.error(f"❌ Errore nel comando: {command[:100]}...")
                        LOGGER.error(f"   Dettagli: {str(e)}")
                    
                    # Non fare rollback - continua con gli altri comandi
                    print(f"⚠️  Errore nel comando {i+1}: {e}")
                    print(f"   Comando: {command[:100]}...")
            
            conn.commit()
            conn.close()
            LOGGER.info("=" * 70)
            LOGGER.info("Elaborazione completata con successo")
            LOGGER.info("=" * 70)
            return True
        
        except Exception as e:
            print(f"❌ Errore di connessione a SQL Server: {e}")
            print("💡 Verifica: server, database, credenziali, driver ODBC")
            LOGGER.error(f"❌ Errore di connessione a SQL Server: {e}")
            return False


def process_batch(converter, download_config: List[dict], use_windows_auth: bool = True):
    """Elabora un batch di fogli da salvare su SQL Server"""
    total = len(download_config)
    success_count = 0
    failed_count = 0
    
    # Log inizio elaborazione
    LOGGER.info("=" * 70)
    LOGGER.info(f"INIZIO ELABORAZIONE BATCH: {total} foglio/i")
    LOGGER.info("=" * 70)
    
    print(f"\n{'=' * 70}")
    print(f"📥 Inizio elaborazione batch: {total} foglio/i")
    print(f"{'=' * 70}\n")
    
    for idx, config in enumerate(download_config, 1):
        try:
            spreadsheet_id = config.get('spreadsheet')
            sheet_name = config.get('sheet')
            
            # Leggi dropCreate e converti per backward compatibility
            drop_create_value = config.get('dropCreate', 'create')
            
            # Se è un booleano (per backward compatibility), converti a stringa
            if isinstance(drop_create_value, bool):
                drop_create = "create" if drop_create_value else "insert"
            else:
                drop_create = str(drop_create_value).lower()
            
            # Valida il valore
            if drop_create not in ['create', 'truncate', 'insert']:
                print(f"        ⚠️  Modalità '{drop_create}' non valida, uso 'create' di default")
                drop_create = 'create'
            
            print(f"[{idx}/{total}] Elaborazione: Sheet '{sheet_name}' da '{spreadsheet_id}'")
            LOGGER.info(f"[{idx}/{total}] Elaborazione: Sheet '{sheet_name}' - Modalità: {drop_create.upper()}")
            
            # Apri lo spreadsheet
            converter.open_spreadsheet(spreadsheet_id)
            
            # Ottieni il foglio
            worksheet = converter.get_worksheet(sheet_name)
            
            # Estrai dati
            headers, data = converter.get_data_and_headers(worksheet)
            
            if not headers or not data:
                print(f"        ❌ Nessun dato trovato nel foglio")
                LOGGER.warning(f"Nessun dato trovato nel foglio '{sheet_name}'")
                failed_count += 1
                continue
            
            print(f"        ✓ Estratti {len(data)} record con {len(headers)} colonne")
            LOGGER.info(f"Estratti {len(data)} record con {len(headers)} colonne")
            
            # Genera SQL
            spreadsheet_name = converter.sheet.title
            sql = converter.generate_sql(spreadsheet_name, sheet_name, headers, data, drop_create=drop_create)
            print(f"        ✓ SQL generato ({drop_create.upper()})")
            
            # Esegui su SQL Server
            if converter.execute_on_sqlserver(sql, use_windows_auth=use_windows_auth):
                print(f"        ✓ Dati inseriti su SQL Server\n")
                success_count += 1
            else:
                print(f"        ❌ Errore nell'esecuzione su SQL Server\n")
                LOGGER.error(f"Errore nell'esecuzione su SQL Server per il foglio '{sheet_name}'")
                failed_count += 1
                
        except Exception as e:
            print(f"        ❌ Errore: {str(e)}\n")
            LOGGER.error(f"Eccezione durante l'elaborazione: {str(e)}")
            failed_count += 1
    
    # Riepilogo
    print(f"{'=' * 70}")
    print(f"📊 Elaborazione completata:")
    print(f"   ✓ Successo: {success_count}/{total}")
    print(f"   ❌ Falliti:  {failed_count}/{total}")
    print(f"{'=' * 70}\n")
    
    # Log riepilogo
    LOGGER.info("=" * 70)
    LOGGER.info(f"RIEPILOGO ELABORAZIONE:")
    LOGGER.info(f"Successo: {success_count}/{total}")
    LOGGER.info(f"Falliti: {failed_count}/{total}")
    LOGGER.info("=" * 70)
    
    return success_count, failed_count


def main():
    """Elabora un batch di sheet da un file batch.json"""
    print("=" * 70)
    print("  Google Sheets to SQL Converter - Batch Mode")
    print("=" * 70)
    
    # Mostra il file di log
    log_file = LOGGER.handlers[0].baseFilename if LOGGER.handlers else "batch_execution.log"
    print(f"\n📝 Log salvato in: {log_file}\n")
    
    # Richiedi il file di configurazione come parametro obbligatorio
    if len(sys.argv) < 2:
        print("\n❌ Errore: Devi specificare il file di configurazione")
        print("\nUtilizzo:")
        print("  python GoogleSheet_to_SQL.py batch.json")
        print("\nEsempio:")
        print("  python GoogleSheet_to_SQL.py batch.json")
        input("\nPremi INVIO per chiudere...")
        sys.exit(1)
    
    download_file = sys.argv[1]
    
    # Verifica che il file esista
    try:
        with open(download_file, 'r', encoding='utf-8') as f:
            download_config = json.load(f)
    except FileNotFoundError:
        print(f"\n❌ Errore: File '{download_file}' non trovato.")
        print(f"   Crea il file con la seguente struttura:")
        print(f"""
[{{
  "spreadsheet": "ID_DELLO_SHEET",
  "sheet": "Nome del foglio",
  "dropCreate": true
}},
{{
  "spreadsheet": "ID_DELLO_SHEET",
  "sheet": "Nome del foglio",
  "dropCreate": false
}}]
""")
        input("\nPremi INVIO per chiudere...")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"\n❌ Errore: Il file '{download_file}' non è un JSON valido")
        input("\nPremi INVIO per chiudere...")
        sys.exit(1)
    
    # Valida il formato
    if not isinstance(download_config, list) or len(download_config) == 0:
        print(f"\n❌ Errore: Il file '{download_file}' deve contenere un array JSON non vuoto")
        input("\nPremi INVIO per chiudere...")
        sys.exit(1)
    
    # Valida gli elementi
    required_keys = ['spreadsheet', 'sheet']
    for idx, config in enumerate(download_config):
        for key in required_keys:
            if key not in config:
                print(f"\n❌ Errore: Elemento {idx+1} non contiene il campo '{key}'")
                input("\nPremi INVIO per chiudere...")
                sys.exit(1)
    
    # Inizializza il converter
    converter = GoogleSheetToSQL(CREDENTIALS_FILE)
    
    # Leggi config per l'autenticazione a SQL Server
    sql_server_config = CONFIG.get('sql_server', {})
    default_auth = sql_server_config.get('use_windows_auth', True)
    
    # Elabora il batch
    process_batch(converter, download_config, use_windows_auth=default_auth)
    
    print("✓ Processo completato!")


if __name__ == "__main__":
    main()
