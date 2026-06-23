import os
import json

# Project root path
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SRC_DIR)
DATA_DIR = os.path.join(SRC_DIR, "data")

if not os.path.exists(DATA_DIR):
    try:
        os.makedirs(DATA_DIR)
    except Exception:
        pass

KULLANICILAR_FILE = os.path.join(DATA_DIR, "kullanicilar.json")
FOLDERS_FILE = os.path.join(DATA_DIR, "klasorler.json")
PDF_PAGES_CACHE_FILE = os.path.join(DATA_DIR, "pdf_sayfa_sayilari.json")

def load_accounts_data():
    if os.path.exists(KULLANICILAR_FILE):
        try:
            with open(KULLANICILAR_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    
    # Try importing legacy kullanici.py if exists
    legacy_accounts = {}
    active_phone = ""
    legacy_path = os.path.join(ROOT_DIR, "kullanici.py")
    if os.path.exists(legacy_path):
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("kullanici", legacy_path)
            kullanici = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(kullanici)
            api_id = getattr(kullanici, "API_ID", "").strip()
            api_hash = getattr(kullanici, "API_HASH", "").strip()
            phone = getattr(kullanici, "PHONE", "").strip()
            if api_id and api_hash and phone:
                legacy_accounts[phone] = {
                    "api_id": api_id,
                    "api_hash": api_hash,
                    "phone": phone
                }
                active_phone = phone
        except Exception as e:
            print(f"Legacy kullanici.py loading error: {e}")

    data = {"active_phone": active_phone, "accounts": legacy_accounts}
    save_accounts_data(data)
    return data

def save_accounts_data(data):
    try:
        with open(KULLANICILAR_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"kullanicilar.json could not be saved: {e}")

def get_active_account():
    data = load_accounts_data()
    active_phone = data.get("active_phone", "")
    if active_phone and active_phone in data.get("accounts", {}):
        return data["accounts"][active_phone]
    # Return first if active_phone is invalid/empty but there are accounts
    accounts = data.get("accounts", {})
    if accounts:
        first_phone = list(accounts.keys())[0]
        data["active_phone"] = first_phone
        save_accounts_data(data)
        return accounts[first_phone]
    return {"api_id": "", "api_hash": "", "phone": ""}

def set_active_account(phone):
    data = load_accounts_data()
    if phone in data.get("accounts", {}):
        data["active_phone"] = phone
        save_accounts_data(data)
        return True
    return False

def add_or_update_account(api_id, api_hash, phone):
    data = load_accounts_data()
    if "accounts" not in data:
        data["accounts"] = {}
    data["accounts"][phone] = {
        "api_id": api_id.strip(),
        "api_hash": api_hash.strip(),
        "phone": phone.strip()
    }
    data["active_phone"] = phone.strip()
    save_accounts_data(data)

def delete_account(phone):
    data = load_accounts_data()
    accounts = data.get("accounts", {})
    if phone in accounts:
        del accounts[phone]
        if data.get("active_phone") == phone:
            data["active_phone"] = list(accounts.keys())[0] if accounts else ""
        save_accounts_data(data)
        return True
    return False

def load_folders():
    folders = []
    if os.path.exists(FOLDERS_FILE):
        try:
            with open(FOLDERS_FILE, "r", encoding="utf-8") as f:
                folders = json.load(f)
        except Exception:
            pass
            
    if not folders:
        # Legacy fallback from old directory
        old_folders_path = os.path.join(ROOT_DIR, "veri çekme", "klasorler.json")
        if os.path.exists(old_folders_path):
            try:
                with open(old_folders_path, "r", encoding="utf-8") as f:
                    folders = json.load(f)
                    save_folders(folders)
            except Exception:
                pass
                
    if not folders:
        folders = ["Sağlık", "Fen", "Sosyal", "YDS Çıkmışları", "Yökdil Çıkmışları", "Temp_Preview"]
        save_folders(folders)
        
    # Ensure all directories exist under 'indirilenler'
    downloads_base = os.path.join(ROOT_DIR, "indirilenler")
    for folder in folders:
        # Avoid creating folder if name contains invalid chars
        if folder:
            folder_path = os.path.join(downloads_base, folder)
            if not os.path.exists(folder_path):
                try:
                    os.makedirs(folder_path)
                except Exception:
                    pass
                    
    return folders

def save_folders(folders):
    try:
        with open(FOLDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(folders, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Folders could not be saved: {e}")

def load_pdf_pages_cache():
    if os.path.exists(PDF_PAGES_CACHE_FILE):
        try:
            with open(PDF_PAGES_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    old_cache_path = os.path.join(ROOT_DIR, "veri çekme", "pdf_sayfa_sayilari.json")
    if os.path.exists(old_cache_path):
        try:
            with open(old_cache_path, "r", encoding="utf-8") as f:
                cache = json.load(f)
                save_pdf_pages_cache(cache)
                return cache
        except Exception:
            pass
    return {}

def save_pdf_pages_cache(cache):
    try:
        with open(PDF_PAGES_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"PDF page cache could not be saved: {e}")
