Şu anki en iyi: 79,556 sn (commit 296893c)

# İlerleme: Corkscrew, 1 tur, duran kalkış

Kabul kriteri: 1 turda hasar 0 ve pist dışı 0 s, 3 turluk yarış temiz, `baseline/perturb_test.py` ±%1 ile 20 varyantın
en az 19'u temiz. "Fark", o ana kadarki en iyi kabul edilen sonuca göredir. Ayrıntılar `EXPERIMENTS.md`'de.

| # | Tarih | Değişiklik (1 cümle) | Dosyalar | 1. tur (sn) | Fark (sn) | Hasar/Pist dışı | Sağlamlık (±%1) | Durum | Commit |
|---|---|---|---|---|---|---|---|---|---|
| E1 | 2026-10-15 | Başlangıç: ekibin kural tabanlı sürücüsü ve parametreleri, headless ölçüm. | `my_driver.py`, `best_params.json` | 84,788 | – | 0 / 0 s | ölçülmedi | Kabul (referans) | 0b2573f |
| E5 | 2026-10-15 | CMA-ES aramasının en hızlı temiz adayı. | `best_params.json` | 82,156 | −2,632 | 0 / 0,34 s (3 turda hasar 6) | ölçülmedi | Red (3. turda hasar, 1. turda 0,34 s pist dışı) | 0ba896a |
| E7 | 2026-10-15 | E5'e `min_speed` 47 ve `margin` 11. | `best_params.json` | 82,690 | −2,098 | 0 / 0 s | 20/20 | Kabul | 4be3d53 |
| E8 | 2026-10-16 | Tuna'nın sürücüsü: sensörden viraj hızı, tam gaz bandı, ışın eşitlik düzeltmesi. | `tuna/` | 80,332 | −2,358 | 0 / 0 s | 20/20 | Kabul | da5ba0a |
| E9a | 2026-10-16 | CMA-ES'in en hızlı temiz 1 tur adayı (`e9_g036_01`). | `fast/params.json` (aday) | 79,404 | −0,928 | 0 / 0 s | – | Red (3 turluk yarışta 0,66 s pist dışı, ön eleme) | 296893c |
| E9b | 2026-10-16 | CMA-ES adayı `e9_g036_07`. | `fast/params.json` (aday) | 79,692 | −0,640 | 0 / 0 s | 18/20 | Red (±%1'de 2 varyant pist dışı) | 296893c |
| E9 | 2026-10-16 | Tuna'nın sürücüsü `fast/`'a kopyalandı, 22 parametre CMA-ES ile ayarlandı (`e9_g040_05`). | `fast/my_driver.py`, `fast/params.json`, `fast/cmaes_fast.py` | 79,556 | −0,776 | 0 / 0 s | 20/20 | Kabul | 296893c |
| E10 | 2026-10-16 | Pist haritası, adım 1: Corkscrew orta çizgisi XML segmentlerinden kuruldu ve sensörlerle doğrulandı (3608,45 m, medyan ışın hatası 2,5 cm); sürüş değişmedi. | `mapped/track.py`, `mapped/verify_geometry.py`, `baseline/run_lap.py` | – | – | – | – | Kabul (altyapı) | 222b275 |
