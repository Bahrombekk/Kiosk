#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
#  AVTOBUS — bir buyruqli o'rnatgich (Linux / mini-PC / Raspberry Pi)
#  Ishlatish:   bash setup.sh
#  Docker + Docker Compose talab qilinadi.
# ─────────────────────────────────────────────────────────────
set -euo pipefail
cd "$(dirname "$0")"

say(){ printf '\033[1;36m%s\033[0m\n' "$*"; }
ok(){  printf '\033[1;32m%s\033[0m\n' "$*"; }
err(){ printf '\033[1;31m%s\033[0m\n' "$*" >&2; }

say "════════════════════════════════════════════"
say "   AVTOBUS.UZ — qurilma o'rnatgichi"
say "════════════════════════════════════════════"

# 1) Docker tekshiruvi
if ! command -v docker >/dev/null 2>&1; then
  err "Docker topilmadi. Avval Docker o'rnating: https://docs.docker.com/engine/install/"
  exit 1
fi
if ! docker compose version >/dev/null 2>&1; then
  err "Docker Compose (v2) topilmadi. Docker'ni yangilang."
  exit 1
fi
ok "✓ Docker mavjud"

# 2) Mavjud .env — qayta sozlashni so'raymiz
KEEP_KEY=""
if [ -f .env ]; then
  say "\n.env allaqachon mavjud."
  read -r -p "Qayta sozlaymizmi? (kalit saqlanadi) [h/Y]: " ans
  if [[ "${ans:-Y}" =~ ^[hH] ]]; then
    ok "Mavjud .env saqlanadi. Faqat qayta ishga tushiramiz."
    docker compose up -d --build
    exit 0
  fi
  KEEP_KEY="$(grep -E '^KIOSK_API_KEY=' .env | cut -d= -f2- || true)"
fi

# 3) Savollar
say "\nSozlamalar (Enter = standart qiymat):"
read -r -p "  Bulut domeni  [cloud.poyezd.uz]: " CLOUD; CLOUD="${CLOUD:-cloud.poyezd.uz}"
read -r -p "  Avtobus nomi  [Avtobus-01]:      " NAME;  NAME="${NAME:-Avtobus-01}"
read -r -p "  Ulash kaliti (ixtiyoriy, darhol tasdiq uchun): " ENROLL

# 4) API kalit (mavjud bo'lsa saqlanadi, aks holda yangi tasodifiy)
if [ -n "$KEEP_KEY" ]; then
  KEY="$KEEP_KEY"
else
  KEY="$( (python3 -c 'import secrets;print(secrets.token_urlsafe(24))' 2>/dev/null) \
        || (head -c 18 /dev/urandom | base64 | tr -d '/+=' | cut -c1-24) )"
fi

# 5) .env yozish
{
  echo "# AVTOBUS.UZ — avto-yaratilgan ($(date +%Y-%m-%d))"
  echo "KIOSK_API_KEY=$KEY"
  echo "KIOSK_NAME=$NAME"
  echo "KIOSK_CLOUD_URL=$CLOUD"
  [ -n "$ENROLL" ] && echo "KIOSK_CLOUD_ENROLL=$ENROLL" || echo "# KIOSK_CLOUD_ENROLL="
  echo "# KIOSK_CLOUD_STATS=60"
} > .env
ok "✓ .env yaratildi"

# 6) Ishga tushirish
say "\nDocker image quriladi va ishga tushiriladi (birinchi marta bir necha daqiqa)..."
docker compose up -d --build

# 7) Manzil
IP="$(hostname -I 2>/dev/null | awk '{print $1}')"; IP="${IP:-<qurilma-IP>}"
ok "\n════════════════════════════════════════════"
ok " ✓ TAYYOR — Avtobus ishga tushdi"
ok "════════════════════════════════════════════"
echo "  Yo'lovchilar:   http://$IP/"
echo "  Bulut:          $CLOUD  (panelда \"$NAME\" ko'rinadi)"
[ -z "$ENROLL" ] && echo "  Keyingi qadam:  bulut panelida \"Tasdiqlash\" tugmasini bosing"
echo ""
echo "  Boshqarish:"
echo "    docker compose logs -f        # loglar"
echo "    docker compose restart        # qayta ishga tushirish"
echo "    docker compose down           # to'xtatish"
echo "    git pull && docker compose up -d --build   # yangilash"
