# API Endpoints with parcel status change

| **API** | **Status** | **Role** |
| --- | --- | --- |
| `POST`/parcels  | booked | customer |
| `POST`/warehouse/assign-pickup | pickup_assigned | logistician |
| `POST`/courier/parcels/{parcel_id}/pickup | picked_up | courier |
| `POST`/warehouse/check-in | in_warehouse | logistician |
| `POST`/warehouse/assign-delivery | delivery_assigned | logistician |
| `POST`/courier/parcels/{parcel_id}/start | out_for_delivery | courier |
| `POST`/courier/parcels/{parcel_id}/deliver | delivered | courier |
| `POST`/parcels/my/{parcel_id}/cancel | cancelled |  |
| `POST`/courier/parcels/{parcel_id}/fail | failed | courier |