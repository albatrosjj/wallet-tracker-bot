╔════════════════════════════════════════╗
║   🤖 WALLET TRACKER BOT               ║
║   20 cüzdan · ETH · BSC · Telegram   ║
╚════════════════════════════════════════╝

20 cüzdanı Ethereum ve BSC üzerinde takip eden,
alım-satım analizi yapıp Telegram'a bildirim gönderen bot.
Her 30 dk'da GitHub Actions'da ücretsiz çalışır.

## 🏗️ Mimari

```
wallet-tracker-bot/
├── .github/workflows/scan.yml   # GitHub Actions (30 dk'da bir çalışır)
├── config/wallets.json           # Cüzdan listesi + ayarlar
├── src/
│   ├── chains/evm.py             # EVM zincir bağlantısı (Eth + BSC)
│   ├── analyzer.py               # P&L, skor, sinyal
│   └── notifier.py               # Telegram bildirim
├── data/state.json               # Kalıcı state (otomatik güncellenir)
├── main.py                       # Ana tarama betiği
└── requirements.txt
```

## 🚀 Kurulum

### 1. GitHub'a yükle

```bash
# Repo oluştur
gh repo create wallet-tracker-bot --public --source=. --push
```

### 2. Telegram Chat ID'ni al

1. @BotFather'da bot'u oluştur (yaptın bile ✅)
2. Bot'a herhangi bir mesaj at
3. Şu URL'e git: `https://api.telegram.org/bot8688597779:AAHFe6CgGzWtL8zaLSCu1ozUtJXpdl58JY8/getUpdates`
4. Gelen JSON'daki `chat.id` değerini al

### 3. Cüzdan adreslerini ekle

`config/wallets.json` dosyasını düzenle — **tek liste**, hangi ağda işlem yaparlarsa yapsınlar bot her cüzdanı hem ETH hem BSC'de tarar:

```json
{
  "wallets": [
    "0xabc...",
    "0xdef...",
    "0x123..."
  ]
}
```

### 4. Chat ID'yi config'e yaz

Aynı dosyada `chat_id` alanını güncelle.

### 5. Pushla, çalışsın

```bash
git add .
git commit -m "initial setup"
git push
```

Actions sekmesinden manuel de tetikleyebilirsin.

## 📊 Sinyaller

| Sinyal | Skor | Anlamı |
|--------|------|--------|
| 🚨 STRONG_BUY | ≥0.7 | Yüksek aktivite, takip et |
| 🟢 BUY | ≥0.5 | Pozitif hareket |
| ⚪ HOLD | ≥0.3 | Nötr, izle |
| ⚫ SKIP | <0.3 | Düşük aktivite |

## ⚠️ Notlar

- **Ücretsiz RPC** kullanır (`eth.drpc.org`, `bsc.drpc.org`) — rate limit gelebilir
- GitHub Actions ayda 2000 dk ücretsiz — 30dk'da bir çalıştırmak ~1440 dk/ay
- Cüzdan eklemek için sadece config'deki JSON'u güncelle, pushla — otomatik devreye alır

## 🤖 Telegram Komutları

Bot'a aşağıdaki komutları yazabilirsin:

| Komut | Açıklama |
|-------|----------|
| `/add 0x...` | Cüzdan ekle |
| `/remove 0x...` veya `/sil 0x...` | Cüzdan sil |
| `/list` | Tüm cüzdanları listele |
| `/status` | Bot durumunu göster |
| `/help` | Yardım menüsü |

Komutlar her 30 dk'da bir scan sırasında işlenir. Anında değil, bir sonraki scan'de uygulanır.
