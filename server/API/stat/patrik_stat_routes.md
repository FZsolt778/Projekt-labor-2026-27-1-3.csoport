**Stat modul – Statisztika és elemzések (/API/stat/routes.py)**

## **Áttekintés**

A stat modul elemzéseket és mutatókat biztosít az adminisztráció számára a raktár telítettségéről, történeti kihasználtságáról és a futárok teljesítményéről.

---

## **Végpontok és szolgáltatások**

### **1\. Aktuális raktárkihasználtság**

> * **Végpont**: GET /stats/warehouse  
> * **Jogosultság**: AdminUser  
> * **Működés (warehouse\_utilization)**:  
  * Kiszámítja a raktárban lévő csomagok számát és a kapacitás százalékos kihasználtságát.  
  * Részletes méret-lebontást ad a csomagokról (S, M, L, XL).

### **2\. Raktár történeti kihasználtsága**

> * **Végpont**: GET /stats/warehouse/history  
> * **Paraméterek**: StatsRangeParams (from\_date, to\_date, max. 366 nap)  
> * **Működés (warehouse\_history)**:  
  * Újrajátssza az eseménynaplót a megadott időszakra vonatkozóan.  
  * Napi bontásban meghatározza a nap végi raktári csomagszámot, a százalékos telítettséget, az átlagos kihasználtságot és a csúcsértéket (peak\_parcel\_count).

### **3\. Futárstatisztikák és jelentések**

> * **Végpont**: GET /stats/couriers  
> * **Paraméterek**: StatsRangeParams (from\_date, to\_date)  
> * **Működés (courier\_stats)**:  
  * Kiszámítja az egyes futárok felvételi (pickups\_count), kézbesítési (deliveries\_count) és hibaszámait (failed\_count).  
  * Meghatározza az aktív napok számát és a napi átlagos kézbesítéseket.  
  * Kiszámítja az átlagos kiszállítási időt percben (avg\_delivery\_minutes: out\_for\_delivery \-\> delivered) és az átlagos átfutási időt órában (avg\_lead\_time\_hours: picked\_up \-\> delivered).  
  * Összesített napi és futáronkénti bontást ad a megadott időszakra.