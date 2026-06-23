import os
import sys
import uvicorn
import webbrowser
import threading
import time

def open_browser():
    # Wait a moment for the server to start
    time.sleep(1.5)
    webbrowser.open("http://127.0.0.1:8000")

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Add script directory to system path
    if script_dir not in sys.path:
        sys.path.append(script_dir)
        
    print("==================================================")
    print("  TELEGRAM WEB MEDYA VE SINAV SORUSU İNDİRİCİ     ")
    print("==================================================")
    print("Sunucu başlatılıyor... Lütfen tarayıcınızdan:")
    print("--> http://127.0.0.1:8000")
    print("adresini ziyaret edin.")
    print("==================================================")
    
    # Start thread to open the browser automatically
    threading.Thread(target=open_browser, daemon=True).start()
    
    # Start uvicorn with reload enabled pointing to the app inside the 'src' directory
    uvicorn.run("src.server:app", host="127.0.0.1", port=8000, reload=True, reload_dirs=[os.path.join(script_dir, "src")])

if __name__ == "__main__":
    main()

