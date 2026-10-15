**User modul – Felhasználókezelés (/API/user/services.py)**

## **Áttekintés**

A user modul felelős a felhasználói profilok karbantartásáért, az adminisztrátori felhasználókezelésért (létrehozás, módosítás, inaktiválás) és a futárok állapotvizsgálatáért.

---

## **Szolgáltatások (services.py)**

### **update\_me(db: Session, user: User, data: UserUpdateMe) \-\> User**

> * **Működés**: A bejelentkezett felhasználó saját adatainak részleges frissítése.  
> * **Ellenőrzések**: Email módosítása esetén ellenőrzi az email cím egyediségét a többi aktív felhasználó között.

### **list\_users(db: Session, params: UserListParams) \-\> dict**

> * **Működés**: Lapozott felhasználói lista lekérése adminisztrátorok számára.  
> * **Szűrés**: Szerepkör (role), aktív állapot (is\_active), valamint név- és email-keresés (search szövegrészlet) alapján.

### **create\_user(db: Session, data: AdminUserCreate) \-\> User**

> * **Működés**: Új belső felhasználó (pl. futár vagy logisztikus) létrehozása adminisztrátor által.  
> * **Ellenőrzések**: Email cím egyediségének vizsgálata.

### **get\_user\_or\_404(db: Session, user\_id: int) \-\> User**

> * **Működés**: Felhasználó lekérése azonosító alapján. Ha nem létezik, 404 NOT FOUND hibát dob.

### **get\_courier\_or\_404(db: Session, courier\_id: int) \-\> User**

> * **Működés**: Segédfüggvény kifejezetten aktív futár (role \== COURIER és is\_active \== True) lekérésére. Hiánya esetén 404 NOT FOUND hibát dob.

### **admin\_update\_user(db: Session, admin: User, user\_id: int, data: AdminUserUpdate) \-\> User**

> * **Működés**: Bármely felhasználó adatainak vagy szerepkörének módosítása admin által.  
> * **Üzleti szabályok és ellenőrzések**:  
  * Email megváltoztatása vagy fiók reaktiválása esetén ellenőrzi az email egyediségét.  
  * Önmodosítási korlátozás: Az adminisztrátor a saját szerepkörét nem módosíthatja, és saját magát nem inaktiválhatja (409 CONFLICT).  
  * Futár védelme: Ha egy futárt inaktiválnának vagy felmentenének a futár szerepkörből, de nyitott csomagjai vannak (has\_open\_parcels), a műveletet a rendszer megtagadja (409 CONFLICT).

### **deactivate\_user(db: Session, admin: User, user\_id: int) \-\> None**

> * **Működés**: Felhasználó inaktiválása (is\_active \= False).  
> * **Ellenőrzések**: Adminisztrátor saját magát nem törölheti; nyitott csomagokkal rendelkező futár nem inaktiválható (409 CONFLICT).

### **has\_open\_parcels(db: Session, user\_id: int) \-\> bool**

> * **Működés**: Igaz értéket ad vissza, ha a futárhoz tartozik folyamatban lévő felvétel (PICKUP\_ASSIGNED, PICKED\_UP) vagy kézbesítés (DELIVERY\_ASSIGNED, OUT\_FOR\_DELIVERY, FAILED).

## ---

**Kapcsolódó sémák (schemas.py)**

> * UserCreateBase / AdminUserCreate: Személyes adatok, lakcím és szerepkör megadása.  
> * UserUpdateMe / AdminUserUpdate: Részleges frissítéshez (PatchModel), felülbírálható mezőkkel.  
> * UserRead, UserSummary, CourierPublic: Különböző részletezettségű kimeneti modellek.

## ---

**Végpontok (routes.py)**

> * **Saját profil**: GET /users/me, PATCH /users/me  
> * **Adminisztráció**: GET /users, POST /users, GET /users/{user\_id}, PATCH /users/{user\_id}, DELETE /users/{user\_id}

# ---