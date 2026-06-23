import re
import os
from src.config import load_pdf_pages_cache, save_pdf_pages_cache
import src.auth as auth

media_cache = {}  # channel_id -> {"max_id": int, "items": [dict, ...]}
sender_names_cache = {}  # sender_id -> sender_name

def clear_caches():
    media_cache.clear()
    sender_names_cache.clear()

def classify_text_nlp(text):
    if not text:
        return []
    text_lower = text.lower()
    scores = {"Sağlık": 0, "Fen": 0, "Sosyal": 0}
    
    health_words = [
        "sağlık", "saglik", "tıp", "tip", "hekim", "doktor", "hasta", "hastalık", "kanser", "tedavi", "ilaç", "ilac",
        "hücre", "hucre", "virüs", "virus", "bakteri", "klinik", "teşhis", "genetik", "biyoloji", "biyolojik",
        "hastane", "salgın", "salgin", "diyet", "obezite", "gıda", "gida", "beslenme", "kalp", "akciğer", "akciger",
        "beyin", "sinir", "kas", "kemik", "kan", "hormon", "cerrahi", "ameliyat", "eczacılık", "eczacilik",
        "health", "medical", "medicine", "doctor", "patient", "disease", "illness", "cancer", "treatment",
        "drug", "cell", "virus", "bacteria", "clinical", "diagnosis", "genetic", "biology", "hospital",
        "epidemic", "obesity", "nutrition", "diet", "heart", "brain", "lung", "blood", "surgery"
    ]
    
    science_words = [
        "fen", "fizik", "kimya", "matematik", "astronomi", "mühendislik", "muhendislik", "teknoloji", "yazılım",
        "yazilim", "yapay zeka", "enerji", "elektrik", "atom", "molekül", "molekul", "gezegen", "yıldız", "yildiz",
        "uzay", "galaksi", "robot", "veri", "data", "bilgisayar", "internet", "mıknatıs", "miknatis", "yerçekimi",
        "yercelimi", "ışık", "isik", "ses", "dalga", "laboratuvar", "formül", "formul", "deney", "arşivi", "arsivi",
        "science", "physics", "chemistry", "mathematics", "astronomy", "engineering", "technology", "software",
        "artificial intelligence", "energy", "electricity", "atom", "molecule", "planet", "star", "space",
        "galaxy", "robot", "computer", "gravity", "light", "wave", "laboratory", "experiment"
    ]
    
    social_words = [
        "sosyal", "tarih", "coğrafya", "cografya", "felsefe", "sosyoloji", "psikoloji", "politika", "siyaset",
        "hukum", "hukuk", "yasa", "kanun", "ekonomi", "iktisat", "finans", "para", "enflasyon", "ticaret", "sanat",
        "edebiyat", "roman", "şiir", "siir", "arkeoloji", "kültür", "kultur", "dilbilim", "medeniyet", "imparatorluk",
        "savaş", "savas", "barış", "baris", "sosyal bilimler", "psikolojik", "tarihi", "antropoloji", "demokrasi",
        "history", "geography", "philosophy", "sociology", "psychology", "politics", "law", "economy",
        "finance", "money", "inflation", "trade", "art", "literature", "novel", "poetry", "archaeology",
        "culture", "linguistics", "civilization", "empire", "war", "peace", "democracy"
    ]
    
    for word in health_words:
        if word in text_lower:
            scores["Sağlık"] += 2 if len(word) > 4 else 1
            
    for word in science_words:
        if word in text_lower:
            scores["Fen"] += 2 if len(word) > 4 else 1
            
    for word in social_words:
        if word in text_lower:
            scores["Sosyal"] += 2 if len(word) > 4 else 1
            
    detected_tags = []
    max_score = max(scores.values())
    if max_score > 0:
        for cat, score in scores.items():
            if score == max_score or (score >= 3 and score >= max_score * 0.7):
                detected_tags.append(cat)
                
    return detected_tags

def turkish_lower(s):
    if not s:
        return ""
    mapping = {
        'İ': 'i',
        'I': 'ı',
        'Ş': 'ş',
        'Ç': 'ç',
        'Ğ': 'ğ',
        'Ö': 'ö',
        'Ü': 'ü'
    }
    for u, l in mapping.items():
        s = s.replace(u, l)
    return s.lower()

def extract_dynamic_tags(items, top_n=24):
    if not items:
        return [], []

    from collections import Counter
    import re

    stopwords = {
        "ve", "veya", "ile", "bir", "icin", "için", "de", "da", "bu", "su", "şu", "o", "ki", "en", "ama", "fakat", 
        "lakin", "ancak", "ise", "gibi", "hem", "hep", "her", "hic", "hiç", "ya", "mi", "mı", "mu", "mü", "olan", 
        "olarak", "olanlar", "tarafından", "tarafindan", "uzere", "üzere", "veyahut", "zira", "cunku", "çünkü",
        "kadar", "belki", "daha", "cok", "çok", "bazi", "bazı", "göre", "gore", "yok", "var", "sonra", "once", "önce",
        "the", "a", "an", "and", "or", "but", "if", "because", "as", "what", "which", "who", "this", "that", "these", 
        "those", "then", "so", "than", "to", "of", "in", "for", "on", "with", "at", "by", "from", "up", "about", 
        "into", "over", "after", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
        "https", "http", "com", "www", "html", "net", "org", "php", "aspx", "videosunu", "dosya", "dosyası", "dosyasi",
        "indir", "indirmek", "tikla", "tıkla", "tıklayın", "tıklayınız", "paylasilan", "paylaşılan", "grup", "kanal",
        "mesaj", "sohbet", "aktif", "yeni", "tüm", "tum", "herkese", "merhaba", "lütfen", "lutfen", "bilgi", "giriş",
        "giris", "soru", "soruları", "sorulari", "çıkmış", "cikmis", "yılı", "yili", "günü", "gunu", "saat", "saati",
        "son", "ilk", "gün", "gun", "hafta", "ay", "yıl", "yil", "cevap", "cevabı", "cevabi", "adlı", "adli", "tarih",
        "tarihli", "tarihi", "sayısı", "sayisi", "sayi", "sayı", "konu", "konusu", "konuları", "konulari",
        "ydstime", "yökdiltime", "ydsacademy", "yds_yokdil_yks", "yds_yokdil_yksdil", "telegram",
        "pdf", "doc", "docx", "xls", "xlsx", "zip", "rar", "mp3", "mp4", "wav", "avi", "mov",
        "izleyelim", "izleyin", "izleyiniz", "izle", "izleme", "izlemek", "izledik", "izledim", "izleyen",
        "çözüm", "cozum", "çözümü", "cozumu", "çözümlü", "cozumlu", "çözümler", "cozumler", "çözmek", "cozmek",
        "sorumuz", "sorusu", "soruları", "sorular", "sorunun", "soruya", "soruda", "sorudan",
        "sayfa", "sayfası", "sayfasi", "sayfalar", "sayfalari",
        "video", "videosu", "videolar",
        "hocam", "hocamız", "arkadaşlar", "arkadaslar", "selam",
        "paylaşım", "paylasim", "paylaşıldı", "paylasildi",
        "güncel", "guncel", "güncellendi", "guncellendi",
        "deneme", "test", "denemesi", "denemeleri", "testi", "testleri"
    }

    word_counts = Counter()
    original_casings = {}

    for item in items:
        text = ""
        if item.get("name"):
            text += item["name"] + " "
        if item.get("text"):
            text += item["text"] + " "
        
        words = re.findall(r'[A-Za-zÇçĞğİıÖöŞşÜü]{3,}', text)
        for w in words:
            w_lower = turkish_lower(w)
            if w_lower in stopwords:
                continue
            
            # Skip words ending with common Turkish grammatical suffixes (verbs, plurals, possessives, cases)
            if len(w_lower) > 4:
                if w_lower.endswith((
                    "elim", "alim", "umuz", "ümüz", "umuzun", "ümüzün", "ımızın", "imizin", 
                    "iniz", "ınız", "lar", "ler", "dan", "den", "tan", "ten", "nın", "nin", 
                    "nun", "nün", "dır", "dir", "dur", "dür", "tır", "tir", "tur", "tür", 
                    "yla", "yle", "ıyla", "iyle", "acak", "ecek", "iyor", "uyor", "üyor", 
                    "unu", "ünü", "ını", "ini", "sun", "sün", "sin", "sın", "cık", "cik"
                )):
                    continue
            
            word_counts[w_lower] += 1
            if w_lower not in original_casings:
                original_casings[w_lower] = w
            else:
                existing = original_casings[w_lower]
                if w.isupper() and not existing.isupper():
                    original_casings[w_lower] = w
                elif w.istitle() and not existing.isupper() and not existing.istitle():
                    original_casings[w_lower] = w

    top_entries = word_counts.most_common(top_n * 2)
    
    extracted_tags = []
    for w_lower, count in top_entries:
        tag_display = original_casings.get(w_lower, w_lower).upper()
        if tag_display not in extracted_tags:
            extracted_tags.append(tag_display)
        if len(extracted_tags) >= top_n:
            break

    # Sort alphabetically
    top_tags = sorted(extracted_tags, key=lambda s: turkish_lower(s))

    for item in items:
        item_tags = []
        text_lower = ""
        if item.get("name"):
            text_lower += turkish_lower(item["name"]) + " "
        if item.get("text"):
            text_lower += turkish_lower(item["text"]) + " "
        if item.get("ext"):
            ext_tag = turkish_lower(item["ext"].replace(".", ""))
            text_lower += ext_tag + " "

        for tag in top_tags:
            tag_lower = turkish_lower(tag)
            if item.get("ext") and turkish_lower(item["ext"].replace(".", "")).upper() == tag:
                if tag not in item_tags:
                    item_tags.append(tag)
            else:
                if re.search(r'\b' + re.escape(tag_lower) + r'\b', text_lower):
                    if tag not in item_tags:
                        item_tags.append(tag)
                        
        item["tags"] = item_tags

    return top_tags, items

async def fetch_media(channel_id, category, show_messages=True):
    global media_cache, sender_names_cache
    client = await auth.get_client()
    if not client or not await auth.is_authorized():
        return [], []
        
    entity = await client.get_entity(channel_id)
    
    if channel_id not in media_cache:
        media_cache[channel_id] = {"max_id": 0, "items": []}
        
    cache_entry = media_cache[channel_id]
    last_max_id = cache_entry["max_id"]
    cached_items = cache_entry["items"]
    
    new_items = []
    highest_id = last_max_id
    
    iter_kwargs = {"limit": 3000}
    if last_max_id > 0:
        iter_kwargs["min_id"] = last_max_id
        
    async for message in client.iter_messages(entity, **iter_kwargs):
        if message.id > highest_id:
            highest_id = message.id
            
        filename = None
        size = 0
        ext = ""
        media_type = "Metin"
        
        text_content = message.text or ""
        has_link = False
        links_extracted = []
        
        urls = re.findall(r'(https?://[^\s]+)', text_content)
        if urls:
            has_link = True
            links_extracted = urls

        if message.file:
            filename = message.file.name
            size = message.file.size or 0
            ext = message.file.ext or ""
            
            if not filename:
                filename = f"dosya_{message.id}{ext}"
            
            mime = message.file.mime_type or ""
            if "audio" in mime or "ogg" in mime or ext in [".mp3", ".wav", ".ogg", ".m4a"]:
                media_type = "Ses"
            elif "image" in mime or ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                media_type = "Görsel"
            else:
                media_type = "Belge"
        elif has_link:
            media_type = "Link"
        
        sender_name = "Sohbet"
        sender_id = message.sender_id
        if sender_id:
            if sender_id in sender_names_cache:
                sender_name = sender_names_cache[sender_id]
            else:
                try:
                    sender = await message.get_sender()
                    if sender:
                        sender_name = getattr(sender, "first_name", "") or getattr(sender, "last_name", "") or getattr(sender, "title", "") or "Sohbet"
                        sender_name = sender_name.strip() or "Sohbet"
                except Exception:
                    pass
                sender_names_cache[sender_id] = sender_name
        
        tags = []
        combined_text = (filename or "") + " " + text_content
        combined_text_lower = turkish_lower(combined_text)
        
        detected_categories = classify_text_nlp(combined_text)
        tags.extend(detected_categories)
        
        if "yokdil" in combined_text_lower or "yökdil" in combined_text_lower:
            tags.append("YÖKDİL")
        if "yds" in combined_text_lower:
            tags.append("YDS")
        if ext:
            ext_tag = ext.replace(".", "").upper()
            if ext_tag and ext_tag not in tags:
                tags.append(ext_tag)
            
        new_items.append({
            "id": message.id,
            "text": text_content,
            "name": filename,
            "size": size,
            "ext": ext,
            "type": media_type,
            "sender": sender_name,
            "date": message.date.strftime("%d.%m.%Y %H:%M"),
            "timestamp": message.date.timestamp(),
            "links": links_extracted,
            "tags": tags
        })
        
    if new_items:
        cached_items.extend(new_items)
        cached_items.sort(key=lambda x: x["timestamp"])
        cache_entry["max_id"] = highest_id
        cache_entry["items"] = cached_items
        
    items = []
    for item in cached_items:
        media_type = item["type"]
        has_link = len(item["links"]) > 0
        
        if not show_messages and media_type == "Metin":
            continue
            
        if category == "all":
            pass
        elif category == "link":
            if not has_link:
                continue
        else:
            if category == "document" and media_type != "Belge":
                continue
            if category == "photo" and media_type != "Görsel":
                continue
            if category == "audio" and media_type != "Ses":
                continue
        
        items.append(item)
        
    top_tags, items = extract_dynamic_tags(items)
    return items, top_tags

async def fetch_global_search(q):
    global sender_names_cache
    client = await auth.get_client()
    if not client or not await auth.is_authorized():
        return [], []
    if not q:
        return [], []
        
    results = []
    async for message in client.iter_messages(None, search=q, limit=100):
        chat_title = "Bilinmeyen Sohbet"
        chat_id = message.chat_id
        try:
            chat = await message.get_chat()
            if chat:
                chat_title = getattr(chat, "title", "") or getattr(chat, "first_name", "") or "Bilinmeyen Sohbet"
        except Exception:
            pass
            
        filename = None
        size = 0
        ext = ""
        media_type = "Metin"
        
        text_content = message.text or ""
        has_link = False
        links_extracted = []
        
        urls = re.findall(r'(https?://[^\s]+)', text_content)
        if urls:
            has_link = True
            links_extracted = urls

        if message.file:
            filename = message.file.name
            size = message.file.size or 0
            ext = message.file.ext or ""
            if not filename:
                filename = f"dosya_{message.id}{ext}"
            
            mime = message.file.mime_type or ""
            if "audio" in mime or "ogg" in mime or ext in [".mp3", ".wav", ".ogg", ".m4a"]:
                media_type = "Ses"
            elif "image" in mime or ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
                media_type = "Görsel"
            else:
                media_type = "Belge"
        elif has_link:
            media_type = "Link"
            
        sender_name = "Sohbet"
        sender_id = message.sender_id
        if sender_id:
            if sender_id in sender_names_cache:
                sender_name = sender_names_cache[sender_id]
            else:
                try:
                    sender = await message.get_sender()
                    if sender:
                        sender_name = getattr(sender, "first_name", "") or getattr(sender, "last_name", "") or getattr(sender, "title", "") or "Sohbet"
                        sender_name = sender_name.strip() or "Sohbet"
                except Exception:
                    pass
                sender_names_cache[sender_id] = sender_name
        
        tags = []
        combined_text = (filename or "") + " " + text_content
        combined_text_lower = turkish_lower(combined_text)
        
        detected_categories = classify_text_nlp(combined_text)
        tags.extend(detected_categories)
        
        if "yokdil" in combined_text_lower or "yökdil" in combined_text_lower:
            tags.append("YÖKDİL")
        if "yds" in combined_text_lower:
            tags.append("YDS")
        if ext:
            ext_tag = ext.replace(".", "").upper()
            if ext_tag and ext_tag not in tags:
                tags.append(ext_tag)
            
        results.append({
            "id": message.id,
            "chat_id": chat_id,
            "chat_name": chat_title,
            "text": text_content,
            "name": filename,
            "size": size,
            "ext": ext,
            "type": media_type,
            "sender": sender_name,
            "date": message.date.strftime("%d.%m.%Y %H:%M"),
            "timestamp": message.date.timestamp(),
            "links": links_extracted,
            "tags": tags
        })
        
    top_tags, results = extract_dynamic_tags(results)
    return results, top_tags
