import gspread
from google.oauth2.service_account import Credentials
import json
import sys
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

    def select_sheet_interactive(self) -> Tuple[str, object]:
        """Mostra un menu interattivo per scegliere il foglio"""
        sheets = self.list_sheets()
        
        print("\n📄 Fogli disponibili:")
        for i, sheet_name in enumerate(sheets, 1):
            print(f"  {i}. {sheet_name}")
        
        while True:
            try:
                choice = input(f"\nScegli il numero del foglio (1-{len(sheets)}): ").strip()
                idx = int(choice) - 1
                if 0 <= idx < len(sheets):
                    selected_name = sheets[idx]
                    selected_ws = self.sheet.worksheet(selected_name)
                    print(f"✓ Selezionato: {selected_name}")
                    return selected_name, selected_ws
                else:
                    print("❌ Numero non valido")
            except ValueError:
                print("❌ Inserisci un numero valido")

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

    def generate_sql(self, spreadsheet_name: str, sheet_name: str, headers: List[str], data: List[List]) -> str:
        """Genera SQL DROP + CREATE TABLE + INSERT statements"""
        sql = []
        
        # Pulisci i nomi prima di concatenarli
        clean_spreadsheet_name = self.clean_table_name(spreadsheet_name)
        clean_sheet_name = self.clean_table_name(sheet_name)
        table_name = f"{clean_spreadsheet_name}_{clean_sheet_name}"
        
        # DROP TABLE IF EXISTS + CREATE TABLE (sintassi corretta SQL Server)
        sql.append(f"-- Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')};")
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
        """Esegue la query su SQL Server"""
        if not PYODBC_AVAILABLE:
            print("❌ Modulo pyodbc non installato!")
            print("   Installa con: pip install pyodbc")
            return False
        
        # Leggi i default dal config
        sql_server_config = CONFIG.get('sql_server', {})
        default_server = sql_server_config.get('default_server', '')
        default_database = sql_server_config.get('default_database', '')
        default_auth = sql_server_config.get('use_windows_auth', True)
        
        # Chiedi i dettagli se non forniti
        if server is None:
            if default_server:
                print(f"🔧 Server default (config.json): {default_server}")
                server = input(f"Inserisci il nome del server SQL Server (default: {default_server}): ").strip()
                if not server:
                    server = default_server
            else:
                server = input("\nInserisci il nome del server SQL Server (es: localhost, .\\SQLEXPRESS): ").strip()
        
        if database is None:
            if default_database:
                print(f"🔧 Database default (config.json): {default_database}")
                database = input(f"Inserisci il nome del database (default: {default_database}): ").strip()
                if not database:
                    database = default_database
            else:
                database = input("Inserisci il nome del database: ").strip()
        
        if use_windows_auth is None:
            use_windows_auth = default_auth
        
        if not server or not database:
            print("❌ Server e database sono obbligatori")
            return False
        
        try:
            # Costruisci la connection string
            if use_windows_auth:
                conn_str = f'Driver={{ODBC Driver 17 for SQL Server}};Server={server};Database={database};Trusted_Connection=yes;'
            else:
                if username is None:
                    username = input("Username SQL Server: ").strip()
                if password is None:
                    password = input("Password: ").strip()
                conn_str = f'Driver={{ODBC Driver 17 for SQL Server}};Server={server};Database={database};UID={username};PWD={password};'
            
            conn = pyodbc.connect(conn_str)
            cursor = conn.cursor()
            
            # Dividi i comandi
            commands = [cmd.strip() for cmd in sql.split(';') if cmd.strip()]
            
            print(f"\n📋 Esecuzione di {len(commands)} comandi...")
            for i, command in enumerate(commands):
                if command.startswith('--'):  # Salta i commenti
                    continue
                try:
                    # Mostra anteprima del comando (primi 80 caratteri)
                    preview = command[:80].replace('\n', ' ')
                    print(f"  [{i}] {preview}..." if len(command) > 80 else f"  [{i}] {preview}")
                    cursor.execute(command)
                except Exception as e:
                    print(f"\n❌ Errore nel comando {i+1}: {e}")
                    print(f"   Comando: {command[:100]}...")
                    conn.rollback()
                    return False
            
            conn.commit()
            conn.close()
            print(f"\n✓ Query eseguita con successo su SQL Server: {server}/{database}")
            return True
        
        except Exception as e:
            print(f"\n❌ Errore di connessione a SQL Server: {e}")
            print("💡 Verifica: server, database, credenziali, driver ODBC installato")
            return False


def process_sheet(converter, sheet_names_count: int = None):
    """Elabora un singolo foglio: selezione, estrazione, generazione SQL e salvataggio"""
    
    # Seleziona il foglio
    sheet_name, worksheet = converter.select_sheet_interactive()
    
    # Estrai dati
    headers, data = converter.get_data_and_headers(worksheet)
    
    if not headers or not data:
        print("❌ Nessun dato da esportare")
        return False
    
    # Mostra preview
    print("\n📋 Preview dei dati:")
    print(f"  Colonne: {', '.join(headers[:5])}{'...' if len(headers) > 5 else ''}")
    print(f"  Prime righe: {data[:2] if data else 'Nessun dato'}")
    
    # Genera SQL (nomefile_sheet_name)
    spreadsheet_name = converter.sheet.title
    sql = converter.generate_sql(spreadsheet_name, sheet_name, headers, data)
    
    # Mostra anteprima SQL
    print("\n📝 Anteprima SQL (prime 20 righe):")
    sql_lines = sql.split('\n')[:20]
    for line in sql_lines:
        print(f"  {line}")
    if len(sql.split('\n')) > 20:
        print("  ...")
    
    # Menu: Esegui o Salva
    print("\n" + "=" * 60)
    print("💾 Cosa vuoi fare?")
    print("  1. Esegui query su SQL Server")
    print("  2. Salva come file .sql")
    print("  3. Esegui e salva")
    print("=" * 60)
    
    while True:
        choice = input("\nScegli un'opzione (1-3): ").strip()
        if choice in ['1', '2', '3']:
            break
        print("❌ Opzione non valida")
    
    # Esegui su database
    if choice in ['1', '3']:
        auth = input("\nUsa autenticazione Windows? (s/n): ").strip().lower()
        use_windows_auth = auth == 's'
        converter.execute_on_sqlserver(sql, use_windows_auth=use_windows_auth)
    
    # Salva file
    if choice in ['2', '3']:
        save = input("\nSalvare su file? (s/n): ").strip().lower()
        if save == 's':
            filename = input("Nome file (default: auto): ").strip()
            converter.export_to_file(sql, filename if filename else None)
    
    # Copia negli appunti (solo su Windows)
    try:
        import pyperclip
        copy = input("\nCopiare il SQL negli appunti? (s/n): ").strip().lower()
        if copy == 's':
            pyperclip.copy(sql)
            print("✓ SQL copiato negli appunti")
    except ImportError:
        pass
    
    return True


def main():
    """Funzione principale"""
    print("=" * 60)
    print("  Google Sheets to SQL Converter")
    print("=" * 60)
    
    # Leggi il default Google Sheet ID dal config
    google_sheets_config = CONFIG.get('google_sheets', {})
    default_sheet_id = google_sheets_config.get('default_sheet_id', '')
    
    # Chiedi l'ID del Google Sheet
    if default_sheet_id:
        print(f"🔧 Google Sheet ID default (config.json): {default_sheet_id}")
        sheet_id = input(f"\nInserisci l'ID del Google Sheet (default: {default_sheet_id}): ").strip()
        if not sheet_id:
            sheet_id = default_sheet_id
    else:
        sheet_id = input("\nInserisci l'ID del Google Sheet (dalla URL): ").strip()
    
    if not sheet_id:
        print("❌ ID non fornito")
        input("\nPremi INVIO per chiudere...")
        sys.exit(1)
    
    # Inizializza
    converter = GoogleSheetToSQL(CREDENTIALS_FILE)
    converter.open_spreadsheet(sheet_id)
    
    # Loop: elabora fogli finché l'utente non decide di uscire
   
    while True:
        if not process_sheet(converter):
            continue
        
        # Chiedi se vuole scaricare dati da altri fogli
        print("\n" + "=" * 60)
        while True:
            another = input("\n📄 Vuoi scaricare dati da un altro foglio? (s/n): ").strip().lower()
            if another in ['s', 'n']:
                break
            print("❌ Inserisci 's' per sì o 'n' per no")
        
        if another != 's':
            break
    
    print("\n✓ Processo completato!")


if __name__ == "__main__":
    main()
