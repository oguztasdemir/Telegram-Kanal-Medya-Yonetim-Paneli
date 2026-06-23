import os
import shutil
import sys
import io
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel
from pypdf import PdfReader

import src.config as config
import src.auth as auth
import src.media as media
from src.downloads import download_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await auth.init_telethon()
    download_manager.start()
    yield
    # Shutdown
    await download_manager.stop()
    client = await auth.get_client()
    if client:
        try:
            await client.disconnect()
        except Exception:
            pass

app = FastAPI(lifespan=lifespan)

# Pydantic models for requests
class ConfigModel(BaseModel):
    api_id: str
    api_hash: str
    phone: str

class CodeModel(BaseModel):
    code: str

class PasswordModel(BaseModel):
    password: str

class DownloadModel(BaseModel):
    channel_id: int
    message_id: int
    filename: str
    target_folder: str

class LeaveChannelModel(BaseModel):
    channel_id: int

class ToggleArchiveModel(BaseModel):
    channel_id: int
    archive: bool

class ToggleMuteModel(BaseModel):
    channel_id: int
    mute: bool

class SendMessageModel(BaseModel):
    channel_id: int
    message_text: str

class BatchDownloadModel(BaseModel):
    channel_id: int
    downloads: list[dict] # list of {"message_id": int, "filename": str}
    target_folder: str

class CancelDownloadModel(BaseModel):
    task_id: str

class FolderModel(BaseModel):
    name: str

class ZipDownloadModel(BaseModel):
    channel_id: int = 0
    downloads: list[dict] # list of {"channel_id": int, "message_id": int, "filename": str}

class SwitchAccountModel(BaseModel):
    phone: str

@app.get("/", response_class=HTMLResponse)
async def get_index():
    template_path = os.path.join(config.SRC_DIR, "templates", "index.html")
    if os.path.exists(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h3>templates/index.html bulunamadı!</h3>"

@app.get("/api/status")
async def get_status():
    active = config.get_active_account()
    api_id = active.get("api_id", "")
    api_hash = active.get("api_hash", "")
    phone = active.get("phone", "")
    
    is_auth = await auth.is_authorized()
            
    return {
        "configured": bool(api_id and api_hash),
        "authorized": is_auth,
        "phone": phone,
        "api_id": api_id,
        "api_hash": api_hash
    }

@app.get("/api/accounts")
async def get_accounts():
    return config.load_accounts_data()

@app.post("/api/switch_account")
async def switch_account(data: SwitchAccountModel):
    success = config.set_active_account(data.phone)
    if not success:
        raise HTTPException(status_code=400, detail="Hesap bulunamadı.")
    
    # Re-initialize the Telethon client with the new active account
    await auth.init_telethon(force_reconnect=True)
    is_auth = await auth.is_authorized()
    media.clear_caches()
    return {
        "status": "success",
        "authorized": is_auth,
        "phone": data.phone
    }

@app.delete("/api/accounts")
async def delete_saved_account(phone: str):
    # If the user is deleting the currently logged-in account, log out first
    active = config.get_active_account()
    if active.get("phone") == phone:
        await auth.logout_active()
    
    config.delete_account(phone)
    return {"status": "success"}

@app.post("/api/save_config")
async def save_config(cfg: ConfigModel):
    media.clear_caches()
    try:
        # Save to kullanicilar.json (adding or updating)
        config.add_or_update_account(cfg.api_id, cfg.api_hash, cfg.phone)
            
        # Re-init client
        await auth.init_telethon(force_reconnect=True)
        return {"status": "success", "message": "Bilgiler kaydedildi."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/send_code")
async def send_code():
    try:
        await auth.send_code_request_auth()
        return {"status": "success", "message": "Doğrulama kodu gönderildi."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Kod gönderme hatası: {e}")

@app.post("/api/login_code")
async def login_code(data: CodeModel):
    try:
        res = await auth.sign_in_code(data.code)
        if res == "success":
            return {"status": "success", "message": "Giriş başarılı."}
        elif res == "2fa_required":
            return {"status": "2fa_required", "message": "İki adımlı doğrulama şifresi gerekli."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/login_2fa")
async def login_2fa(data: PasswordModel):
    try:
        await auth.sign_in_password(data.password)
        return {"status": "success", "message": "Giriş başarılı."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Şifre hatalı veya doğrulanamadı: {e}")

@app.post("/api/logout")
async def logout():
    await auth.logout_active()
    media.clear_caches()
    return {"status": "success"}

@app.post("/api/clear_cache")
async def clear_cache():
    media.clear_caches()
    config.save_pdf_pages_cache({})
    
    # Folders to delete preview files from
    folders_to_clear = [
        os.path.join(config.ROOT_DIR, "Temp_Preview"),
        os.path.join(config.ROOT_DIR, "indirilenler", "Temp_Preview")
    ]
    for folder in folders_to_clear:
        if os.path.exists(folder):
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)
                except Exception as e:
                    print(f"Failed to delete {file_path}. Reason: {e}")
                    
    return {"status": "success"}

@app.get("/api/channels")
async def get_channels(q: str = "", show_archived: bool = False):
    client = await auth.get_client()
    if not client or not await auth.is_authorized():
        return {"channels": []}
        
    try:
        dialogs = await client.get_dialogs(limit=100)
        archived_ch = []
        normal_ch = []
        q_norm = "".join(c for c in q.lower() if c.isalnum()) if q else ""
        
        for d in dialogs:
            chat_type = "channel"
            if d.is_group:
                chat_type = "group"
            elif d.is_user:
                chat_type = "user"
                
            if not show_archived and d.folder_id == 1:
                continue
                
            name = d.name or "Bilinmeyen Sohbet"
            if q_norm:
                name_norm = "".join(c for c in name.lower() if c.isalnum())
                if q_norm not in name_norm:
                    continue
            
            is_muted = False
            try:
                if d.dialog.notify_settings and d.dialog.notify_settings.mute_until:
                    from datetime import datetime, timezone
                    mute_until = d.dialog.notify_settings.mute_until
                    if mute_until.timestamp() > datetime.now(timezone.utc).timestamp():
                        is_muted = True
            except Exception:
                pass

            ch_info = {
                "name": name,
                "id": d.id,
                "type": chat_type,
                "folder_id": d.folder_id or 0,
                "muted": is_muted
            }
            
            if d.folder_id == 1:
                archived_ch.append(ch_info)
            else:
                normal_ch.append(ch_info)
        return {"channels": archived_ch + normal_ch}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/leave_channel")
async def leave_channel(data: LeaveChannelModel):
    client = await auth.get_client()
    if not client or not await auth.is_authorized():
        raise HTTPException(status_code=401, detail="Oturum açılmamış.")
    try:
        entity = await client.get_entity(data.channel_id)
        await client.delete_dialog(entity)
        return {"status": "success", "message": "Sohbetten ayrılındı."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/toggle_archive")
async def toggle_archive(data: ToggleArchiveModel):
    client = await auth.get_client()
    if not client or not await auth.is_authorized():
        raise HTTPException(status_code=401, detail="Oturum açılmamış.")
    try:
        from telethon.tl.functions.folders import EditPeerFoldersRequest
        from telethon.tl.types import InputFolderPeer
        entity = await client.get_entity(data.channel_id)
        
        folder_id = 1 if data.archive else 0
        await client(EditPeerFoldersRequest(folder_peers=[
            InputFolderPeer(peer=entity, folder_id=folder_id)
        ]))
        return {"status": "success", "message": "Arşiv durumu güncellendi."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/toggle_mute")
async def toggle_mute(data: ToggleMuteModel):
    client = await auth.get_client()
    if not client or not await auth.is_authorized():
        raise HTTPException(status_code=401, detail="Oturum açılmamış.")
    try:
        from telethon.tl.functions.account import UpdateNotifySettingsRequest
        from telethon.tl.types import InputNotifyPeer, InputPeerNotifySettings
        entity = await client.get_entity(data.channel_id)
        
        mute_until = 365 * 24 * 60 * 60 if data.mute else 0
        await client(UpdateNotifySettingsRequest(
            peer=InputNotifyPeer(peer=entity),
            settings=InputPeerNotifySettings(mute_until=mute_until)
        ))
        return {"status": "success", "message": "Sessize alma durumu güncellendi."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/media")
async def get_media(channel_id: int, category: str, show_messages: bool = True):
    try:
        items, top_tags = await media.fetch_media(channel_id, category, show_messages)
        return {"media": items, "top_tags": top_tags}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/global_search")
async def global_search(q: str):
    try:
        results, top_tags = await media.fetch_global_search(q)
        return {"results": results, "top_tags": top_tags}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/send_message")
async def send_message(data: SendMessageModel):
    client = await auth.get_client()
    if not client or not await auth.is_authorized():
        raise HTTPException(status_code=401, detail="Oturum açılmamış.")
    try:
        entity = await client.get_entity(data.channel_id)
        await client.send_message(entity, data.message_text)
        return {"status": "success", "message": "Mesaj başarıyla gönderildi."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/search_pdf_text")
async def search_pdf_text(channel_id: int, message_id: int, query: str):
    client = await auth.get_client()
    if not client or not await auth.is_authorized():
        raise HTTPException(status_code=401, detail="Oturum açılmamış.")
    try:
        entity = await client.get_entity(channel_id)
        message = await client.get_messages(entity, ids=message_id)
        
        if not message or not message.file or message.file.ext.lower() != '.pdf':
            raise HTTPException(status_code=400, detail="Dosya PDF formatında değil.")
            
        buffer = io.BytesIO()
        await client.download_media(message, file=buffer)
        buffer.seek(0)
        
        reader = PdfReader(buffer)
        matches = []
        
        query_clean = query.lower()
        for idx, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if query_clean in text.lower():
                lines = text.split("\n")
                snippet = ""
                for line in lines:
                    if query_clean in line.lower():
                        snippet = line.strip()
                        break
                matches.append({
                    "page": idx + 1,
                    "snippet": snippet or f"Sayfa {idx + 1} içerisinde eşleşme bulundu."
                })
                
        return {"matches": matches}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download")
async def trigger_download(data: DownloadModel):
    client = await auth.get_client()
    if not client or not await auth.is_authorized():
        raise HTTPException(status_code=401, detail="Oturum açılmamış.")
        
    key = download_manager.add_download(data.channel_id, data.message_id, data.filename, data.target_folder)
    return {"status": "success", "key": key}

@app.post("/api/download_batch")
async def trigger_batch_download(data: BatchDownloadModel):
    client = await auth.get_client()
    if not client or not await auth.is_authorized():
        raise HTTPException(status_code=401, detail="Oturum açılmamış.")
        
    keys = []
    for dl in data.downloads:
        key = download_manager.add_download(data.channel_id, dl['message_id'], dl['filename'], data.target_folder)
        keys.append(key)
        
    return {"status": "success", "count": len(data.downloads), "keys": keys}

@app.post("/api/cancel_download")
async def cancel_download(data: CancelDownloadModel):
    success = download_manager.cancel_download(data.task_id)
    if success:
        return {"status": "success"}
    return {"status": "failed", "message": "İndirme iptal edilemedi veya zaten tamamlanmış."}

@app.post("/api/clear_completed")
async def clear_completed():
    download_manager.clear_completed()
    return {"status": "success"}

@app.get("/api/stream_preview")
async def stream_preview(channel_id: int, message_id: int):
    client = await auth.get_client()
    if not client or not await auth.is_authorized():
        raise HTTPException(status_code=401, detail="Oturum açılmamış.")
    try:
        entity = await client.get_entity(channel_id)
        message = await client.get_messages(entity, ids=message_id)
        
        if not message or not message.media:
            raise HTTPException(status_code=404, detail="Medya bulunamadı.")
            
        mime = "application/octet-stream"
        if message.file:
            mime = message.file.mime_type or "application/octet-stream"
            
        buffer = io.BytesIO()
        await client.download_media(message, file=buffer)
        buffer.seek(0)
        
        return StreamingResponse(buffer, media_type=mime)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pdf_page_count")
async def get_pdf_page_count(channel_id: int, message_id: int):
    cache_key = f"{channel_id}_{message_id}"
    cache = config.load_pdf_pages_cache()
    if cache_key in cache:
        return {"page_count": cache[cache_key]}
        
    client = await auth.get_client()
    if not client or not await auth.is_authorized():
        raise HTTPException(status_code=401, detail="Oturum açılmamış.")
        
    try:
        entity = await client.get_entity(channel_id)
        message = await client.get_messages(entity, ids=message_id)
        
        if not message or not message.file or message.file.ext.lower() != '.pdf':
            raise HTTPException(status_code=400, detail="Dosya PDF değil.")
            
        buffer = io.BytesIO()
        await client.download_media(message, file=buffer)
        buffer.seek(0)
        
        reader = PdfReader(buffer)
        page_count = len(reader.pages)
        
        cache[cache_key] = page_count
        config.save_pdf_pages_cache(cache)
        
        return {"page_count": page_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/downloads")
async def get_download_status():
    return {"downloads": download_manager.get_all()}

@app.post("/api/open_folder")
async def open_folder(folder_name: str):
    try:
        downloads_base = os.path.join(config.ROOT_DIR, "indirilenler")
        if folder_name == "YDS":
            folder = os.path.join(downloads_base, "YDS Çıkmışları")
        elif folder_name == "YÖKDİL":
            folder = os.path.join(downloads_base, "Yökdil Çıkmışları")
        else:
            folder = os.path.join(downloads_base, folder_name)
            
        if not os.path.exists(folder):
            os.makedirs(folder)
            
        os.startfile(folder)
        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download_zip")
async def download_zip(data: ZipDownloadModel):
    client = await auth.get_client()
    if not client or not await auth.is_authorized():
        raise HTTPException(status_code=401, detail="Oturum açılmamış.")
        
    try:
        import zipfile
        zip_buffer = io.BytesIO()
        
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            for dl in data.downloads:
                msg_id = dl["message_id"]
                filename = dl["filename"]
                ch_id = dl.get("channel_id") or data.channel_id
                if not ch_id:
                    continue
                
                entity = await client.get_entity(ch_id)
                message = await client.get_messages(entity, ids=msg_id)
                if message and message.media:
                    file_buffer = io.BytesIO()
                    await client.download_media(message, file=file_buffer)
                    file_buffer.seek(0)
                    zip_file.writestr(filename, file_buffer.read())
                    
        zip_buffer.seek(0)
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=telegram_downloads.zip"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ZIP oluşturulurken hata: {e}")

@app.get("/api/folders")
async def get_folders():
    return {"folders": config.load_folders()}

@app.post("/api/folders")
async def add_folder(folder: FolderModel):
    folders = config.load_folders()
    name = folder.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Klasör adı boş olamaz.")
    if name in folders:
        return {"status": "success", "folders": folders}
    folders.append(name)
    config.save_folders(folders)
    return {"status": "success", "folders": folders}

@app.delete("/api/folders")
async def delete_folder(name: str):
    folders = config.load_folders()
    if name in folders:
        folders.remove(name)
        config.save_folders(folders)
    return {"status": "success", "folders": folders}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server:app", host="127.0.0.1", port=8000, reload=True)
