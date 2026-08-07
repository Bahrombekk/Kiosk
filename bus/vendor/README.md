# vendor/ — bundle qilinadigan tashqi binarlar

Bu papkaga **ikkita fayl** qo'ying (repoga kirmaydi — `.gitignore`da). Ular
`build.ps1` tomonidan `Avtobus.exe` yoniga bundle qilinadi, shunda **mijoz
qurilmasida Node.js yoki ffmpeg alohida o'rnatilmaydi**.

| Fayl | Nima | Qayerdan |
|---|---|---|
| `node.exe` | Nuxt (Nitro) veb-serverini ishga tushiradi | https://nodejs.org/dist/ — LTS, **win-x64** `.zip` ichidagi `node.exe` |
| `ffmpeg.exe` | Video "faststart" remux (mobil ijro tez ochilsin) | https://www.gyan.dev/ffmpeg/builds/ — "essentials" build, `bin\ffmpeg.exe` |
| `nssm.exe` | Windows Service wrapper (boot'da avto-start, qulasa restart) | https://nssm.cc/download — `win64\nssm.exe` |

## Qadamlar
1. Node.js LTS Windows **binary (.zip)** ni yuklab oling, ichidan `node.exe` ni
   shu papkaga nusxalang.
2. ffmpeg "essentials" ni yuklab oling, `bin\ffmpeg.exe` ni shu papkaga nusxalang.
3. `.\build.ps1` ni ishga tushiring.

> Faqat **x64** binarlar (Avtobus 64-bitли Windows uchun quriladi). Versiyani
> vaqti-vaqti bilan yangilab turing (xavfsizlik yangilanishlari).
