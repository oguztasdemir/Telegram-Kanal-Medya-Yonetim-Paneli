import os
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError, PhoneCodeExpiredError
from src.config import get_active_account, ROOT_DIR, delete_account, DATA_DIR

client = None
phone_code_hash = None

async def get_client():
    global client
    return client

async def init_telethon(force_reconnect=False):
    global client
    active = get_active_account()
    api_id = active.get("api_id")
    api_hash = active.get("api_hash")
    phone = active.get("phone")
    
    if not api_id or not api_hash or not phone:
        print("Telethon not initialized: missing active account credentials.")
        return None
        
    if client:
        # If client is already for the active phone number and connected, keep it
        if client.api_id == int(api_id) and getattr(client, "_phone", "") == phone and not force_reconnect:
            if client.is_connected():
                return client
        
        # Otherwise disconnect old client
        try:
            await client.disconnect()
        except Exception:
            pass
            
    try:
        session_path = os.path.join(DATA_DIR, f"session_{phone.replace('+', '')}")
        client = TelegramClient(session_path, int(api_id), api_hash)
        client._phone = phone  # Attach helper property
        await client.connect()
        print(f"Telethon client connected successfully for account: {phone}")
        return client
    except Exception as e:
        print(f"Telethon connection error for {phone}: {e}")
        return None

async def is_authorized():
    global client
    if not client:
        await init_telethon()
    if not client:
        return False
    try:
        return await client.is_user_authorized()
    except Exception:
        return False

async def send_code_request_auth():
    global client, phone_code_hash
    if not client:
        await init_telethon()
    if not client:
        raise Exception("Client is not initialized. Please verify credentials.")
        
    active = get_active_account()
    phone = active.get("phone")
    if not phone:
        raise Exception("Active phone number not found.")
        
    res = await client.send_code_request(phone)
    phone_code_hash = res.phone_code_hash
    return phone_code_hash

async def sign_in_code(code):
    global client, phone_code_hash
    if not client or not phone_code_hash:
        raise Exception("Code request must be sent first.")
        
    active = get_active_account()
    phone = active.get("phone")
    
    try:
        await client.sign_in(phone, code, phone_code_hash=phone_code_hash)
        return "success"
    except SessionPasswordNeededError:
        return "2fa_required"

async def sign_in_password(password):
    global client
    if not client:
        raise Exception("Client is not connected.")
    await client.sign_in(password=password)
    return "success"

async def logout_active():
    global client
    active = get_active_account()
    phone = active.get("phone")
    
    if client:
        try:
            await client.log_out()
        except Exception:
            pass
        try:
            await client.disconnect()
        except Exception:
            pass
        client = None

    if phone:
        # Delete session file
        session_file = os.path.join(DATA_DIR, f"session_{phone.replace('+', '')}.session")
        if os.path.exists(session_file):
            try:
                os.remove(session_file)
            except Exception:
                pass
                
        # We can keep it in kullanicilar.json so they can quick-login again (as requested: "hızlı giriş gibi şeyler olsun eğer hesaptan çıkarsa")
        # To do a quick login, it's just saved in the accounts database but the session is cleared.
        # So we keep the account record in kullanicilar.json but they will need to request code if they sign back in.
