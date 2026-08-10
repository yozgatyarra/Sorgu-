#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
em1rhxnquery | Arastir.vip Telegram Bot
Sends professional TXT reports for every query.
Single-file production artifact.
"""

import os, sys, json, time, io
from datetime import datetime
from typing import Dict, Any
import requests
import logging
from logging.handlers import RotatingFileHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters

# ═══════════════════════════════════════════════════════════════════════════════
# CREDENTIALS — BOT TOKENİNİZİ BURAYA YAPIŞTIRIN
# ═══════════════════════════════════════════════════════════════════════════════
BOT_TOKEN = "8452524196:AAE077HzD7_g7dluOcOjvXvySF2P-_9JbBI"  # <-- TOKENİNİZİ BURAYA YAPIŞTIRIN
BASE_URL = "http://arastir.vip/api"
SIGNATURE = "em1rhxnquery"
VERSION = "v3.0-telegram"

ENDPOINT_MAP = {
    "1": {"name": "Kimlik Sorgu",      "ep": "tc",      "params": ["tc"],          "desc": "TC numarası ile kimlik bilgisi"},
    "2": {"name": "Ad Soyad Sorgu",    "ep": "adsoyad", "params": ["ad", "soyad"], "desc": "Ad ve soyad ile arama"},
    "3": {"name": "Aile Sorgu",        "ep": "aile",    "params": ["tc"],          "desc": "TC ile aile bilgisi"},
    "4": {"name": "Soy Ağacı Sorgu",   "ep": "sulale",  "params": ["tc"],          "desc": "TC ile soy ağacı"},
    "5": {"name": "Çocuk Sorgu",       "ep": "cocuk",   "params": ["tc"],          "desc": "TC ile çocuk bilgisi"},
    "6": {"name": "Adres Sorgu",       "ep": "adres",   "params": ["tc"],          "desc": "TC ile adres bilgisi"},
    "7": {"name": "GSM → TC Sorgu",    "ep": "gsmtc",   "params": ["gsm"],         "desc": "GSM numarası ile TC"},
    "8": {"name": "TC → GSM Sorgu",    "ep": "tcgsm",   "params": ["tc"],          "desc": "TC ile GSM numarası"},
    "9": {"name": "İşyeri Sorgu",      "ep": "isyeri",  "params": ["tc"],          "desc": "TC ile işyeri bilgisi"},
}

USER_STATE: Dict[int, Dict[str, Any]] = {}

logger = logging.getLogger(SIGNATURE)
logger.setLevel(logging.DEBUG)
fmt = logging.Formatter(f"%(asctime)s | {SIGNATURE} | %(levelname)-8s | %(message)s", datefmt="%H:%M:%S")
fh = RotatingFileHandler(f"{SIGNATURE}_bot.log", maxBytes=5_242_880, backupCount=3, encoding="utf-8")
fh.setFormatter(fmt)
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(fmt)
logger.addHandler(fh)
logger.addHandler(ch)

# ═══════════════════════════════════════════════════════════════════════════════
# CORE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def query_api(key: str, params: Dict[str, str], timeout: float = 30.0, retries: int = 3, delay: float = 2.0) -> Dict[str, Any]:
    meta = ENDPOINT_MAP[key]
    url = f"{BASE_URL}/{meta['ep']}.php"
    t0 = time.time()
    last_err = None
    resp = None
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/json,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9"
    })
    
    for a in range(1, retries + 1):
        try:
            resp = session.get(url, params=params, timeout=timeout, allow_redirects=True)
            break
        except requests.exceptions.Timeout:
            last_err = f"Timeout (deneme {a}/{retries})"
            if a < retries: time.sleep(delay * a)
        except requests.exceptions.ConnectionError as e:
            last_err = f"Bağlantı hatası: {str(e)[:60]}"
            if a < retries: time.sleep(delay)
        except Exception as e:
            last_err = f"Beklenmeyen: {str(e)[:80]}"
            break
    
    rt = (time.time() - t0) * 1000
    
    if resp is None:
        return {
            "name": meta["name"], "ep": meta["ep"], "params": params,
            "status": 0, "ctype": "none", "raw": "", "parsed": None,
            "err": last_err or "Tüm denemeler başarısız", "rt_ms": rt,
            "ts": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        }
    
    ct = resp.headers.get("Content-Type", "unknown")
    raw = resp.text
    parsed = None
    try:
        parsed = resp.json()
    except Exception:
        pass
    
    err = None
    if resp.status_code != 200:
        err = f"HTTP {resp.status_code}"
    elif not raw.strip():
        err = "Boş yanıt"
    
    return {
        "name": meta["name"], "ep": meta["ep"], "params": params,
        "status": resp.status_code, "ctype": ct, "raw": raw, "parsed": parsed,
        "err": err, "rt_ms": rt,
        "ts": datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    }

def build_txt_report(res: Dict[str, Any]) -> str:
    lines = [
        "=" * 66,
        f"  {SIGNATURE} | PROFESYONEL SORGU RAPORU",
        f"  {VERSION}",
        "=" * 66,
        "",
        f"Sorgu Tipi     : {res['name']}",
        f"Endpoint       : /api/{res['ep']}.php",
        f"Zaman          : {res['ts']}",
        f"Yanıt Süresi   : {res['rt_ms']:.0f} ms",
        f"Parametreler   : {json.dumps(res['params'], ensure_ascii=False)}",
        f"HTTP Status    : {res['status']}",
        f"Content-Type   : {res['ctype']}",
        "",
        "-" * 66,
    ]
    
    if res["err"]:
        lines.extend([
            "HATA BİLGİSİ",
            "-" * 66,
            f"{res['err']}",
            "",
        ])
    
    if res["parsed"] is not None:
        lines.extend([
            "YAPILANDIRILMIŞ VERİ (JSON)",
            "-" * 66,
            json.dumps(res["parsed"], indent=2, ensure_ascii=False),
            "",
        ])
    
    lines.extend([
        "HAM YANIT",
        "-" * 66,
    ])
    
    raw = res["raw"]
    if len(raw) > 5000:
        raw = raw[:5000] + f"\n\n... [{len(res['raw']) - 5000} karakter kırpıldı] ..."
    
    lines.append(raw)
    lines.extend([
        "",
        "-" * 66,
        f"🔧 Geliştirici  : {SIGNATURE}",
        f"🔧 Versiyon     : {VERSION}",
        f"🔧 Rapor ID     : {datetime.now().strftime('%Y%m%d%H%M%S')}",
        "=" * 66,
    ])
    
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════════════════════════════
# TELEGRAM HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    uname = update.effective_user.username or "N/A"
    logger.info(f"START | uid={uid} | @{uname}")
    
    keyboard = []
    row = []
    for k, v in ENDPOINT_MAP.items():
        row.append(InlineKeyboardButton(v["name"], callback_data=f"ep:{k}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    await update.message.reply_text(
        f"👋 <b>Merhaba {update.effective_user.first_name}!</b>\n\n"
        f"🤖 <b>{SIGNATURE} Em1rhxnquery Sorgu Botu</b>\n"
        f"📄 Sonuçlar profesyonel TXT raporu olarak gönderilir.\n\n"
        f"⬇️ Aşağıdan sorgu tipini seçin:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )

async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid in USER_STATE:
        del USER_STATE[uid]
        await update.message.reply_text("✅ Mevcut işlem iptal edildi. /start")
    else:
        await update.message.reply_text("ℹ️ Aktif işlem yok. /start")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    if not data.startswith("ep:"):
        return
    
    key = data.split(":", 1)[1]
    if key not in ENDPOINT_MAP:
        return
    
    meta = ENDPOINT_MAP[key]
    uid = update.effective_user.id
    USER_STATE[uid] = {"key": key}
    
    if len(meta["params"]) == 1:
        param_name = meta["params"][0].upper()
        example = "12345678901" if param_name == "TC" else ("5551234567" if param_name == "GSM" else "değer")
        await query.edit_message_text(
            f"📍 <b>{meta['name']}</b>\n\n"
            f"ℹ️ {meta['desc']}\n\n"
            f"Lütfen <code>{param_name}</code> gönderin:\n"
            f"Örnek: <code>{example}</code>\n\n"
            f"🚫 İptal: /cancel",
            parse_mode="HTML"
        )
    else:
        await query.edit_message_text(
            f"📍 <b>{meta['name']}</b>\n\n"
            f"ℹ️ {meta['desc']}\n\n"
            f"Lütfen parametreleri şu formatta gönderin:\n"
            f"<code>{'|'.join(p.upper() for p in meta['params'])}</code>\n"
            f"Örnek: <code>Ahmet|Yılmaz</code>\n\n"
            f"🚫 İptal: /cancel",
            parse_mode="HTML"
        )

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    
    if uid not in USER_STATE:
        await update.message.reply_text(
            "ℹ️ Sorgu başlatmak için /start yazın.",
            parse_mode="HTML"
        )
        return
    
    state = USER_STATE[uid]
    key = state["key"]
    meta = ENDPOINT_MAP[key]
    
    params: Dict[str, str] = {}
    if len(meta["params"]) == 1:
        params[meta["params"][0]] = text
    else:
        parts = text.split("|")
        if len(parts) != len(meta["params"]):
            await update.message.reply_text(
                f"❌ Hatalı format!\n"
                f"Beklenen: <code>{'|'.join(p.upper() for p in meta['params'])}</code>\n"
                f"Örnek: <code>{'|'.join('Örnek' for _ in meta['params'])}</code>\n\n"
                f"🚫 İptal: /cancel",
                parse_mode="HTML"
            )
            return
        for i, p in enumerate(meta["params"]):
            params[p] = parts[i].strip()
    
    if not all(params.values()):
        await update.message.reply_text("❌ Parametreler boş olamaz. /cancel", parse_mode="HTML")
        return
    
    wait_msg = await update.message.reply_text("⏳ Sorgu gönderiliyor, lütfen bekleyin...")
    
    try:
        res = query_api(key, params)
    except Exception as e:
        logger.error(f"QUERY_EXCEPTION | uid={uid} | err={e}")
        await wait_msg.edit_text(f"❌ Sorgu sırasında hata oluştu:\n<code>{str(e)[:200]}</code>", parse_mode="HTML")
        if uid in USER_STATE: del USER_STATE[uid]
        return
    
    txt_content = build_txt_report(res)
    filename = f"{SIGNATURE}_{meta['ep']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    bio = io.BytesIO(txt_content.encode('utf-8'))
    bio.name = filename
    
    emoji = "✅" if res["status"] == 200 and not res["err"] else "❌"
    
    await wait_msg.delete()
    await update.message.reply_document(
        document=bio,
        caption=(
            f"{emoji} <b>{meta['name']}</b>\n"
            f"⏱️ Süre: <code>{res['rt_ms']:.0f} ms</code>\n"
            f"📡 Status: <code>{res['status']}</code>\n"
            f"{'⚠️ Hata: ' + res['err'] if res['err'] else '✅ Başarılı'}\n\n"
            f"🔧 {SIGNATURE} | {VERSION}"
        ),
        parse_mode="HTML"
    )
    
    logger.info(f"RESULT | uid={uid} | ep={meta['ep']} | status={res['status']} | err={res['err']}")
    
    if uid in USER_STATE:
        del USER_STATE[uid]

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"TELEGRAM_ERROR: {context.error}", exc_info=True)

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE" or not BOT_TOKEN:
        print("\n" + "=" * 60)
        print("❌ BOT TOKEN EKSİK!")
        print("=" * 60)
        print("Kodun en üstündeki BOT_TOKEN değişkenine tokeninizi yapıştırın.")
        print("=" * 60 + "\n")
        sys.exit(1)
    
    logger.info("=" * 60)
    logger.info(f"{SIGNATURE} BOT STARTING")
    logger.info(f"VERSION: {VERSION}")
    logger.info(f"BASE_URL: {BASE_URL}")
    logger.info("=" * 60)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("cancel", cmd_cancel))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(error_handler)
    
    logger.info("Polling started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()