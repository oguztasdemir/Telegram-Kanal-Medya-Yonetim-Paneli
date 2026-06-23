import os
import asyncio
import uuid
import src.auth as auth
from src.config import ROOT_DIR

class DownloadQueueManager:
    def __init__(self):
        self.downloads = {}  # task_id -> dict
        self.queue = asyncio.Queue()
        self.sem = asyncio.Semaphore(2)  # max 2 concurrent downloads
        self._workers = []

    def start(self):
        if not self._workers:
            for _ in range(2):
                w = asyncio.create_task(self._worker_loop())
                self._workers.append(w)

    async def stop(self):
        for w in self._workers:
            w.cancel()
        self._workers.clear()

    async def _worker_loop(self):
        while True:
            try:
                task_id = await self.queue.get()
                if task_id not in self.downloads:
                    self.queue.task_done()
                    continue
                
                dl = self.downloads[task_id]
                if dl["status"] == "cancelled":
                    self.queue.task_done()
                    continue
                
                # Wait for semaphore to restrict concurrency to 2
                async with self.sem:
                    if dl["status"] == "cancelled":
                        self.queue.task_done()
                        continue
                    dl["status"] = "downloading"
                    try:
                        # Capture task reference to support cancellation
                        download_task = asyncio.create_task(self._perform_download(task_id, dl))
                        dl["_task_ref"] = download_task
                        await download_task
                    except asyncio.CancelledError:
                        dl["status"] = "cancelled"
                    except Exception as e:
                        dl["status"] = "failed"
                        dl["error"] = str(e)
                    finally:
                        if "_task_ref" in dl:
                            del dl["_task_ref"]
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Queue worker error: {e}")
                await asyncio.sleep(1)

    async def _perform_download(self, task_id, dl):
        client = await auth.get_client()
        if not client:
            raise Exception("Telegram client is not connected.")
            
        try:
            target_folder = dl["target_folder"]
            downloads_base = os.path.join(ROOT_DIR, "indirilenler")
            if target_folder == "YDS":
                folder = os.path.join(downloads_base, "YDS Çıkmışları")
            elif target_folder == "YÖKDİL":
                folder = os.path.join(downloads_base, "Yökdil Çıkmışları")
            else:
                folder = os.path.join(downloads_base, target_folder)
                
            if not os.path.exists(folder):
                os.makedirs(folder)
                
            filename = dl["filename"]
            base, ext = os.path.splitext(filename)
            counter = 1
            target_path = os.path.join(folder, filename)
            while os.path.exists(target_path):
                filename = f"{base}_{counter}{ext}"
                target_path = os.path.join(folder, filename)
                counter += 1
            dl["filename"] = filename
            
            entity = await client.get_entity(dl["channel_id"])
            message = await client.get_messages(entity, ids=dl["message_id"])
            
            def progress_callback(current, total):
                if total > 0:
                    dl["progress"] = round(current / total, 2)
                    dl["status"] = "downloading"
                    
            await client.download_media(message, file=target_path, progress_callback=progress_callback)
            dl["progress"] = 1.0
            dl["status"] = f"completed ({os.path.basename(folder)})"
        except asyncio.CancelledError:
            dl["status"] = "cancelled"
            if 'target_path' in locals() and os.path.exists(target_path):
                try:
                    os.remove(target_path)
                except Exception:
                    pass
            raise
        except Exception as e:
            dl["progress"] = 0.0
            dl["status"] = "failed"
            dl["error"] = str(e)
            if 'target_path' in locals() and os.path.exists(target_path):
                try:
                    os.remove(target_path)
                except Exception:
                    pass
            raise e

    def add_download(self, channel_id, message_id, filename, target_folder):
        # Check if already in downloads
        for existing_id, val in list(self.downloads.items()):
            if val["channel_id"] == channel_id and val["message_id"] == message_id:
                if val["status"] in ["completed", "failed", "cancelled"] or val["status"].startswith("completed"):
                    val["status"] = "waiting"
                    val["progress"] = 0.0
                    val["error"] = None
                    val["target_folder"] = target_folder
                    val["filename"] = filename
                    self.queue.put_nowait(existing_id)
                    return existing_id
                else:
                    return existing_id

        task_id = str(uuid.uuid4())
        self.downloads[task_id] = {
            "id": task_id,
            "channel_id": channel_id,
            "message_id": message_id,
            "filename": filename,
            "target_folder": target_folder,
            "progress": 0.0,
            "status": "waiting",
            "error": None
        }
        self.queue.put_nowait(task_id)
        return task_id

    def cancel_download(self, task_id):
        if task_id in self.downloads:
            dl = self.downloads[task_id]
            if dl["status"] in ["waiting", "downloading"]:
                dl["status"] = "cancelled"
                if "_task_ref" in dl and dl["_task_ref"]:
                    dl["_task_ref"].cancel()
                return True
        return False

    def clear_completed(self):
        for task_id in list(self.downloads.keys()):
            if self.downloads[task_id]["status"] in ["completed", "failed", "cancelled"] or self.downloads[task_id]["status"].startswith("completed"):
                del self.downloads[task_id]

    def get_all(self):
        res = {}
        for k, v in self.downloads.items():
            res[k] = {ik: iv for ik, iv in v.items() if ik != "_task_ref"}
        return res

download_manager = DownloadQueueManager()
