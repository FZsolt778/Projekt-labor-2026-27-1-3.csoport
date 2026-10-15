**Warehouse modul – Raktárkezelés (/API/warehouse/routes.py)**

## **Áttekintés**

A warehouse modul a raktári bevételezésért, a raktárkapacitás kezeléséért, valamint a csomagfelvételek és kiszállítások futárokhoz rendeléséért felelős.

---

## **Végpontok és szolgáltatások**

### **1\. Raktár adatainak lekérése és frissítése**

> * **Lekérés**: GET /warehouse (Jogosultság: StaffUser) – Visszaadja a raktár nevét és kapacitását.  
> * **Módosítás**: PATCH /warehouse (Jogosultság: AdminUser) – Raktárkapacitás vagy név frissítése. A kapacitás nem csökkenthető a jelenleg raktárban tartózkodó csomagok száma alá (409 CONFLICT).

### **2\. Választható futárok listázása**

> * **Végpont**: GET /warehouse/couriers  
> * **Működés (list\_couriers)**: Az aktív futárok ábécé szerinti listáját adja vissza a logisztikus számára.

### **3\. Csomagok raktári bevételezése (Check-in)**

> * **Végpont**: POST /warehouse/check-in  
> * **Törzs**: CheckInRequest (parcel\_ids: csomagazonosítók listája)  
> * **Működés (check\_in)**:  
  * Tömeges bevételezés PICKED\_UP (felvett) vagy FAILED (sikertelenül kézbesített) státuszú csomagoknál.  
  * Zárással garantálja a tranzakcióbiztonságot, és ellenőrzi, hogy van-e elegendő szabad kapacitás a raktárban. Túllépés esetén 409 CONFLICT hibát ad.  
  * Sikeres bevételezés után a csomagok állapota IN\_WAREHOUSE lesz.

### **4\. Csomagfelvétel hozzárendelése futárhoz**

> * **Végpont**: POST /warehouse/assign-pickup  
> * **Törzs**: PickupAssignRequest (courier\_id, parcel\_ids)  
> * **Működés (assign\_pickup)**: A kijelölt csomagokhoz beállítja a felvevő futárt, a csomagok állapota PICKUP\_ASSIGNED lesz.

### **5\. Kézbesítés hozzárendelése futárhoz**

> * **Végpont**: POST /warehouse/assign-delivery  
> * **Törzs**: DeliveryAssignRequest (courier\_id, parcel\_ids, delivery\_date, delivery\_slot)  
> * **Működés (assign\_delivery)**:  
  * Raktárban lévő csomagok kiszállításának kiosztása.  
  * Ellenőrzi, hogy a kiszállítás napja nem korábbi-e a felvétel napjánál.  
  * Beállítja a kézbesítési dátumot, idősávot és a futárt, a csomag állapota DELIVERY\_ASSIGNED lesz.

# ---