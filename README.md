# iphone-mask

Windows için ağ kimlik maskeleme aracı. Yetkili NAC / device fingerprinting testlerinde bir Windows cihazını ağda iPhone gibi göstermek için kullanılır: MAC adresini Apple OUI ile değiştirir, hostname'i iPhone yapar, TTL'i 64'e çeker, isteğe bağlı olarak DHCP Option 55 parametre sırasını iOS'a benzetmeyi dener ve düz HTTP trafiğinde User-Agent'i iPhone olarak değiştiren bir proxy açar.

## Kullanım amacı

Bu araç yalnızca üzerinde yazılı izin bulunan güvenlik değerlendirmelerinde (NAC bypass testi, device profiling değerlendirmesi) kullanılmak için yazıldı. Yetkisi olmayan bir ağda kullanmak politika ihlali veya yasal sorun doğurabilir.

## Nasıl çalışır

- MAC adresi: ağ adaptörünün kayıt defterindeki NetworkAddress değeri rastgele bir Apple OUI ile değiştirilir, adaptör yeniden başlatılır.
- Hostname: TCP/IP ve ComputerName kayıtları "iPhone" olarak güncellenir.
- TTL: Windows varsayılanı 128'den iOS varsayılanı olan 64'e çekilir.
- DHCP fingerprint: Windows DHCP servisi durdurulup iOS parametre sırasıyla özel bir DHCPDISCOVER paketi gönderilir. Bu adım ağın DHCP sunucusuna bağlı olarak başarısız olabilir.
- HTTP proxy: 127.0.0.1:8899 üzerinde çalışan bir proxy, düz HTTP isteklerindeki User-Agent başlığını iPhone olarak değiştirir. HTTPS trafiği şifreli olduğu için değiştirilmeden geçer.

Program kapatıldığında (CTRL+C, pencere kapatma, hata) tüm değişiklikler orijinal haline geri döndürülür.

## Çalıştırma

Yönetici izni gerekir. Çift tıklanırsa UAC ile otomatik yükseltme ister.

```
python main.py
```

## Sınırlamalar

- Derin paket analizi yapan kurumsal güvenlik duvarları DHCP parametre diziliminden veya TLS/JA3 fingerprint'inden gerçek işletim sistemini tespit edebilir.
- Windows arka plan servisleri (Windows Update, OneDrive vb.) Microsoft sunucularına istek atmaya devam eder.
- HTTPS trafiğinde User-Agent değiştirilmez.
